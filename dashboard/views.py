from datetime import timedelta

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.access import ADMIN_SPACE, EMPLOYEE_SPACE, get_active_space, set_active_space, user_can_access_employee_space
from accounts.models import Utilisateur

from alerts.models import Alerte
from attendance.models import Pointage


def _deny_and_logout(request):
    messages.error(request, "Accès refusé : votre compte n'a pas les droits plateforme.")
    logout(request)
    return redirect('login')


def _redirect_to_active_space(request):
    active_space = get_active_space(request)
    if active_space == EMPLOYEE_SPACE:
        return redirect('dashboard:employee_home')
    if active_space == ADMIN_SPACE:
        return redirect('dashboard:index')
    return _deny_and_logout(request)


def _employee_queryset_for_dashboard():
    return (
        Utilisateur.objects.filter(is_superuser=False)
        .exclude(roles__nom__iexact='admin')
        .exclude(roles__nom__iexact='acces_total')
        .distinct()
    )

@login_required(login_url='login')
def dashboard(request):
    if get_active_space(request) == EMPLOYEE_SPACE:
        return redirect('dashboard:employee_home')

    if not request.user.is_platform_admin:
        return _deny_and_logout(request)

    today = timezone.localdate()
    start_week = today - timedelta(days=6)

    employee_qs = _employee_queryset_for_dashboard()
    total_employees = employee_qs.count()

    today_present_count = (
        Pointage.objects.filter(
            utilisateur__in=employee_qs,
            horodatage__date=today,
            statut='VALIDE',
        )
        .values('utilisateur_id')
        .distinct()
        .count()
    )
    today_absent_count = max(total_employees - today_present_count, 0)

    not_recognized_today = Alerte.objects.filter(
        date_creation__date=today,
        type__in=['UTILISATEUR_INCONNU', 'ECHEC_RECONNAISSANCE', 'TENTATIVE_FRAUDE'],
    ).count()

    weekly_present_map = {
        item['jour']: item['total']
        for item in (
            Pointage.objects.filter(
                utilisateur__in=employee_qs,
                horodatage__date__gte=start_week,
                horodatage__date__lte=today,
                statut='VALIDE',
            )
            .annotate(jour=TruncDate('horodatage'))
            .values('jour')
            .annotate(total=Count('utilisateur', distinct=True))
        )
    }
    weekly_unknown_map = {
        item['jour']: item['total']
        for item in (
            Alerte.objects.filter(
                date_creation__date__gte=start_week,
                date_creation__date__lte=today,
                type__in=['UTILISATEUR_INCONNU', 'ECHEC_RECONNAISSANCE', 'TENTATIVE_FRAUDE'],
            )
            .annotate(jour=TruncDate('date_creation'))
            .values('jour')
            .annotate(total=Count('id'))
        )
    }

    weekly_stats = []
    for i in range(7):
        day = start_week + timedelta(days=i)
        presents = weekly_present_map.get(day, 0)
        absents = max(total_employees - presents, 0)
        unrecorded = weekly_unknown_map.get(day, 0)
        weekly_stats.append({
            'day': day.strftime('%a'),
            'presents': presents,
            'absents': absents,
            'unrecorded': unrecorded,
        })

    recent_checkins = (
        Pointage.objects.select_related('utilisateur')
        .filter(utilisateur__in=employee_qs)
        .order_by('-horodatage')[:10]
    )

    context = {
        'user': request.user,
        'total_employees': total_employees,
        'today_present_count': today_present_count,
        'today_absent_count': today_absent_count,
        'not_recognized_today': not_recognized_today,
        'weekly_stats': weekly_stats,
        'recent_checkins': recent_checkins,
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url='login')
def employee_home(request):
    if get_active_space(request) == ADMIN_SPACE:
        return redirect('dashboard:index')
    if not user_can_access_employee_space(request.user):
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
    if get_active_space(request) == ADMIN_SPACE:
        return redirect('dashboard:index')
    if not user_can_access_employee_space(request.user):
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
    if get_active_space(request) == ADMIN_SPACE:
        return redirect('dashboard:index')
    if not user_can_access_employee_space(request.user):
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


@login_required(login_url='login')
def switch_space(request, space):
    chosen_space = set_active_space(request, space)
    if chosen_space != space:
        messages.error(request, "Cet espace n'est pas disponible pour votre compte.")
    return _redirect_to_active_space(request)
