from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from accounts.models import Utilisateur
from alerts.models import Alerte
from attendance.models import Pointage
from attendance.utils import format_duration

from .models import ScheduleRequest, ScheduleSettings

try:
    import holidays
except ImportError:  # pragma: no cover - optional dependency fallback
    holidays = None

ABSENCE_CATEGORIES = {
    ScheduleRequest.CATEGORY_CONGE,
    ScheduleRequest.CATEGORY_MALADIE,
    ScheduleRequest.CATEGORY_AUTRE,
}


def get_schedule_settings() -> ScheduleSettings:
    return ScheduleSettings.get_solo()


def schedule_features_enabled() -> bool:
    return get_schedule_settings().is_enabled


def get_employee_queryset():
    return (
        Utilisateur.objects.filter(is_superuser=False)
        .exclude(roles__nom__iexact='admin')
        .exclude(roles__nom__iexact='acces_total')
        .distinct()
        .order_by('first_name', 'last_name', 'username')
    )


def get_user_label(utilisateur: Utilisateur) -> str:
    return utilisateur.get_full_name() or utilisateur.username


def month_bounds(reference_day: date) -> tuple[date, date]:
    start = reference_day.replace(day=1)
    last_day = calendar.monthrange(reference_day.year, reference_day.month)[1]
    return start, reference_day.replace(day=last_day)


def iter_days(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def get_belgian_holidays(start_date: date, end_date: date) -> dict[date, str]:
    if holidays is None:
        return {}

    years = range(start_date.year, end_date.year + 1)
    try:
        holiday_source = holidays.country_holidays('BE', years=years)
    except Exception:
        return {}

    return {
        holiday_day: str(name)
        for holiday_day, name in holiday_source.items()
        if start_date <= holiday_day <= end_date
    }


def _local_time(value):
    if value is None:
        return None
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return value


def _worked_duration(pointages):
    open_entry = None
    total = timedelta()

    for pointage in pointages:
        if pointage.type == 'ENTREE':
            if open_entry is None:
                open_entry = pointage.horodatage
            continue

        if pointage.type == 'SORTIE' and open_entry is not None and pointage.horodatage > open_entry:
            total += pointage.horodatage - open_entry
            open_entry = None

    return total


def analyze_day(utilisateur: Utilisateur, target_day: date, settings_obj: ScheduleSettings | None = None, holiday_map=None):
    settings_obj = settings_obj or get_schedule_settings()
    holiday_map = holiday_map or get_belgian_holidays(target_day, target_day)

    approved_requests = list(
        ScheduleRequest.objects.filter(
            utilisateur=utilisateur,
            status=ScheduleRequest.STATUS_APPROVED,
            start_at__date__lte=target_day,
            end_at__date__gte=target_day,
        ).order_by('start_at')
    )

    absence_requests = [item for item in approved_requests if item.category in ABSENCE_CATEGORIES]
    delay_requests = [item for item in approved_requests if item.category == ScheduleRequest.CATEGORY_RETARD]

    pointages = list(
        Pointage.objects.filter(
            utilisateur=utilisateur,
            statut='VALIDE',
            horodatage__date=target_day,
        ).order_by('horodatage')
    )

    first_entry = next((item.horodatage for item in pointages if item.type == 'ENTREE'), None)
    exits = [item.horodatage for item in pointages if item.type == 'SORTIE']
    last_exit = exits[-1] if exits else None
    worked_duration = _worked_duration(pointages)
    has_effective_work = worked_duration.total_seconds() > 0

    required_presence = True
    if target_day.weekday() >= 5:
        required_presence = False
    if utilisateur.date_debut and target_day < utilisateur.date_debut:
        required_presence = False
    if utilisateur.date_fin and target_day > utilisateur.date_fin:
        required_presence = False
    if target_day in holiday_map:
        required_presence = False
    if absence_requests:
        required_presence = False

    local_now = timezone.localtime(timezone.now())
    should_check_absence = target_day < local_now.date() or (
        target_day == local_now.date() and local_now.time() >= settings_obj.departure_window_end
    )

    absent = required_presence and should_check_absence and (not pointages or not has_effective_work)

    late = False
    if first_entry is not None and has_effective_work and not absent:
        late = _local_time(first_entry).time() > settings_obj.arrival_window_end and not delay_requests

    early_departure = False
    if last_exit is not None and has_effective_work and not absent:
        early_departure = _local_time(last_exit).time() < settings_obj.departure_window_start and not absence_requests

    required_duration = timedelta(minutes=settings_obj.required_daily_minutes)
    short_day = has_effective_work and worked_duration < required_duration and not absence_requests and not absent

    return {
        'day': target_day,
        'holiday_name': holiday_map.get(target_day, ''),
        'approved_requests': approved_requests,
        'absence_requests': absence_requests,
        'delay_requests': delay_requests,
        'required_presence': required_presence,
        'pointages': pointages,
        'first_entry': first_entry,
        'last_exit': last_exit,
        'worked_duration': worked_duration,
        'worked_duration_display': format_duration(worked_duration),
        'late': late,
        'early_departure': early_departure,
        'short_day': short_day,
        'absent': absent,
    }


def _create_schedule_alert(utilisateur: Utilisateur, alert_type: str, description: str):
    _, created = Alerte.objects.get_or_create(
        utilisateur=utilisateur,
        type=alert_type,
        description=description,
        defaults={'statut': 'NOUVELLE'},
    )
    return created


def sync_schedule_alerts(start_date: date | None = None, end_date: date | None = None, users=None):
    settings_obj = get_schedule_settings()
    if not settings_obj.is_enabled:
        return {'absences': 0, 'retards': 0, 'early_departures': 0, 'short_days': 0}

    today = timezone.localdate()
    start_date = start_date or (today - timedelta(days=2))
    end_date = end_date or today

    queryset = users if users is not None else get_employee_queryset()
    if hasattr(queryset, 'all'):
        queryset = queryset.all()

    holiday_map = get_belgian_holidays(start_date, end_date)
    created_counts = {'absences': 0, 'retards': 0, 'early_departures': 0, 'short_days': 0}

    for utilisateur in queryset:
        for current_day in iter_days(start_date, end_date):
            analysis = analyze_day(utilisateur, current_day, settings_obj=settings_obj, holiday_map=holiday_map)

            if analysis['absent']:
                description = f"Absence détectée le {current_day.strftime('%d/%m/%Y')}."
                created_counts['absences'] += int(_create_schedule_alert(utilisateur, 'ABSENCE', description))

            if analysis['late'] and analysis['first_entry'] is not None:
                entry_display = _local_time(analysis['first_entry']).strftime('%H:%M')
                description = f"Retard détecté le {current_day.strftime('%d/%m/%Y')} : arrivée à {entry_display}."
                created_counts['retards'] += int(_create_schedule_alert(utilisateur, 'RETARD', description))

            if analysis['early_departure'] and analysis['last_exit'] is not None:
                exit_display = _local_time(analysis['last_exit']).strftime('%H:%M')
                description = f"Départ anticipé détecté le {current_day.strftime('%d/%m/%Y')} : sortie à {exit_display}."
                created_counts['early_departures'] += int(_create_schedule_alert(utilisateur, 'DEPART_ANTICIPE', description))

            if analysis['short_day']:
                description = (
                    f"Journée trop courte le {current_day.strftime('%d/%m/%Y')} : "
                    f"{analysis['worked_duration_display']} prestées."
                )
                created_counts['short_days'] += int(_create_schedule_alert(utilisateur, 'JOURNEE_COURTE', description))

    return created_counts


def build_pointage_feedback(pointage: Pointage):
    utilisateur = getattr(pointage, 'utilisateur', None)
    if utilisateur is None:
        return {'flags': [], 'messages': [], 'worked_duration_display': '0h00'}

    settings_obj = get_schedule_settings()
    if not settings_obj.is_enabled:
        return {'flags': [], 'messages': [], 'worked_duration_display': '0h00'}

    target_day = _local_time(pointage.horodatage).date()
    sync_schedule_alerts(start_date=target_day, end_date=target_day, users=[utilisateur])
    analysis = analyze_day(utilisateur, target_day, settings_obj=settings_obj)

    flags = []
    messages = []

    if pointage.type == 'ENTREE' and analysis['late']:
        flags.append('RETARD')
        messages.append(
            f"Retard détecté : arrivée à {_local_time(analysis['first_entry']).strftime('%H:%M')} "
            f"(après {settings_obj.arrival_window_end.strftime('%H:%M')})."
        )

    if pointage.type == 'SORTIE' and analysis['early_departure']:
        flags.append('DEPART_ANTICIPE')
        messages.append(
            f"Départ anticipé : sortie à {_local_time(analysis['last_exit']).strftime('%H:%M')} "
            f"(avant {settings_obj.departure_window_start.strftime('%H:%M')})."
        )

    if pointage.type == 'SORTIE' and analysis['short_day']:
        flags.append('JOURNEE_COURTE')
        messages.append(f"Journée trop courte : {analysis['worked_duration_display']} au lieu de 8h00.")

    details = pointage.details if isinstance(pointage.details, dict) else {}
    details['schedule_flags'] = flags
    details['schedule_feedback'] = messages
    details['worked_duration_display'] = analysis['worked_duration_display']
    pointage.details = details
    pointage.save(update_fields=['details'])

    return {
        'flags': flags,
        'messages': messages,
        'worked_duration_display': analysis['worked_duration_display'],
    }
