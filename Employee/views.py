from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.utils.html import format_html
from django.urls import reverse
from datetime import date
import csv
from .models import Utilisateur, Pointage, Alerte, Role
from .forms import UtilisateurForm

try:
    import insightface
    import numpy as np
    from PIL import Image
except ImportError:
    insightface = None


def _compute_face_embedding(photo_file):
    if insightface is None:
        raise ImportError("insightface n'est pas installé. Exécutez pip install insightface")

    pil_image = Image.open(photo_file).convert('RGB')
    img_array = np.asarray(pil_image)

    app = insightface.app.FaceAnalysis(allowed_modules=['detection', 'recognition'])
    app.prepare(ctx_id=-1, det_size=(640, 640))

    faces = app.get(img_array)
    if not faces:
        return None

    return faces[0].embedding


class FiltreBiometrique:
    @staticmethod
    def filtrer_queryset(queryset, valeur):
        if valeur == 'enrole':
            return queryset.filter(Embedding_facial__isnull=False)
        elif valeur == 'non_enrole':
            return queryset.filter(Embedding_facial__isnull=True)
        return queryset

@login_required(login_url='login')
def utilisateur_list(request):
    recherche = request.GET.get('q', '').strip()
    departement = request.GET.get('departement', '')
    biometrie = request.GET.get('biometrie', '')
    date_debut = request.GET.get('date_debut', '')

    utilisateurs = Utilisateur.objects.all()

    if recherche:
        utilisateurs = utilisateurs.filter(
            Q(Nom__icontains=recherche) |
            Q(Prenom__icontains=recherche) |
            Q(Email__icontains=recherche)
        )

    if departement:
        utilisateurs = utilisateurs.filter(Departement=departement)

    if biometrie:
        utilisateurs = FiltreBiometrique.filtrer_queryset(utilisateurs, biometrie)

    if date_debut:
        utilisateurs = utilisateurs.filter(Date_debut=date_debut)

    utilisateurs = utilisateurs.prefetch_related('pointages', 'roles')

    context = {
        'utilisateurs': utilisateurs,
        'recherche': recherche,
        'filtre_departement': departement,
        'filtre_biometrie': biometrie,
        'filtre_date_debut': date_debut,
        'liste_departements': Utilisateur.objects.values_list('Departement', flat=True).distinct().exclude(Departement__isnull=True),
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
            Q(utilisateur__Nom__icontains=recherche) |
            Q(utilisateur__Prenom__icontains=recherche)
        )

    if type_filtre:
        pointages = pointages.filter(type=type_filtre)

    if statut_filtre:
        pointages = pointages.filter(statut=statut_filtre)

    context = {
        'pointages': pointages,
        'choix_type': [('ENTREE', 'Entrée'), ('SORTIE', 'Sortie')],
        'choix_statut': [('Validé', 'Validé'), ('Non validé', 'Non validé')],
    }
    return render(request, 'utilisateur/pointage_list.html', context)

@login_required(login_url='login')
def alerte_list(request):
    recherche = request.GET.get('q', '').strip()
    statut_filtre = request.GET.get('statut', '')

    alertes = Alerte.objects.select_related('utilisateur', 'pointage')

    if recherche:
        alertes = alertes.filter(
            Q(utilisateur__Nom__icontains=recherche) |
            Q(Description__icontains=recherche)
        )

    if statut_filtre:
        alertes = alertes.filter(Statut=statut_filtre)

    context = {
        'alertes': alertes,
        'choix_statut': [('NOUVELLE', 'Nouvelle'), ('VUE', 'Vue'), ('TRAITÉE', 'Traitée')],
    }
    return render(request, 'utilisateur/alerte_list.html', context)

# --- VIEWS CRUD EMPLOYES ---
@login_required(login_url='login')
def create_utilisateur(request):
    if request.method == 'POST':
        form = UtilisateurForm(request.POST, request.FILES)
        if form.is_valid():
            utilisateur = form.save(commit=False)
            photo = form.cleaned_data.get('Photo')
            if photo:
                embedding = _compute_face_embedding(photo)
                if embedding is None:
                    form.add_error('Photo', 'Aucun visage détecté sur la photo. Veuillez télécharger une photo claire du visage.')
                    return render(request, 'utilisateur/utilisateur_form.html', {'form': form, 'action': 'Créer'})
                utilisateur.Embedding_facial = embedding
            utilisateur.save()
            form.save_m2m()
            messages.success(request, 'Employé créé avec succès.')
            return redirect('Employee:utilisateur_list')
    else:
        form = UtilisateurForm()
    return render(request, 'utilisateur/utilisateur_form.html', {'form': form, 'action': 'Créer'})


@login_required(login_url='login')
def update_utilisateur(request, utilisateur_id):
    utilisateur = get_object_or_404(Utilisateur, pk=utilisateur_id)
    if request.method == 'POST':
        form = UtilisateurForm(request.POST, request.FILES, instance=utilisateur)
        if form.is_valid():
            utilisateur = form.save(commit=False)
            photo = form.cleaned_data.get('Photo')
            if photo:
                embedding = _compute_face_embedding(photo)
                if embedding is None:
                    form.add_error('Photo', 'Aucun visage détecté sur la photo. Veuillez télécharger une photo claire du visage.')
                    return render(request, 'utilisateur/utilisateur_form.html', {'form': form, 'action': 'Modifier'})
                utilisateur.Embedding_facial = embedding
            utilisateur.save()
            form.save_m2m()
            messages.success(request, 'Employé mis à jour avec succès.')
            return redirect('Employee:utilisateur_list')
    else:
        form = UtilisateurForm(instance=utilisateur)
    return render(request, 'utilisateur/utilisateur_form.html', {'form': form, 'action': 'Modifier'})


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
    """Affiche la liste des rôles définis dans le MLD"""
    roles = Role.objects.all()
    return render(request, 'utilisateur/role_list.html', {'roles': roles})


@login_required(login_url='login')
def exporter_csv(request):
    utilisateurs = Utilisateur.objects.all()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="utilisateurs_bioattend.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID_Utilisateur', 'Nom', 'Prénom', 'Email', 'Département'])
    for u in utilisateurs:
        writer.writerow([u.ID_Utilisateur, u.Nom, u.Prenom, u.Email, u.Departement])
    return response

def badge_presence(utilisateur):
    today = date.today()
    dernier = Pointage.objects.filter(utilisateur=utilisateur, horodatage__date=today).last()
    if dernier and dernier.type == 'ENTREE':
        return format_html('<b style="background: #d4edda; color: #155724; padding: 5px; border-radius: 5px;">Présent</b>')
    return format_html('<b style="background: #f8d7da; color: #721c24; padding: 5px; border-radius: 5px;">Absent</b>')