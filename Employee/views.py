from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.utils.html import format_html
from datetime import date
import csv
from .models import Utilisateur, Pointage, Alerte, Role

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

# --- AJOUT DE LA FONCTION MANQUANTE POUR LE MLD ---
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