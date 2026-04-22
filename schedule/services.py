from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta

import requests
from django.conf import settings
from django.utils import timezone

from accounts.models import Utilisateur
from alerts.models import Alerte
from attendance.models import Pointage
from attendance.utils import format_duration

from .models import ScheduleRequest, ScheduleSettings

try:
    import holidays
except ImportError:  
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


def get_rh_recipient_emails() -> list[str]:
    return list(
        Utilisateur.objects.filter(
            roles__nom__in=['admin', 'acces_total'],
        )
        .exclude(email__isnull=True)
        .exclude(email__exact='')
        .distinct()
        .values_list('email', flat=True)
    )


def _send_email_via_brevo(subject: str, html_content: str, to_emails: list[str], cc_emails: list[str] | None = None) -> bool:
    if not settings.BREVO_API_KEY or not to_emails:
        return False

    payload = {
        'sender': {
            'name': settings.BREVO_SENDER_NAME,
            'email': settings.BREVO_SENDER_EMAIL,
        },
        'to': [{'email': email} for email in to_emails],
        'subject': subject,
        'htmlContent': html_content,
        'textContent': html_content,
    }

    if cc_emails:
        payload['cc'] = [{'email': email} for email in cc_emails if email]

    try:
        response = requests.post(
            settings.BREVO_API_ENDPOINT,
            json=payload,
            headers={
                'accept': 'application/json',
                'api-key': settings.BREVO_API_KEY,
            },
            timeout=15,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False


def _send_absence_notification(utilisateur: Utilisateur, target_day: date, description: str) -> bool:
    rh_emails = get_rh_recipient_emails()
    if not rh_emails:
        return False

    subject = f"Alerte absence BioAttend – {target_day.strftime('%d/%m/%Y')}"
    html_content = (
        f"<p>Une absence a été détectée pour <strong>{utilisateur.get_full_name() or utilisateur.username}</strong> "
        f"le {target_day.strftime('%d/%m/%Y')}.</p>"
        f"<p>{description}</p>"
        "<p>Merci de vérifier le planning et de prendre les actions nécessaires.</p>"
    )

    return _send_email_via_brevo(subject, html_content, rh_emails)


def _send_late_notification(utilisateur: Utilisateur, target_day: date, entry_display: str, description: str) -> bool:
    rh_emails = get_rh_recipient_emails()
    if not rh_emails:
        return False

    cc_emails = [utilisateur.email] if utilisateur.email else []
    subject = f"Alerte retard BioAttend – {target_day.strftime('%d/%m/%Y')}"
    html_content = (
        f"<p>Un retard a été détecté pour <strong>{utilisateur.get_full_name() or utilisateur.username}</strong> "
        f"le {target_day.strftime('%d/%m/%Y')}.</p>"
        f"<p>Arrivée enregistrée à {entry_display}.</p>"
        f"<p>{description}</p>"
        "<p>Merci de valider la présence et d'informer l'intéressé si nécessaire.</p>"
    )

    return _send_email_via_brevo(subject, html_content, rh_emails, cc_emails=cc_emails)


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


def _local_day_bounds(target_day: date):
    tz = timezone.get_current_timezone()
    start_local = timezone.make_aware(datetime.combine(target_day, time.min), tz)
    end_local = start_local + timedelta(days=1)
    return start_local, end_local


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


def _time_delta_between(target_day: date, actual_time: time, expected_time: time) -> timedelta:
    actual_dt = datetime.combine(target_day, actual_time)
    expected_dt = datetime.combine(target_day, expected_time)
    return actual_dt - expected_dt


def analyze_day(utilisateur: Utilisateur, target_day: date, settings_obj: ScheduleSettings | None = None, holiday_map=None):
    settings_obj = settings_obj or get_schedule_settings()
    holiday_map = holiday_map or get_belgian_holidays(target_day, target_day)
    day_start, day_end = _local_day_bounds(target_day)

    approved_requests = list(
        ScheduleRequest.objects.filter(
            utilisateur=utilisateur,
            status=ScheduleRequest.STATUS_APPROVED,
            start_at__lt=day_end,
            end_at__gte=day_start,
        ).order_by('start_at')
    )

    absence_requests = [item for item in approved_requests if item.category in ABSENCE_CATEGORIES]
    delay_requests = [item for item in approved_requests if item.category == ScheduleRequest.CATEGORY_RETARD]

    pointages = list(
        Pointage.objects.filter(
            utilisateur=utilisateur,
            statut='VALIDE',
            horodatage__gte=day_start,
            horodatage__lt=day_end,
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
    if first_entry is not None and not absent:
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


def _create_schedule_alert(utilisateur: Utilisateur, alert_type: str, description: str, target_day: date):
    day_token = target_day.strftime('%d/%m/%Y')
    existing = Alerte.objects.filter(
        utilisateur=utilisateur,
        type=alert_type,
        description__contains=day_token,
    ).first()

    if existing is not None:
        if existing.description != description:
            existing.description = description
            existing.save(update_fields=['description'])
        return False

    Alerte.objects.create(
        utilisateur=utilisateur,
        type=alert_type,
        description=description,
    )
    return True


def _should_send_absence_notification_for_day(target_day: date, settings_obj: ScheduleSettings | None = None) -> bool:
    settings_obj = settings_obj or get_schedule_settings()
    local_now = timezone.localtime(timezone.now())
    return target_day < local_now.date() or (
        target_day == local_now.date() and local_now.time() >= settings_obj.departure_window_end
    )


def trigger_absence_alert(utilisateur: Utilisateur, target_day: date) -> dict:
    settings_obj = get_schedule_settings()
    holiday_map = get_belgian_holidays(target_day, target_day)
    analysis = analyze_day(utilisateur, target_day, settings_obj=settings_obj, holiday_map=holiday_map)
    result = {
        'absent': analysis['absent'],
        'alert_created': False,
        'email_sent': False,
        'description': '',
        'reason': '',
    }

    if not analysis['absent']:
        result['reason'] = 'Aucune absence détectée pour cette date ou la journée n est pas encore terminee.'
        return result

    description = f"Absence detectee pour {get_user_label(utilisateur)} le {target_day.strftime('%d/%m/%Y')}."
    created = _create_schedule_alert(utilisateur, 'ABSENCE', description, target_day)
    result['alert_created'] = created
    result['description'] = description

    if created and _should_send_absence_notification_for_day(target_day, settings_obj=settings_obj):
        result['email_sent'] = _send_absence_notification(utilisateur, target_day, description)

    return result


def trigger_absence_alerts_for_day(target_day: date | None = None, users=None) -> dict:
    target_day = target_day or timezone.localdate()
    queryset = users if users is not None else get_employee_queryset()
    if hasattr(queryset, 'all'):
        queryset = queryset.all()

    absences = []
    for utilisateur in queryset:
        result = trigger_absence_alert(utilisateur, target_day)
        if result['absent']:
            absences.append({
                'user_id': str(utilisateur.id),
                'username': utilisateur.username,
                'full_name': utilisateur.get_full_name(),
                'alert_created': result['alert_created'],
                'email_sent': result['email_sent'],
                'description': result['description'],
                'reason': result.get('reason', ''),
            })

    return {
        'date': target_day,
        'checked': queryset.count() if hasattr(queryset, 'count') else len(list(queryset)),
        'absences': absences,
    }


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
        employee_label = get_user_label(utilisateur)
        for current_day in iter_days(start_date, end_date):
            analysis = analyze_day(utilisateur, current_day, settings_obj=settings_obj, holiday_map=holiday_map)

            if analysis['absent']:
                description = f"Absence détectée pour {employee_label} le {current_day.strftime('%d/%m/%Y')}."
                created = _create_schedule_alert(utilisateur, 'ABSENCE', description, current_day)
                created_counts['absences'] += int(created)
                if created and current_day == today:
                    _send_absence_notification(utilisateur, current_day, description)

            if analysis['late'] and analysis['first_entry'] is not None:
                entry_display = _local_time(analysis['first_entry']).strftime('%H:%M')
                description = (
                    f"Retard détecté pour {employee_label} le {current_day.strftime('%d/%m/%Y')} : "
                    f"arrivée à {entry_display}."
                )
                created = _create_schedule_alert(utilisateur, 'RETARD', description, current_day)
                created_counts['retards'] += int(created)
                if created and current_day == today:
                    _send_late_notification(utilisateur, current_day, entry_display, description)

            if analysis['early_departure'] and analysis['last_exit'] is not None:
                exit_display = _local_time(analysis['last_exit']).strftime('%H:%M')
                description = f"Départ anticipé détecté le {current_day.strftime('%d/%m/%Y')} : sortie à {exit_display}."
                created_counts['early_departures'] += int(_create_schedule_alert(utilisateur, 'DEPART_ANTICIPE', description, current_day))

            if analysis['short_day']:
                description = (
                    f"Journée trop courte pour {employee_label} le {current_day.strftime('%d/%m/%Y')} : "
                    f"{analysis['worked_duration_display']} prestées."
                )
                created_counts['short_days'] += int(_create_schedule_alert(utilisateur, 'JOURNEE_COURTE', description, current_day))

    return created_counts


def get_pointage_display_context(pointage: Pointage, *, persist: bool = False):
    utilisateur = getattr(pointage, 'utilisateur', None)
    details = pointage.details if isinstance(pointage.details, dict) else {}

    fallback_payload = {
        'flags': list(details.get('schedule_flags', [])),
        'messages': list(details.get('schedule_feedback', [])),
        'worked_duration_display': details.get('worked_duration_display', '0h00'),
    }

    if utilisateur is None:
        return fallback_payload

    settings_obj = get_schedule_settings()
    if not settings_obj.is_enabled:
        return fallback_payload

    target_day = _local_time(pointage.horodatage).date()
    if persist:
        sync_schedule_alerts(start_date=target_day, end_date=target_day, users=[utilisateur])

    analysis = analyze_day(utilisateur, target_day, settings_obj=settings_obj)

    flags = []
    messages = []
    required_duration = timedelta(minutes=settings_obj.required_daily_minutes)
    required_duration_display = format_duration(required_duration)
    pointage_local_time = _local_time(pointage.horodatage)

    if pointage.type == 'ENTREE' and analysis['late']:
        entry_time = pointage_local_time.time()
        late_duration = _time_delta_between(target_day, entry_time, settings_obj.arrival_window_end)
        late_duration_display = format_duration(late_duration)
        flags.append('RETARD')
        messages.append(
            f"Retard de {late_duration_display} "
            f"(arrivée à {entry_time.strftime('%H:%M')} au lieu de {settings_obj.arrival_window_end.strftime('%H:%M')})."
        )

    if pointage.type == 'SORTIE' and analysis['early_departure']:
        exit_time = pointage_local_time.time()
        early_duration = _time_delta_between(target_day, settings_obj.departure_window_start, exit_time)
        early_duration_display = format_duration(early_duration)
        flags.append('DEPART_ANTICIPE')
        messages.append(
            f"Départ anticipé de {early_duration_display} "
            f"(sortie à {exit_time.strftime('%H:%M')} au lieu de {settings_obj.departure_window_start.strftime('%H:%M')})."
        )

    if pointage.type == 'SORTIE' and analysis['short_day']:
        missing_duration = required_duration - analysis['worked_duration']
        missing_duration_display = format_duration(missing_duration)
        flags.append('JOURNEE_COURTE')
        messages.append(
            f"Travail effectif réduit de {missing_duration_display} "
            f"({analysis['worked_duration_display']} au lieu de {required_duration_display})."
        )

    payload = {
        'flags': flags,
        'messages': messages,
        'worked_duration_display': analysis['worked_duration_display'],
    }

    if persist:
        details['schedule_flags'] = payload['flags']
        details['schedule_feedback'] = payload['messages']
        details['worked_duration_display'] = payload['worked_duration_display']
        pointage.details = details
        pointage.save(update_fields=['details'])

    return payload


def attach_schedule_display(pointages, *, persist: bool = False):
    enriched = []
    for pointage in pointages:
        payload = get_pointage_display_context(pointage, persist=persist)
        pointage.schedule_flags = payload.get('flags', [])
        pointage.schedule_feedback = payload.get('messages', [])
        pointage.schedule_feedback_display = ' · '.join(pointage.schedule_feedback) if pointage.schedule_feedback else 'RAS'
        pointage.worked_duration_display = payload.get('worked_duration_display', '0h00')
        enriched.append(pointage)
    return enriched


def build_pointage_feedback(pointage: Pointage):
    return get_pointage_display_context(pointage, persist=True)
