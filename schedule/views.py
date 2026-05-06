import calendar
import csv
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.access import ADMIN_SPACE, EMPLOYEE_SPACE, get_active_space, user_can_access_employee_space

from alerts.models import Alerte

from .forms import ScheduleRequestForm, ScheduleSettingsForm
from .models import ScheduleRequest
from .services import (
    ABSENCE_CATEGORIES,
    get_belgian_holidays,
    get_employee_queryset,
    get_schedule_settings,
    get_user_label,
    iter_days,
    month_bounds,
    schedule_features_enabled,
    sync_schedule_alerts,
)


def _deny_and_logout(request):
    messages.error(request, "Accès refusé : votre compte n'a pas les droits nécessaires.")
    return redirect('login')


def _is_admin_view(request):
    return get_active_space(request) != EMPLOYEE_SPACE and request.user.is_platform_admin


def _sync_recent_schedule_alerts_once(request, admin_view):
    if not schedule_features_enabled():
        return

    today = timezone.localdate()
    user_token = 'admin' if admin_view else str(request.user.pk)
    cache_key = f"schedule-alert-sync:{user_token}:{today.isoformat()}"
    if cache.get(cache_key):
        return

    sync_schedule_alerts(
        users=None if admin_view else [request.user],
    )
    cache.set(cache_key, True, 15 * 60)


def _parse_month(raw_value):
    if raw_value:
        try:
            return datetime.strptime(raw_value, '%Y-%m').date().replace(day=1)
        except ValueError:
            pass
    return timezone.localdate().replace(day=1)


def _build_day_event_map(entries, month_start, month_end, is_admin_view=False):
    day_events = {}
    for current_day in iter_days(month_start, month_end):
        day_events[current_day] = []

    for entry in entries:
        start_day = max(month_start, timezone.localtime(entry.start_at).date() if timezone.is_aware(entry.start_at) else entry.start_at.date())
        end_day = min(month_end, timezone.localtime(entry.end_at).date() if timezone.is_aware(entry.end_at) else entry.end_at.date())
        css_class = 'event-absence'
        if entry.category == ScheduleRequest.CATEGORY_CONGE:
            css_class = 'event-conge'
        elif entry.category == ScheduleRequest.CATEGORY_RETARD:
            css_class = 'event-retard'

        for current_day in iter_days(start_day, end_day):
            if current_day not in day_events:
                continue
            label = entry.get_category_display()
            if is_admin_view:
                label = f"{get_user_label(entry.utilisateur)} · {label}"
            day_events[current_day].append({'label': label, 'class': css_class})

    return day_events


def _build_calendar_weeks(month_start, day_events, holiday_map):
    weeks = []
    month_matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(month_start.year, month_start.month)

    for week in month_matrix:
        row = []
        for current_day in week:
            row.append(
                {
                    'date': current_day,
                    'is_current_month': current_day.month == month_start.month,
                    'is_today': current_day == timezone.localdate(),
                    'events': day_events.get(current_day, []),
                    'holiday_name': holiday_map.get(current_day, ''),
                }
            )
        weeks.append(row)

    return weeks


@login_required(login_url='login')
def schedule_home(request):
    if not (_is_admin_view(request) or user_can_access_employee_space(request.user)):
        return _deny_and_logout(request)

    admin_view = _is_admin_view(request)
    selected_month = _parse_month(request.GET.get('month', ''))
    month_start, month_end = month_bounds(selected_month)
    settings_obj = get_schedule_settings()

    _sync_recent_schedule_alerts_once(request, admin_view)

    visible_entries = ScheduleRequest.objects.select_related('utilisateur', 'created_by', 'reviewed_by').filter(
        status=ScheduleRequest.STATUS_APPROVED,
        start_at__date__lte=month_end,
        end_at__date__gte=month_start,
    )
    if admin_view:
        visible_entries = visible_entries.exclude(category=ScheduleRequest.CATEGORY_RETARD)
    else:
        visible_entries = visible_entries.filter(utilisateur=request.user, category__in=ABSENCE_CATEGORIES)

    holiday_map = get_belgian_holidays(month_start, month_end)
    day_events = _build_day_event_map(visible_entries, month_start, month_end, is_admin_view=admin_view)

    for holiday_day, holiday_name in holiday_map.items():
        if holiday_day in day_events:
            day_events[holiday_day].append({'label': holiday_name, 'class': 'event-holiday'})

    calendar_weeks = _build_calendar_weeks(month_start, day_events, holiday_map)

    form_initial = {
        'start_at': timezone.localtime(timezone.now()).replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M'),
        'end_at': (timezone.localtime(timezone.now()) + timedelta(hours=8)).replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M'),
    }
    if not admin_view:
        form_initial['utilisateur'] = request.user.pk

    form = ScheduleRequestForm(actor=request.user, is_admin=admin_view, initial=form_initial)

    pending_requests = ScheduleRequest.objects.select_related('utilisateur', 'created_by').filter(status=ScheduleRequest.STATUS_PENDING)
    recent_requests = ScheduleRequest.objects.select_related('utilisateur', 'reviewed_by').all()

    if admin_view:
        pending_requests = list(pending_requests.order_by('start_at', 'created_at')[:25])
        recent_requests = list(recent_requests.order_by('-created_at')[:40])
    else:
        pending_requests = list(pending_requests.filter(utilisateur=request.user).order_by('start_at', 'created_at')[:25])
        recent_requests = list(recent_requests.filter(utilisateur=request.user).order_by('-created_at')[:40])

    previous_month = (month_start - timedelta(days=1)).replace(day=1)
    next_month = (month_end + timedelta(days=1)).replace(day=1)

    context = {
        'schedule_form': form,
        'settings_form': ScheduleSettingsForm(instance=settings_obj) if request.user.is_platform_admin else None,
        'calendar_weeks': calendar_weeks,
        'month_label': month_start.strftime('%B %Y').capitalize(),
        'month_param': month_start.strftime('%Y-%m'),
        'previous_month': previous_month.strftime('%Y-%m'),
        'next_month': next_month.strftime('%Y-%m'),
        'pending_requests': pending_requests,
        'recent_requests': recent_requests,
        'admin_view': admin_view,
        'settings_obj': settings_obj,
        'features_enabled': settings_obj.is_enabled,
        'pending_count': len(pending_requests),
        'approved_absence_count': visible_entries.count(),
        'holiday_count': len(holiday_map),
    }
    return render(request, 'schedule/index.html', context)


@login_required(login_url='login')
def submit_request(request):
    if request.method != 'POST':
        return redirect('schedule:home')

    admin_view = _is_admin_view(request)
    if not (admin_view or user_can_access_employee_space(request.user)):
        return _deny_and_logout(request)

    settings_obj = get_schedule_settings()
    if not settings_obj.is_enabled:
        messages.warning(request, "Les fonctionnalités d'emploi du temps sont actuellement désactivées.")
        return redirect('schedule:home')

    form = ScheduleRequestForm(request.POST, actor=request.user, is_admin=admin_view)
    if not form.is_valid():
        for _, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)
        return redirect(f"{reverse('schedule:home')}?month={timezone.localdate().strftime('%Y-%m')}")

    entry = form.save(commit=False)
    entry.created_by = request.user
    if admin_view and entry.category == ScheduleRequest.CATEGORY_MALADIE:
        entry.status = ScheduleRequest.STATUS_APPROVED
        entry.reviewed_by = request.user
        entry.reviewed_at = timezone.now()
    else:
        entry.status = ScheduleRequest.STATUS_PENDING if not admin_view else ScheduleRequest.STATUS_APPROVED
        if admin_view:
            entry.reviewed_by = request.user
            entry.reviewed_at = timezone.now()
    entry.save()

    if not admin_view:
        Alerte.objects.create(
            utilisateur=request.user,
            type='DEMANDE_PLANNING',
            description=(
                f"Nouvelle demande {entry.get_category_display().lower()} envoyée du "
                f"{timezone.localtime(entry.start_at).strftime('%d/%m/%Y %H:%M')} au "
                f"{timezone.localtime(entry.end_at).strftime('%d/%m/%Y %H:%M')}."
            ),
        )
        messages.success(request, "Votre demande a bien été envoyée aux RH pour validation.")
    else:
        messages.success(request, "L'entrée planning a bien été enregistrée.")

    return redirect('schedule:home')


@login_required(login_url='login')
def review_request(request, request_id, decision):
    if request.method != 'POST' or not request.user.is_platform_admin:
        return redirect('schedule:home')

    schedule_request = get_object_or_404(ScheduleRequest, pk=request_id)
    schedule_request.reviewed_by = request.user
    schedule_request.reviewed_at = timezone.now()
    schedule_request.status = (
        ScheduleRequest.STATUS_APPROVED if decision == 'approve' else ScheduleRequest.STATUS_REJECTED
    )
    schedule_request.save(update_fields=['reviewed_by', 'reviewed_at', 'status', 'updated_at'])

    Alerte.objects.create(
        utilisateur=schedule_request.utilisateur,
        type='DEMANDE_PLANNING',
        description=(
            f"Votre demande {schedule_request.get_category_display().lower()} a été "
            f"{'approuvée' if decision == 'approve' else 'refusée'}."
        ),
    )
    messages.success(request, "La demande a bien été mise à jour.")
    return redirect('schedule:home')


@login_required(login_url='login')
def export_schedule_csv(request):
    admin_view = _is_admin_view(request)
    if not (admin_view or user_can_access_employee_space(request.user)):
        return _deny_and_logout(request)

    selected_month = _parse_month(request.GET.get('month', ''))
    month_start, month_end = month_bounds(selected_month)

    queryset = ScheduleRequest.objects.select_related('utilisateur').filter(
        status=ScheduleRequest.STATUS_APPROVED,
        start_at__date__lte=month_end,
        end_at__date__gte=month_start,
    )
    if not admin_view:
        queryset = queryset.filter(utilisateur=request.user, category__in=ABSENCE_CATEGORIES)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="emploi_du_temps_{month_start.strftime("%Y_%m")}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Employé', 'Type', 'Statut', 'Début', 'Fin', 'Description'])

    for entry in queryset.order_by('start_at'):
        writer.writerow([
            get_user_label(entry.utilisateur),
            entry.get_category_display(),
            entry.get_status_display(),
            timezone.localtime(entry.start_at).strftime('%d/%m/%Y %H:%M'),
            timezone.localtime(entry.end_at).strftime('%d/%m/%Y %H:%M'),
            entry.description,
        ])

    holiday_map = get_belgian_holidays(month_start, month_end)
    for holiday_day, holiday_name in sorted(holiday_map.items()):
        writer.writerow(['Tous', 'Jour férié', 'Applicable', holiday_day.strftime('%d/%m/%Y'), holiday_day.strftime('%d/%m/%Y'), holiday_name])

    return response


@login_required(login_url='login')
def schedule_settings_view(request):
    if not request.user.is_platform_admin:
        return redirect('schedule:home')

    settings_obj = get_schedule_settings()
    form = ScheduleSettingsForm(request.POST or None, instance=settings_obj)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Les paramètres de retard et de présence ont été mis à jour.")
            return redirect('schedule:home')
        for _, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)

    return render(
        request,
        'schedule/settings.html',
        {
            'settings_form': form,
            'settings_obj': settings_obj,
            'admin_view': True,
            'features_enabled': settings_obj.is_enabled,
        },
    )


@login_required(login_url='login')
def toggle_schedule_features(request):
    if request.method != 'POST' or not request.user.is_platform_admin:
        return redirect('schedule:home')

    settings_obj = get_schedule_settings()
    settings_obj.is_enabled = request.POST.get('is_enabled') == 'on'
    settings_obj.save(update_fields=['is_enabled', 'updated_at'])
    messages.success(
        request,
        "Les fonctionnalités d'emploi du temps sont maintenant activées."
        if settings_obj.is_enabled
        else "Les fonctionnalités d'emploi du temps sont maintenant désactivées.",
    )
    return redirect('schedule:home')
