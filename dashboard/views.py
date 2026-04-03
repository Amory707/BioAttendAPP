from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

from alerts.models import Alerte
from attendance.models import Pointage


def _deny_and_logout(request):
    messages.error(request, "Accès refusé : votre compte n'a pas les droits plateforme.")
    logout(request)
    return redirect('login')

@login_required(login_url='login')
def dashboard(request):
    if request.user.is_employe and not request.user.is_platform_admin:
        return redirect('dashboard:employee_home')

    if not request.user.is_platform_admin:
        return _deny_and_logout(request)

    context = {
        'user': request.user,
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url='login')
def employee_home(request):
    if request.user.is_platform_admin:
        return redirect('dashboard:index')
    if not request.user.is_employe:
        return _deny_and_logout(request)

    pointages_qs = Pointage.objects.filter(utilisateur=request.user)
    alertes_qs = Alerte.objects.filter(utilisateur=request.user)

    context = {
        'user': request.user,
        'total_pointages': pointages_qs.count(),
        'pointages_valides': pointages_qs.filter(statut='VALIDE').count(),
        'alertes_non_traitees': alertes_qs.exclude(statut='TRAITEE').count(),
        'recent_pointages': pointages_qs.order_by('-horodatage')[:8],
        'recent_alertes': alertes_qs.order_by('-date_creation')[:8],
    }
    return render(request, 'dashboard/employee_home.html', context)


@login_required(login_url='login')
def employee_pointages(request):
    if request.user.is_platform_admin:
        return redirect('dashboard:index')
    if not request.user.is_employe:
        return _deny_and_logout(request)

    type_filtre = request.GET.get('type', '').strip()
    statut_filtre = request.GET.get('statut', '').strip()

    pointages = Pointage.objects.filter(utilisateur=request.user)

    if type_filtre:
        pointages = pointages.filter(type=type_filtre)

    if statut_filtre:
        pointages = pointages.filter(statut=statut_filtre)

    context = {
        'pointages': pointages.order_by('-horodatage'),
        'type_filtre': type_filtre,
        'statut_filtre': statut_filtre,
        'choix_type': Pointage.TYPE_CHOICES,
        'choix_statut': Pointage.STATUT_CHOICES,
    }
    return render(request, 'dashboard/employee_pointages.html', context)


@login_required(login_url='login')
def employee_alertes(request):
    if request.user.is_platform_admin:
        return redirect('dashboard:index')
    if not request.user.is_employe:
        return _deny_and_logout(request)

    statut_filtre = request.GET.get('statut', '').strip()

    alertes = Alerte.objects.filter(utilisateur=request.user)
    if statut_filtre:
        alertes = alertes.filter(statut=statut_filtre)

    context = {
        'alertes': alertes.order_by('-date_creation'),
        'statut_filtre': statut_filtre,
        'choix_statut': Alerte.STATUT_CHOICES,
    }
    return render(request, 'dashboard/employee_alertes.html', context)

def logout_view(request):
    logout(request)
    return redirect('login')  
