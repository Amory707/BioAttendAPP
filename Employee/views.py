from datetime import date, datetime, timedelta

import csv
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.db.models.functions import ExtractHour, TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.utils.html import escape

from accounts.models import Role, Utilisateur

from alerts.models import Alerte

from attendance.models import Pointage

from .forms import UtilisateurUnifiedForm

MAX_UPLOAD_IMAGE_COUNT = 5
MAX_TOTAL_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

try:
    import insightface
    import numpy as np
    from PIL import Image, ImageOps

except ImportError:
    insightface = None


def _compute_face_embeddings(photo_files):
    """Traite les images, valide une identite unique et retourne (embedding_moyen, indice_surete)."""
    if insightface is None: raise ImportError("insightface n'est pas installé. Exécutez pip install insightface")

    app = insightface.app.FaceAnalysis(allowed_modules=['detection', 'recognition'])
    app.prepare(ctx_id=-1, det_size=(640, 640), det_thresh=0.35)

    similarity_threshold = 0.35 # Valeur à configurer

    embeddings = []
    for idx, photo_file in enumerate(photo_files[:5], start=1):
        pil_image = ImageOps.exif_transpose(Image.open(photo_file)).convert('RGB')
        img_array = np.array(pil_image)
        faces = app.get(img_array)

        if not faces:
            raise ValueError(
                f"Aucun visage détecté dans la photo n°{idx} ({photo_file.name}). "
                "Veuillez remplacer cette image par une photo claire du visage."
            )
        
        if len(faces) > 1:
            raise ValueError(
                f"La photo n°{idx} ({photo_file.name}) contient plusieurs visages. "
                "Veuillez fournir une image avec un seul visage."
            )
        
        embeddings.append(faces[0].embedding)

    if not embeddings:
        return None, None

    normed = []
    for emb in embeddings:
        emb_norm = np.linalg.norm(emb)
        if emb_norm == 0:
            continue
        normed.append(emb / emb_norm)

    if not normed:
        return None, None

    pairwise_similarities = []
    for i in range(len(normed)):
        for j in range(i + 1, len(normed)):
            similarity = float(np.dot(normed[i], normed[j]))
            pairwise_similarities.append(similarity)

    if pairwise_similarities:
        if min(pairwise_similarities) < similarity_threshold: raise ValueError("Les visages televerses semblent appartenir a des personnes differentes.")
        
        avg_similarity = sum(pairwise_similarities) / len(pairwise_similarities)
        indice_surete = round(max(0.0, min(100.0, avg_similarity * 100.0)), 2)

    else: indice_surete = None

    return np.mean(embeddings, axis=0), indice_surete

def _validate_photo_uploads(photo_files):
    if len(photo_files) > MAX_UPLOAD_IMAGE_COUNT:
        return f"Vous pouvez televerser au maximum {MAX_UPLOAD_IMAGE_COUNT} images."

    total_size = sum((photo.size or 0) for photo in photo_files)
    if total_size > MAX_TOTAL_UPLOAD_BYTES:
        max_mb = MAX_TOTAL_UPLOAD_BYTES // (1024 * 1024)
        return f"La taille totale des images depasse la limite autorisee ({max_mb} MB)."

    for photo in photo_files:
        content_type = getattr(photo, 'content_type', '') or ''
        if not content_type.startswith('image/'):
            return "Seuls les fichiers image sont autorises."

    return None


SORT_FIELDS = {
    'username': 'username',
    '-username': '-username',
    'last_name': 'last_name',
    '-last_name': '-last_name',
    'departement': 'departement',
    '-departement': '-departement',
    'indice_surete': 'indice_surete',
    '-indice_surete': '-indice_surete',
}

SORT_OPTIONS = [
    ('username', "Nom d'utilisateur (A → Z)"),
    ('-username', "Nom d'utilisateur (Z → A)"),
    ('last_name', 'Nom (A → Z)'),
    ('-last_name', 'Nom (Z → A)'),
    ('departement', 'Département (A → Z)'),
    ('-departement', 'Département (Z → A)'),
    ('indice_surete', 'Indice de sûreté (croissant)'),
    ('-indice_surete', 'Indice de sûreté (décroissant)'),
]


class FiltreBiometrique:
    @staticmethod
    def filtrer_queryset(queryset, valeur):
        if valeur == 'enrole':
            return queryset.filter(embedding_facial__isnull=False)
        if valeur == 'non_enrole':
            return queryset.filter(embedding_facial__isnull=True)
        return queryset


def _safe_parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _filtered_pointages_queryset(request, utilisateur=None, active_tab='pointage'):
    search = request.GET.get('q', '').strip()
    type_filtre = request.GET.get('type', '').strip()
    statut_filtre = request.GET.get('statut', '').strip()
    date_debut_raw = request.GET.get('date_debut', '').strip()
    date_fin_raw = request.GET.get('date_fin', '').strip()

    date_debut = _safe_parse_date(date_debut_raw)
    date_fin = _safe_parse_date(date_fin_raw)

    base_pointages = Pointage.objects.select_related('utilisateur')
    if utilisateur is not None: base_pointages = base_pointages.filter(utilisateur=utilisateur)
    if date_debut: base_pointages = base_pointages.filter(horodatage__date__gte=date_debut)
    if date_fin: base_pointages = base_pointages.filter(horodatage__date__lte=date_fin)

    filtered_pointages = base_pointages
    if search and utilisateur is None:
        filtered_pointages = filtered_pointages.filter(
            Q(utilisateur__first_name__icontains=search)
            | Q(utilisateur__last_name__icontains=search)
            | Q(utilisateur__username__icontains=search)
        )

    if type_filtre: filtered_pointages = filtered_pointages.filter(type=type_filtre)
    if statut_filtre: filtered_pointages = filtered_pointages.filter(statut=statut_filtre)
    if active_tab == 'pointage': filtered_pointages = filtered_pointages.filter(statut='VALIDE')

    return {
        'base_pointages': base_pointages,
        'filtered_pointages': filtered_pointages.order_by('-horodatage'),
        'search': search,
        'type_filtre': type_filtre,
        'statut_filtre': statut_filtre,
        'date_debut_raw': date_debut_raw,
        'date_fin_raw': date_fin_raw,
        'date_debut': date_debut,
        'date_fin': date_fin,
    }

def _build_statistics_context(request, utilisateur=None, active_tab='pointage'):

    filtered_data = _filtered_pointages_queryset(request, utilisateur=utilisateur, active_tab=active_tab)
    base_pointages = filtered_data['base_pointages']
    filtered_pointages = filtered_data['filtered_pointages']
    
    search = filtered_data['search']
    
    type_filtre = filtered_data['type_filtre']
    statut_filtre = filtered_data['statut_filtre']
    
    date_debut_raw = filtered_data['date_debut_raw']
    date_fin_raw = filtered_data['date_fin_raw']
    date_debut = filtered_data['date_debut']
    date_fin = filtered_data['date_fin']

    total = base_pointages.count()
    total_entrees = base_pointages.filter(type='ENTREE').count()
    total_sorties = base_pointages.filter(type='SORTIE').count()
    total_valides = base_pointages.filter(statut='VALIDE').count()
    total_invalides = base_pointages.filter(statut='NON_VALIDE').count()
    
    confiance_moyenne = base_pointages.aggregate(moyenne=Avg('score_confiance'))['moyenne']
    confiance_moyenne = round(confiance_moyenne or 0.0, 2)
    taux_validation = round((total_valides / total) * 100, 2) if total else 0.0

    users_scope = Utilisateur.objects.all()
    if utilisateur is not None:
        users_scope = users_scope.filter(pk=utilisateur.pk)

    user_summaries = list(
        users_scope.annotate(
            total_pointages=Count('pointages'),
            total_valides=Count('pointages', filter=Q(pointages__statut='VALIDE')),
            total_invalides=Count('pointages', filter=Q(pointages__statut='NON_VALIDE')),
            moyenne_confiance=Avg('pointages__score_confiance'),
        ).order_by('-total_pointages', 'last_name', 'first_name')
    )

    for summary in user_summaries:
        summary.moyenne_confiance = round(summary.moyenne_confiance or 0.0, 2)
        summary.taux_validation = round((summary.total_valides / summary.total_pointages) * 100, 2) if summary.total_pointages else 0.0

    daily_rows = list(
        base_pointages
        .annotate(jour=TruncDate('horodatage'))
        .values('jour')
        .annotate(
            total=Count('id'),
            entrees=Count('id', filter=Q(type='ENTREE')),
            sorties=Count('id', filter=Q(type='SORTIE')),
            invalides=Count('id', filter=Q(statut='NON_VALIDE')),
        )
        .order_by('jour')
    )

    day_max = max((row['total'] for row in daily_rows), default=0)
    daily_chart = []
    for row in daily_rows:
        total_row = row['total'] or 0
        width = int((total_row / day_max) * 100) if day_max else 0
        daily_chart.append({
            'label': row['jour'].strftime('%d/%m/%Y') if row['jour'] else '-',
            'total': total_row,
            'entrees': row['entrees'] or 0,
            'sorties': row['sorties'] or 0,
            'invalides': row['invalides'] or 0,
            'width': max(width, 4) if total_row else 0,
        })

    hourly_rows = {
        item['heure']: item['total']
        for item in base_pointages.annotate(heure=ExtractHour('horodatage')).values('heure').annotate(total=Count('id'))
    }
    hourly_max = max(hourly_rows.values(), default=0)
    hourly_chart = []

    for hour in range(24):
        value = hourly_rows.get(hour, 0)
        width = int((value / hourly_max) * 100) if hourly_max else 0
        hourly_chart.append({
            'label': f"{hour:02d}h",
            'total': value,
            'width': max(width, 4) if value else 0,
        })

    alerts_qs = Alerte.objects.all()
    if utilisateur is not None:
        alerts_qs = alerts_qs.filter(
            Q(utilisateur=utilisateur)
            | Q(
                utilisateur__isnull=True,
                type__in=['UTILISATEUR_INCONNU', 'ECHEC_RECONNAISSANCE', 'TENTATIVE_FRAUDE'],
            )
        )

    if date_debut: alerts_qs = alerts_qs.filter(date_creation__date__gte=date_debut)
    if date_fin: alerts_qs = alerts_qs.filter(date_creation__date__lte=date_fin)

    alert_totales = alerts_qs.count()
    alertes_echec_reco = alerts_qs.filter(type='ECHEC_RECONNAISSANCE').count()
    alertes_inconnu = alerts_qs.filter(type='UTILISATEUR_INCONNU').count()
    alertes_fraude = alerts_qs.filter(type='TENTATIVE_FRAUDE').count()
    alertes_retard = alerts_qs.filter(type='RETARD').count()
    alertes_absence = alerts_qs.filter(type='ABSENCE').count()
    alertes_double_pointage = alerts_qs.filter(type='DOUBLE_POINTAGE').count()

    last_30_days = timezone.now() - timedelta(days=30)
    recent_pointages = base_pointages.filter(horodatage__gte=last_30_days)
    recent_total = recent_pointages.count()
    tendance_label = 'Stable'
    if recent_total:
        recent_invalid = recent_pointages.filter(statut='NON_VALIDE').count()
        failure_rate = (recent_invalid / recent_total) * 100
        if failure_rate <= 5: tendance_label = 'Tres bon'
        elif failure_rate <= 12: tendance_label = 'Correct'
        else: tendance_label = 'A surveiller'

    confidence_timeline_data = list(
        base_pointages.annotate(jour=TruncDate('horodatage')).values('jour').annotate(confiance=Avg('score_confiance')).order_by('jour')
    )

    confidence_timeline = {
        'labels': [item['jour'].strftime('%d/%m') for item in confidence_timeline_data if item['jour']],
        'data': [round(item['confiance'] or 0.0, 2) for item in confidence_timeline_data]
    }
    
    daily_chart_data_chart = {
        'labels': [item['label'] for item in daily_chart],
        'entrees': [item['entrees'] for item in daily_chart],
        'sorties': [item['sorties'] for item in daily_chart],
        'invalides': [item['invalides'] for item in daily_chart],
    }
    
    hourly_chart_data_chart = {
        'labels': [item['label'] for item in hourly_chart],
        'data': [item['total'] for item in hourly_chart],
    }
    
    alert_types_data = {
        'labels': ['Échec reco', 'Utilisateur inconnu', 'Tentative fraude', 'Retard', 'Absence', 'Double pointage'],
        'data': [alertes_echec_reco, alertes_inconnu, alertes_fraude, alertes_retard, alertes_absence, alertes_double_pointage],
    }

    problem_q = request.GET.get('problem_q', '').strip()
    problem_type = request.GET.get('problem_type', '').strip()
    problem_status = request.GET.get('problem_status', '').strip()
    problem_type_choices = [
        ('UTILISATEUR_INCONNU', 'Utilisateur inconnu'),
        ('ECHEC_RECONNAISSANCE', 'Echec reconnaissance'),
        ('TENTATIVE_FRAUDE', 'Tentative de fraude'),
    ]

    valid_problem_types = {value for value, _ in problem_type_choices}
    valid_problem_statuses = {value for value, _ in Alerte.STATUT_CHOICES}

    problem_alerts = alerts_qs.filter(type__in=valid_problem_types)
    if problem_q:
        problem_alerts = problem_alerts.filter(
            Q(description__icontains=problem_q)
            | Q(utilisateur__first_name__icontains=problem_q)
            | Q(utilisateur__last_name__icontains=problem_q)
            | Q(utilisateur__username__icontains=problem_q)
        )
    if problem_type in valid_problem_types: problem_alerts = problem_alerts.filter(type=problem_type)
    if problem_status in valid_problem_statuses: problem_alerts = problem_alerts.filter(statut=problem_status)

    problem_alerts = problem_alerts.select_related('utilisateur').order_by('-date_creation')

    if utilisateur is None: pointage_export_url = reverse('Employee:pointage_export_csv')
    else: pointage_export_url = reverse('Employee:pointage_export_utilisateur_csv', kwargs={'utilisateur_id': utilisateur.pk})

    return {
        'active_tab': active_tab,
        'scope_utilisateur': utilisateur,
        'is_user_scope': utilisateur is not None,
        'pointages': filtered_pointages[:200],
        'total_pointages': total,
        'total_entrees': total_entrees,
        'total_sorties': total_sorties,
        'total_valides': total_valides,
        'total_invalides': total_invalides,
        'confiance_moyenne': confiance_moyenne,
        'taux_validation': taux_validation,
        'alert_totales': alert_totales,
        'alertes_echec_reco': alertes_echec_reco,
        'alertes_inconnu': alertes_inconnu,
        'alertes_fraude': alertes_fraude,
        'alertes_retard': alertes_retard,
        'alertes_absence': alertes_absence,
        'alertes_double_pointage': alertes_double_pointage,
        'tendance_label': tendance_label,
        'daily_chart': daily_chart,
        'hourly_chart': hourly_chart,
        'user_summaries': user_summaries[:20],
        'q': search,
        'type_filtre': type_filtre,
        'statut_filtre': statut_filtre,
        'date_debut': date_debut_raw,
        'date_fin': date_fin_raw,
        'pointage_export_url': pointage_export_url,
        'choix_type': Pointage.TYPE_CHOICES,
        'choix_statut': Pointage.STATUT_CHOICES,
        'confidence_timeline_json': json.dumps(confidence_timeline),
        'daily_chart_json': json.dumps(daily_chart_data_chart),
        'hourly_chart_json': json.dumps(hourly_chart_data_chart),
        'alert_types_json': json.dumps(alert_types_data),
        'confidence_timeline': confidence_timeline,
        'alert_types_data': alert_types_data,
        'problem_alerts': problem_alerts[:200],
        'problem_q': problem_q,
        'problem_type': problem_type,
        'problem_status': problem_status,
        'problem_type_choices': problem_type_choices,
        'problem_status_choices': Alerte.STATUT_CHOICES,
    }

@login_required(login_url='login')
def exporter_pointages_csv(request, utilisateur_id=None):
    utilisateur = None
    if utilisateur_id is not None: utilisateur = get_object_or_404(Utilisateur, pk=utilisateur_id)

    active_tab = request.GET.get('tab', 'pointage').strip().lower()
    if active_tab not in {'pointage', 'analytique', 'problemes'}: active_tab = 'pointage'

    filtered_data = _filtered_pointages_queryset(request, utilisateur=utilisateur, active_tab=active_tab)
    pointages = filtered_data['filtered_pointages']

    response = HttpResponse(content_type='text/csv')
    if utilisateur is None: filename = 'pointages_export.csv'
    else: filename = f'pointages_{utilisateur.username}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'ID Pointage',
        'Date Heure',
        'Username',
        'Nom',
        'Prenom',
        'Type',
        'Statut',
        'Score IA',
    ])

    for pointage in pointages:
        writer.writerow([
            pointage.pk,
            pointage.horodatage.strftime('%Y-%m-%d %H:%M:%S') if pointage.horodatage else '',
            pointage.utilisateur.username,
            pointage.utilisateur.last_name,
            pointage.utilisateur.first_name,
            pointage.type,
            pointage.statut,
            pointage.score_confiance,
        ])

    return response

@login_required(login_url='login')
def utilisateur_list(request):
    recherche = request.GET.get('q', '').strip()
    departement = request.GET.get('departement', '')
    biometrie = request.GET.get('biometrie', '')
    date_debut = request.GET.get('date_debut', '')
    tri = request.GET.get('tri', 'username')

    utilisateurs = Utilisateur.objects.all()

    if recherche:
        utilisateurs = utilisateurs.filter(
            Q(last_name__icontains=recherche)
            | Q(first_name__icontains=recherche)
            | Q(email__icontains=recherche)
        )

    if departement: utilisateurs = utilisateurs.filter(departement=departement)

    if biometrie: utilisateurs = FiltreBiometrique.filtrer_queryset(utilisateurs, biometrie)

    if date_debut: utilisateurs = utilisateurs.filter(date_debut=date_debut)

    order_field = SORT_FIELDS.get(tri, 'username')
    utilisateurs = utilisateurs.order_by(order_field).prefetch_related('pointages', 'roles')

    context = {
        'utilisateurs': utilisateurs,
        'recherche': recherche,
        'filtre_departement': departement,
        'filtre_biometrie': biometrie,
        'filtre_date_debut': date_debut,
        'tri': tri,
        'sort_options': SORT_OPTIONS,
        'liste_departements': Utilisateur.objects.values_list('departement', flat=True)
        .distinct()
        .exclude(departement__isnull=True),
    }

    return render(request, 'utilisateur/utilisateur_list.html', context)

@login_required(login_url='login')
def utilisateur_detail(request, utilisateur_id):
    utilisateur = get_object_or_404(Utilisateur, pk=utilisateur_id)
    pointages = utilisateur.pointages.order_by('-horodatage')

    today = date.today()
    dernier_pointage = pointages.filter(horodatage__date=today).last()

    context = {
        'utilisateur': utilisateur,
        'pointages': pointages,
        'dernier_pointage': dernier_pointage,
        'has_embedding': utilisateur.embedding_facial is not None,
    }

    return render(request, 'utilisateur/utilisateur_detail.html', context)


@login_required(login_url='login')
def pointage_list(request):
    context = _build_statistics_context(request, active_tab='pointage')
    return render(request, 'utilisateur/statistiques.html', context)


@login_required(login_url='login')
def statistiques_analytique(request):
    context = _build_statistics_context(request, active_tab='analytique')
    return render(request, 'utilisateur/statistiques.html', context)


@login_required(login_url='login')
def statistiques_problemes(request):
    context = _build_statistics_context(request, active_tab='problemes')
    return render(request, 'utilisateur/statistiques.html', context)


@login_required(login_url='login')
def statistiques_utilisateur(request, utilisateur_id):
    utilisateur = get_object_or_404(Utilisateur, pk=utilisateur_id)
    active_tab = request.GET.get('tab', 'pointage').strip().lower()
    if active_tab not in {'pointage', 'analytique', 'problemes'}: active_tab = 'pointage'
    context = _build_statistics_context(request, utilisateur=utilisateur, active_tab=active_tab)
    return render(request, 'utilisateur/statistiques.html', context)


@login_required(login_url='login')
def alerte_list(request):
    if request.method == 'POST':
        if request.POST.get('delete_all') == '1':
            Alerte.objects.all().update(statut='TRAITEE')
            messages.success(request, 'Toutes les alertes ont été marquées comme traitées.')
            return redirect('Employee:alerte_list')

        if request.POST.get('delete_selected') == '1':
            selected_ids = request.POST.getlist('selected_alertes')
            if selected_ids:
                Alerte.objects.filter(id__in=selected_ids).update(statut='TRAITEE')
                messages.success(request, 'Alertes sélectionnées marquées comme traitées.')
            
            else: messages.info(request, 'Aucune alerte sélectionnée pour être traitée.')
            
            return redirect('Employee:alerte_list')

        messages.info(request, 'Aucune action valide pour les alertes.')
        return redirect('Employee:alerte_list')

    recherche = request.GET.get('q', '').strip()
    statut_filtre = request.GET.get('statut', '')

    alertes = Alerte.objects.select_related('utilisateur', 'pointage')

    if recherche:
        alertes = alertes.filter(
            Q(utilisateur__last_name__icontains=recherche)
            | Q(description__icontains=recherche)
        )

    if statut_filtre:
        alertes = alertes.filter(statut=statut_filtre)

    context = {
        'alertes': alertes,
        'choix_statut': [('NOUVELLE', 'Nouvelle'), ('VUE', 'Vue'), ('TRAITEE', 'Traitée')],
    }

    return render(request, 'utilisateur/alerte_list.html', context)

@login_required(login_url='login')
def create_utilisateur(request):
    if request.method == 'POST':
        photos = request.FILES.getlist('photos')
        form = UtilisateurUnifiedForm(
            request.POST,
            request.FILES,
            editing_self=True, request_user=request.user,
        )
        if form.is_valid():
            upload_error = _validate_photo_uploads(photos)
            if upload_error:
                form.add_error(None, upload_error)
                return render(request, 'utilisateur/utilisateur_form.html', {
                    'form': form, 'action': 'Créer', 'editing_self': True, 'has_embedding': False,
                })

            utilisateur = form.save(commit=False)
            if photos and insightface is not None:
                try:
                    embedding, indice_surete = _compute_face_embeddings(photos)
                except ValueError as exc:
                    form.add_error(None, str(exc))
                    return render(request, 'utilisateur/utilisateur_form.html', {
                        'form': form, 'action': 'Créer', 'editing_self': True, 'has_embedding': False,
                    })
                if embedding is None:
                    form.add_error(None, 'Aucun visage détecté dans les photos fournies. Veuillez utiliser des photos claires du visage.')
                    return render(request, 'utilisateur/utilisateur_form.html', {
                        'form': form, 'action': 'Créer', 'editing_self': True, 'has_embedding': False,
                    })
                utilisateur.embedding_facial = embedding
                utilisateur.indice_surete = indice_surete
            utilisateur.save()
            form.save_roles(utilisateur)
            messages.success(request, 'Employé créé avec succès.')
            return redirect('Employee:utilisateur_list')
    else: form = UtilisateurUnifiedForm(editing_self=True, request_user=request.user)
    
    return render(request, 'utilisateur/utilisateur_form.html', {
        'form': form, 'action': 'Créer', 'editing_self': True, 'has_embedding': False,
    })

@login_required(login_url='login')
def update_utilisateur(request, utilisateur_id):
    utilisateur = get_object_or_404(Utilisateur, pk=utilisateur_id)
    editing_self = (request.user.pk == utilisateur.pk)

    if request.method == 'POST':
        photos = request.FILES.getlist('photos')
        form = UtilisateurUnifiedForm(
            request.POST, request.FILES,
            instance=utilisateur,
            editing_self=editing_self,
            request_user=request.user,
        )

        if form.is_valid():
            upload_error = _validate_photo_uploads(photos)
            if upload_error:
                form.add_error(None, upload_error)
                return render(request, 'utilisateur/utilisateur_form.html', {
                    'form': form, 'action': 'Modifier',
                    'editing_self': editing_self, 'utilisateur': utilisateur,
                    'has_embedding': utilisateur.embedding_facial is not None,
                })

            utilisateur_obj = form.save()
            if photos and insightface is not None:
                try:
                    embedding, indice_surete = _compute_face_embeddings(photos)
                except ValueError as exc:
                    form.add_error(None, str(exc))
                    return render(request, 'utilisateur/utilisateur_form.html', {
                        'form': form, 'action': 'Modifier',
                        'editing_self': editing_self, 'utilisateur': utilisateur,
                        'has_embedding': utilisateur.embedding_facial is not None,
                    })
                
                if embedding is None:
                    form.add_error(None, 'Aucun visage détecté dans les photos fournies. Veuillez utiliser des photos claires du visage.')
                    return render(request, 'utilisateur/utilisateur_form.html', {
                        'form': form, 'action': 'Modifier',
                        'editing_self': editing_self, 'utilisateur': utilisateur,
                        'has_embedding': utilisateur.embedding_facial is not None,
                    })
                
                utilisateur_obj.embedding_facial = embedding
                utilisateur_obj.indice_surete = indice_surete
                utilisateur_obj.save(update_fields=['embedding_facial', 'indice_surete'])

            messages.success(request, 'Employé mis à jour avec succès.')

            return redirect('Employee:utilisateur_list')
    else:
        form = UtilisateurUnifiedForm(
            instance=utilisateur,
            editing_self=editing_self,
            request_user=request.user,
        )

    return render(request, 'utilisateur/utilisateur_form.html', {
        'form': form,
        'action': 'Modifier',
        'editing_self': editing_self,
        'utilisateur': utilisateur,
        'has_embedding': utilisateur.embedding_facial is not None,
    })

@login_required(login_url='login')
def delete_utilisateur(request, utilisateur_id):
    utilisateur = get_object_or_404(Utilisateur, pk=utilisateur_id)
    if request.method == 'POST':
        utilisateur.delete()
        messages.success(request, 'Employé supprimé avec succès.')
        return redirect('Employee:utilisateur_list')
    return render(request, 'utilisateur/utilisateur_confirm_delete.html', {'utilisateur': utilisateur})


@login_required(login_url='login')
def role_list(request):
    roles = Role.objects.all()
    return render(request, 'utilisateur/role_list.html', {'roles': roles})


@login_required(login_url='login')
def exporter_csv(request):
    utilisateurs = Utilisateur.objects.all()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="utilisateurs_bioattend.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Nom', 'Prénom', 'Email', 'Département'])
    for utilisateur in utilisateurs:
        writer.writerow([
            utilisateur.pk,
            utilisateur.last_name,
            utilisateur.first_name,
            utilisateur.email,
            utilisateur.departement,
        ])
    return response


def badge_presence(utilisateur):
    today = date.today()
    dernier = Pointage.objects.filter(utilisateur=utilisateur, horodatage__date=today).last()
    if dernier and dernier.type == 'ENTREE': return format_html('<b style="background: #d4edda; color: #155724; padding: 5px; border-radius: 5px;">Présent</b>')
    return format_html('<b style="background: #f8d7da; color: #721c24; padding: 5px; border-radius: 5px;">Absent</b>')