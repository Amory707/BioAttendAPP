import csv
from datetime import datetime, time, timedelta

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.db.models import Count, Q, Min
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.access import ADMIN_SPACE, EMPLOYEE_SPACE, get_active_space, set_active_space, user_can_access_employee_space
from accounts.models import Utilisateur
from alerts.models import Alerte

from attendance.models import Pointage
from attendance.utils import summarize_work_time, format_duration
from schedule.services import attach_schedule_display, analyze_day, get_belgian_holidays, get_schedule_settings

EMPLOYEE_ALERT_TYPES = [
    'RETARD',
    'ABSENCE',
    'DEPART_ANTICIPE',
    'JOURNEE_COURTE',
    'DOUBLE_POINTAGE',
    'DEMANDE_PLANNING',
]


def _user_label(utilisateur):
    return utilisateur.get_full_name() or utilisateur.username


def _safe_parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _deny_and_logout(request):
    messages.error(request, "Accès refusé : votre compte n'a pas les droits plateforme.")
    logout(request)
    return redirect('login')

def _redirect_to_active_space(request):
    active_space = get_active_space(request)
    if active_space == EMPLOYEE_SPACE: return redirect('dashboard:employee_home')
    if active_space == ADMIN_SPACE: return redirect('dashboard:index')
    return _deny_and_logout(request)

def _employee_queryset_for_dashboard():
    # Dashboard KPIs must include every user account.
    return Utilisateur.objects.all().distinct()


def _compute_punctuality_counts_for_users(users, target_day):
    if not users:
        return {'late': 0, 'early_departure': 0, 'short_day': 0}

    settings_obj = get_schedule_settings()
    holiday_map = get_belgian_holidays(target_day, target_day)
    late = 0
    early_departure = 0
    short_day = 0

    for utilisateur in users:
        analysis = analyze_day(utilisateur, target_day, settings_obj=settings_obj, holiday_map=holiday_map)
        late += int(analysis['late'])
        early_departure += int(analysis['early_departure'])
        short_day += int(analysis['short_day'])

    return {
        'late': late,
        'early_departure': early_departure,
        'short_day': short_day,
    }


def _absence_reason(utilisateur, analysis, target_day):
    if analysis['absence_requests']:
        reasons = sorted({item.get_category_display() for item in analysis['absence_requests']})
        return f"Absence justifiée ({', '.join(reasons)})"

    if analysis['holiday_name']:
        return f"Jour férié ({analysis['holiday_name']})"

    if target_day.weekday() >= 5:
        return 'Repos hebdomadaire'

    if utilisateur.date_debut and target_day < utilisateur.date_debut:
        return 'Pas encore en poste'

    if utilisateur.date_fin and target_day > utilisateur.date_fin:
        return 'Contrat terminé'

    return 'Aucun justificatif identifié'


def _time_delta_on_day(target_day, lhs, rhs):
    return datetime.combine(target_day, lhs) - datetime.combine(target_day, rhs)


def _local_day_bounds(target_day):
    tz = timezone.get_current_timezone()
    start_local = timezone.make_aware(datetime.combine(target_day, time.min), tz)
    end_local = start_local + timedelta(days=1)
    return start_local, end_local


def _collect_punctuality_rows(metric, target_day):
    settings_obj = get_schedule_settings()
    holiday_map = get_belgian_holidays(target_day, target_day)
    rows = []

    for utilisateur in _employee_queryset_for_dashboard().order_by('first_name', 'last_name', 'username'):
        analysis = analyze_day(utilisateur, target_day, settings_obj=settings_obj, holiday_map=holiday_map)

        if metric == 'late' and analysis['late'] and analysis['first_entry'] is not None:
            actual_entry = timezone.localtime(analysis['first_entry']).time()
            expected_entry = settings_obj.arrival_window_end
            delay = _time_delta_on_day(target_day, actual_entry, expected_entry)
            rows.append({
                'utilisateur': utilisateur,
                'label': _user_label(utilisateur),
                'time_display': actual_entry.strftime('%H:%M'),
                'detail': (
                    f"Arrivée à {actual_entry.strftime('%H:%M')} "
                    f"(seuil {expected_entry.strftime('%H:%M')}) · "
                    f"retard de {format_duration(delay)}"
                ),
            })

        elif metric == 'early' and analysis['early_departure'] and analysis['last_exit'] is not None:
            actual_exit = timezone.localtime(analysis['last_exit']).time()
            expected_exit = settings_obj.departure_window_start
            early_delta = _time_delta_on_day(target_day, expected_exit, actual_exit)
            rows.append({
                'utilisateur': utilisateur,
                'label': _user_label(utilisateur),
                'time_display': actual_exit.strftime('%H:%M'),
                'detail': (
                    f"Sortie à {actual_exit.strftime('%H:%M')} "
                    f"(seuil {expected_exit.strftime('%H:%M')}) · "
                    f"anticipation de {format_duration(early_delta)}"
                ),
            })

        elif metric == 'short' and analysis['short_day']:
            required_duration = timedelta(minutes=settings_obj.required_daily_minutes)
            missing_duration = max(required_duration - analysis['worked_duration'], timedelta())
            rows.append({
                'utilisateur': utilisateur,
                'label': _user_label(utilisateur),
                'time_display': analysis['worked_duration_display'],
                'detail': (
                    f"Temps requis: {format_duration(required_duration)} · "
                    f"manque: {format_duration(missing_duration)}"
                ),
            })

    return rows

@login_required(login_url='login')
def dashboard(request):
    if get_active_space(request) == EMPLOYEE_SPACE: return redirect('dashboard:employee_home')

    if not request.user.is_platform_admin: return _deny_and_logout(request)

    today = timezone.localdate()
    start_week = today - timedelta(days=6)
    today_start, today_end = _local_day_bounds(today)

    employee_qs = _employee_queryset_for_dashboard()
    employee_list = list(employee_qs)
    total_employees = employee_qs.count()

    today_present_count = (
        Pointage.objects.filter(
            utilisateur__in=employee_qs,
            horodatage__gte=today_start,
            horodatage__lt=today_end,
            statut='VALIDE',
        )
        .values('utilisateur_id')
        .distinct()
        .count()
    )

    today_absent_count = max(total_employees - today_present_count, 0)

    # Keep this metric aligned with "Stat Sécurité" source of truth.
    not_recognized_today = Alerte.objects.filter(type__in=Alerte.SECURITY_TYPES).count()

    settings_obj = get_schedule_settings()
    week_holidays = get_belgian_holidays(start_week, today)

    weekly_stats = []
    for i in range(7):
        day = start_week + timedelta(days=i)
        day_start, day_end = _local_day_bounds(day)

        present_user_ids = set(
            Pointage.objects.filter(
                utilisateur__in=employee_qs,
                horodatage__gte=day_start,
                horodatage__lt=day_end,
                statut='VALIDE',
            )
            .values_list('utilisateur_id', flat=True)
            .distinct()
        )

        justified_absences = 0
        unjustified_absences = 0
        for utilisateur in employee_list:
            if utilisateur.pk in present_user_ids:
                continue
            analysis = analyze_day(utilisateur, day, settings_obj=settings_obj, holiday_map=week_holidays)
            if analysis['required_presence']:
                unjustified_absences += 1
            else:
                justified_absences += 1

        security_incidents = Pointage.objects.filter(
            horodatage__gte=day_start,
            horodatage__lt=day_end,
            origine=Pointage.ORIGINE_POINTEUSE,
            statut='NON_VALIDE',
            incident_type__in=['UTILISATEUR_INCONNU', 'ECHEC_RECONNAISSANCE', 'TENTATIVE_FRAUDE'],
        ).count()

        weekly_stats.append({
            'day': day.strftime('%a'),
            'presents': len(present_user_ids),
            'justified_absences': justified_absences,
            'unjustified_absences': unjustified_absences,
            'security_incidents': security_incidents,
        })

    punctuality_counts = _compute_punctuality_counts_for_users(employee_list, today)
    today_late_count = punctuality_counts['late']
    today_early_departure_count = punctuality_counts['early_departure']
    today_short_day_count = punctuality_counts['short_day']

    recent_checkins = list(
        Pointage.objects.select_related('utilisateur')
        .filter(utilisateur__in=employee_qs)
        .order_by('-horodatage')[:10]
    )
    recent_checkins = attach_schedule_display(recent_checkins)

    context = {
        'user': request.user,
        'total_employees': total_employees,
        'today_present_count': today_present_count,
        'today_absent_count': today_absent_count,
        'today_late_count': today_late_count,
        'today_early_departure_count': today_early_departure_count,
        'today_short_day_count': today_short_day_count,
        'not_recognized_today': not_recognized_today,
        'weekly_stats': weekly_stats,
        'recent_checkins': recent_checkins,
    }

    return render(request, 'dashboard.html', context)


@login_required(login_url='login')
def today_present_list(request):
    if get_active_space(request) == EMPLOYEE_SPACE:
        return redirect('dashboard:employee_home')

    if not request.user.is_platform_admin:
        return _deny_and_logout(request)

    today = timezone.localdate()
    today_start, today_end = _local_day_bounds(today)
    employee_qs = _employee_queryset_for_dashboard()

    present_user_ids = list(
        Pointage.objects.filter(
            utilisateur__in=employee_qs,
            horodatage__gte=today_start,
            horodatage__lt=today_end,
            statut='VALIDE',
        )
        .values_list('utilisateur_id', flat=True)
        .distinct()
    )

    present_users = (
        employee_qs.filter(pk__in=present_user_ids)
        .annotate(
            first_arrival=Min(
                'pointages__horodatage',
                filter=Q(
                    pointages__horodatage__gte=today_start,
                    pointages__horodatage__lt=today_end,
                    pointages__statut='VALIDE',
                    pointages__type='ENTREE',
                ),
            )
        )
        .order_by('first_name', 'last_name', 'username')
    )

    context = {
        'target_day': today,
        'present_users': present_users,
    }
    return render(request, 'dashboard/presents_today.html', context)


@login_required(login_url='login')
def today_absent_list(request):
    if get_active_space(request) == EMPLOYEE_SPACE:
        return redirect('dashboard:employee_home')

    if not request.user.is_platform_admin:
        return _deny_and_logout(request)

    today = timezone.localdate()
    today_start, today_end = _local_day_bounds(today)
    employee_qs = _employee_queryset_for_dashboard()
    settings_obj = get_schedule_settings()
    holiday_map = get_belgian_holidays(today, today)

    present_user_ids = set(
        Pointage.objects.filter(
            utilisateur__in=employee_qs,
            horodatage__gte=today_start,
            horodatage__lt=today_end,
            statut='VALIDE',
        )
        .values_list('utilisateur_id', flat=True)
        .distinct()
    )

    absentees = employee_qs.exclude(pk__in=present_user_ids).order_by('first_name', 'last_name', 'username')

    absents_non_attendus = []
    absents_non_justifies = []
    for utilisateur in absentees:
        analysis = analyze_day(utilisateur, today, settings_obj=settings_obj, holiday_map=holiday_map)
        row = {
            'utilisateur': utilisateur,
            'label': _user_label(utilisateur),
            'raison': _absence_reason(utilisateur, analysis, today),
        }
        if analysis['required_presence']:
            absents_non_justifies.append(row)
        else:
            absents_non_attendus.append(row)

    context = {
        'target_day': today,
        'absents_non_attendus': absents_non_attendus,
        'absents_non_justifies': absents_non_justifies,
        'total_absents': len(absents_non_attendus) + len(absents_non_justifies),
    }
    return render(request, 'dashboard/absents_today.html', context)


@login_required(login_url='login')
def today_punctuality_list(request, metric):
    if get_active_space(request) == EMPLOYEE_SPACE:
        return redirect('dashboard:employee_home')

    if not request.user.is_platform_admin:
        return _deny_and_logout(request)

    meta = {
        'late': {
            'title': 'Retards du jour',
            'value_label': 'Heure arrivée',
        },
        'early': {
            'title': 'Départs anticipés du jour',
            'value_label': 'Heure sortie',
        },
        'short': {
            'title': 'Journées trop courtes du jour',
            'value_label': 'Temps effectif',
        },
    }
    if metric not in meta:
        return redirect('dashboard:index')

    today = timezone.localdate()
    rows = _collect_punctuality_rows(metric, today)

    context = {
        'target_day': today,
        'rows': rows,
        'metric': metric,
        'metric_title': meta[metric]['title'],
        'value_label': meta[metric]['value_label'],
    }
    return render(request, 'dashboard/punctuality_today.html', context)

@login_required(login_url='login')
def employee_home(request):
    if get_active_space(request) == ADMIN_SPACE: return redirect('dashboard:index')
    if not user_can_access_employee_space(request.user): return _deny_and_logout(request)

    pointages_qs = Pointage.objects.filter(utilisateur=request.user)
    work_stats = summarize_work_time(pointages_qs)
    recent_pointages = attach_schedule_display(list(pointages_qs.order_by('-horodatage')[:8]))
    today = timezone.localdate()
    month_start = today.replace(day=1)
    punctuality_counts = {'late': 0, 'early_departure': 0, 'short_day': 0}
    settings_obj = get_schedule_settings()
    holiday_map = get_belgian_holidays(month_start, today)

    # Données pour le graphique des heures travaillées cette semaine
    week_start = today - timedelta(days=today.weekday())  # Lundi de cette semaine
    weekly_hours = []
    weekly_labels = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_start = timezone.make_aware(datetime.combine(day, time.min), timezone.get_current_timezone())
        day_end = day_start + timedelta(days=1)
        day_pointages = pointages_qs.filter(
            horodatage__gte=day_start,
            horodatage__lt=day_end,
            statut='VALIDE'
        ).order_by('horodatage')

        # Calculer la durée travaillée pour ce jour
        total_duration = timedelta()
        current_entry = None

        for pointage in day_pointages:
            if pointage.type == 'ENTREE':
                current_entry = pointage.horodatage
            elif pointage.type == 'SORTIE' and current_entry is not None:
                if pointage.horodatage > current_entry:
                    total_duration += pointage.horodatage - current_entry
                current_entry = None

        hours = total_duration.total_seconds() / 3600
        weekly_hours.append(round(hours, 1))
        weekly_labels.append(day.strftime('%a'))

    # Données pour le graphique des retards sur le mois
    monthly_late_days = []
    monthly_labels = []
    absences_this_month = 0
    for day_offset in range((today - month_start).days + 1):
        day = month_start + timedelta(days=day_offset)
        analysis = analyze_day(request.user, day, settings_obj=settings_obj, holiday_map=holiday_map)
        punctuality_counts['late'] += int(analysis['late'])
        punctuality_counts['early_departure'] += int(analysis['early_departure'])
        punctuality_counts['short_day'] += int(analysis['short_day'])
        if analysis.get('absent'):
            absences_this_month += 1
        if analysis['late']:
            monthly_late_days.append(1)
            monthly_labels.append(day.strftime('%d/%m'))
        else:
            monthly_late_days.append(0)
            monthly_labels.append('')

    alertes_qs = Alerte.objects.filter(
        utilisateur=request.user,
        masquee=False,
        type__in=EMPLOYEE_ALERT_TYPES,
    )
    recent_incidents = alertes_qs.order_by('-date_creation')[:8]

    context = {
        'user': request.user,
        'total_pointages': pointages_qs.count(),
        'pointages_valides': pointages_qs.filter(statut='VALIDE').count(),
        'retards_mois': punctuality_counts['late'],
        'absences_mois': absences_this_month,
        'departs_anticipes_mois': punctuality_counts['early_departure'],
        'journees_courtes_mois': punctuality_counts['short_day'],
        'incidents_securite': alertes_qs.count(),
        'recent_pointages': recent_pointages,
        'recent_incidents': recent_incidents,
        'worked_time_today': work_stats['today_duration_display'],
        'worked_time_week': work_stats['week_duration_display'],
        'completed_work_sessions': work_stats['today_sessions'],
        'completed_work_sessions_today': work_stats['today_sessions'],
        'weekly_hours': weekly_hours,
        'weekly_labels': weekly_labels,
        'monthly_late_days': monthly_late_days,
        'monthly_labels': monthly_labels,
    }

    return render(request, 'dashboard/employee_home.html', context)

@login_required(login_url='login')
def employee_pointages(request):

    if get_active_space(request) == ADMIN_SPACE: return redirect('dashboard:index')

    if not user_can_access_employee_space(request.user): return _deny_and_logout(request)

    type_filtre = request.GET.get('type', '').strip()

    pointages = Pointage.objects.filter(utilisateur=request.user)

    if type_filtre: pointages = pointages.filter(type=type_filtre)

    ordered_pointages = attach_schedule_display(list(pointages.order_by('-horodatage')))

    context = {
        'pointages': ordered_pointages,
        'type_filtre': type_filtre,
        'choix_type': Pointage.TYPE_CHOICES,
    }

    return render(request, 'dashboard/employee_pointages.html', context)

@login_required(login_url='login')
def employee_prestations(request):

    if get_active_space(request) == ADMIN_SPACE: return redirect('dashboard:index')

    if not user_can_access_employee_space(request.user): return _deny_and_logout(request)

    work_stats = summarize_work_time(Pointage.objects.filter(utilisateur=request.user))
    history = work_stats['daily_breakdown'][:31]
    chart_data = {
        'labels': [item['label'] for item in reversed(history)],
        'data': [round(item['duration'].total_seconds() / 3600, 2) for item in reversed(history)],
    }

    context = {
        'worked_time_today': work_stats['today_duration_display'],
        'worked_time_week': work_stats['week_duration_display'],
        'completed_work_sessions': work_stats['today_sessions'],
        'completed_work_sessions_today': work_stats['today_sessions'],
        'daily_work_history': history,
        'work_hours_chart_data': chart_data,
        'work_hours_chart_json': chart_data,
    }

    return render(request, 'dashboard/employee_prestations.html', context)

@login_required(login_url='login')
def employee_work_hours_csv(request):

    if get_active_space(request) == ADMIN_SPACE: return redirect('dashboard:index')

    if not user_can_access_employee_space(request.user): return _deny_and_logout(request)

    work_stats = summarize_work_time(Pointage.objects.filter(utilisateur=request.user))

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="heures_prestées.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['Date', 'Première entrée', 'Dernière sortie', 'Sessions', 'Temps travaillé'])

    for day in work_stats['daily_breakdown']:
        writer.writerow([
            day['label'],
            day['first_entry_display'],
            day['last_exit_display'],
            day['sessions'],
            day['duration_display'],
        ])

    return response

@login_required(login_url='login')
def employee_alertes(request):

    if get_active_space(request) == ADMIN_SPACE: return redirect('dashboard:index')

    if not user_can_access_employee_space(request.user): return _deny_and_logout(request)

    statut_filtre = request.GET.get('statut', '').strip()
    date_debut_raw = request.GET.get('date_debut', '').strip()
    date_fin_raw = request.GET.get('date_fin', '').strip()
    date_debut = _safe_parse_date(date_debut_raw)
    date_fin = _safe_parse_date(date_fin_raw)

    alertes = Alerte.objects.filter(
        utilisateur=request.user,
        masquee=False,
        type__in=EMPLOYEE_ALERT_TYPES,
    )
    if statut_filtre:
        alertes = alertes.filter(type=statut_filtre)
    if date_debut:
        alertes = alertes.filter(date_creation__date__gte=date_debut)
    if date_fin:
        alertes = alertes.filter(date_creation__date__lte=date_fin)

    type_labels = dict(Alerte.TYPE_CHOICES)
    alertes = alertes.order_by('-date_creation')

    resume_total = alertes.count()
    resume_schedule_total = alertes.filter(type__in=['ABSENCE', 'RETARD', 'DEPART_ANTICIPE', 'JOURNEE_COURTE', 'DOUBLE_POINTAGE']).count()
    resume_schedule_absence = alertes.filter(type='ABSENCE').count()
    resume_schedule_retard = alertes.filter(type='RETARD').count()
    resume_schedule_depart_anticipe = alertes.filter(type='DEPART_ANTICIPE').count()
    resume_schedule_journee_courte = alertes.filter(type='JOURNEE_COURTE').count()
    resume_schedule_double_pointage = alertes.filter(type='DOUBLE_POINTAGE').count()
    resume_planning_total = alertes.filter(type='DEMANDE_PLANNING').count()

    context = {
        'alertes': alertes,
        'statut_filtre': statut_filtre,
        'date_debut': date_debut_raw,
        'date_fin': date_fin_raw,
        'choix_statut': [
            (alert_type, type_labels.get(alert_type, alert_type))
            for alert_type in EMPLOYEE_ALERT_TYPES
        ],        'schedule_types': ['ABSENCE', 'RETARD', 'DEPART_ANTICIPE', 'JOURNEE_COURTE', 'DOUBLE_POINTAGE'],        'resume_total': resume_total,
        'resume_schedule_total': resume_schedule_total,
        'resume_schedule_absence': resume_schedule_absence,
        'resume_schedule_retard': resume_schedule_retard,
        'resume_schedule_depart_anticipe': resume_schedule_depart_anticipe,
        'resume_schedule_journee_courte': resume_schedule_journee_courte,
        'resume_schedule_double_pointage': resume_schedule_double_pointage,
        'resume_planning_total': resume_planning_total,
    }

    return render(request, 'dashboard/employee_alertes.html', context)

def logout_view(request):
    logout(request)
    return redirect('login')  

@login_required(login_url='login')
def switch_space(request, space):
    chosen_space = set_active_space(request, space)
    if chosen_space != space: messages.error(request, "Cet espace n'est pas disponible pour votre compte.")
    return _redirect_to_active_space(request)
