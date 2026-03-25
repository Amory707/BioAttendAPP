from datetime import date
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html

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
    """Traite jusqu'a 5 images, valide une identite unique et retourne (embedding_moyen, indice_surete)."""
    if insightface is None:
        raise ImportError("insightface n'est pas installé. Exécutez pip install insightface")

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
        if min(pairwise_similarities) < similarity_threshold:
            raise ValueError(
                "Les visages televerses semblent appartenir a des personnes differentes."
            )
        avg_similarity = sum(pairwise_similarities) / len(pairwise_similarities)
        indice_surete = round(max(0.0, min(100.0, avg_similarity * 100.0)), 2)
    else:
        indice_surete = None

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

    if departement:
        utilisateurs = utilisateurs.filter(departement=departement)

    if biometrie:
        utilisateurs = FiltreBiometrique.filtrer_queryset(utilisateurs, biometrie)

    if date_debut:
        utilisateurs = utilisateurs.filter(date_debut=date_debut)

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
    recherche = request.GET.get('q', '').strip()
    type_filtre = request.GET.get('type', '')
    statut_filtre = request.GET.get('statut', '')

    pointages = Pointage.objects.select_related('utilisateur')

    if recherche:
        pointages = pointages.filter(
            Q(utilisateur__last_name__icontains=recherche)
            | Q(utilisateur__first_name__icontains=recherche)
        )

    if type_filtre:
        pointages = pointages.filter(type=type_filtre)

    if statut_filtre:
        pointages = pointages.filter(statut=statut_filtre)

    context = {
        'pointages': pointages,
        'choix_type': [('ENTREE', 'Entrée'), ('SORTIE', 'Sortie')],
        'choix_statut': [('VALIDE', 'Validé'), ('NON_VALIDE', 'Non validé')],
    }
    return render(request, 'utilisateur/pointage_list.html', context)


@login_required(login_url='login')
def alerte_list(request):
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
            request.POST, request.FILES,
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
            new_role = form.cleaned_data.get('role')
            from accounts.models import RoleUtilisateur
            if new_role:
                RoleUtilisateur.objects.get_or_create(utilisateur=utilisateur, role=new_role)
            messages.success(request, 'Employé créé avec succès.')
            return redirect('Employee:utilisateur_list')
    else:
        form = UtilisateurUnifiedForm(editing_self=True, request_user=request.user)
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
    if dernier and dernier.type == 'ENTREE':
        return format_html('<b style="background: #d4edda; color: #155724; padding: 5px; border-radius: 5px;">Présent</b>')
    return format_html('<b style="background: #f8d7da; color: #721c24; padding: 5px; border-radius: 5px;">Absent</b>')