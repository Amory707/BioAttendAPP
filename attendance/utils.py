from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.utils import timezone

from .models import Pointage


def format_duration(duration: timedelta | None) -> str:
    if not duration:
        return '0h00'

    total_minutes = max(int(duration.total_seconds() // 60), 0)
    hours, minutes = divmod(total_minutes, 60)
    return f'{hours}h{minutes:02d}'


def summarize_work_time(pointages_qs) -> dict[str, Any]:
    valid_pointages = (
        pointages_qs.filter(statut='VALIDE', utilisateur__isnull=False)
        .exclude(horodatage__isnull=True)
        .order_by('utilisateur_id', 'horodatage')
    )

    open_entries = {}
    total_duration = timedelta()
    user_durations = defaultdict(timedelta)
    daily_stats = defaultdict(lambda: {
        'duration': timedelta(),
        'first_entry': None,
        'last_exit': None,
        'sessions': 0,
    })
    completed_sessions = 0

    for pointage in valid_pointages:
        user_id = pointage.utilisateur_id
        if not user_id:
            continue

        current_entry = open_entries.get(user_id)

        if pointage.type == 'ENTREE':
            if current_entry is None:
                open_entries[user_id] = pointage.horodatage
            continue

        if pointage.type == 'SORTIE' and current_entry is not None:
            if pointage.horodatage > current_entry:
                duration = pointage.horodatage - current_entry
                total_duration += duration
                user_durations[user_id] += duration
                local_entry = timezone.localtime(current_entry) if timezone.is_aware(current_entry) else current_entry
                local_exit = timezone.localtime(pointage.horodatage) if timezone.is_aware(pointage.horodatage) else pointage.horodatage
                work_day = local_entry.date()
                daily_stats[work_day]['duration'] += duration
                daily_stats[work_day]['sessions'] += 1
                daily_stats[work_day]['first_entry'] = (
                    local_entry
                    if daily_stats[work_day]['first_entry'] is None or local_entry < daily_stats[work_day]['first_entry']
                    else daily_stats[work_day]['first_entry']
                )
                daily_stats[work_day]['last_exit'] = (
                    local_exit
                    if daily_stats[work_day]['last_exit'] is None or local_exit > daily_stats[work_day]['last_exit']
                    else daily_stats[work_day]['last_exit']
                )
                completed_sessions += 1
            open_entries[user_id] = None

    today = timezone.localdate()
    start_of_week = today - timedelta(days=today.weekday())
    today_duration = daily_stats.get(today, {}).get('duration', timedelta())
    today_sessions = daily_stats.get(today, {}).get('sessions', 0)
    week_duration = sum(
        (stats['duration'] for work_day, stats in daily_stats.items() if start_of_week <= work_day <= today),
        timedelta(),
    )
    worked_days = [stats['duration'] for stats in daily_stats.values() if stats['duration'].total_seconds() > 0]
    average_duration = sum(worked_days, timedelta()) / len(worked_days) if worked_days else timedelta()

    daily_breakdown = []
    for work_day, stats in sorted(daily_stats.items(), reverse=True):
        first_entry = stats['first_entry']
        last_exit = stats['last_exit']
        duration = stats['duration']
        daily_breakdown.append({
            'date': work_day,
            'label': work_day.strftime('%d/%m/%Y'),
            'duration': duration,
            'duration_display': format_duration(duration),
            'first_entry': first_entry,
            'first_entry_display': first_entry.strftime('%H:%M') if first_entry else '--',
            'last_exit': last_exit,
            'last_exit_display': last_exit.strftime('%H:%M') if last_exit else '--',
            'sessions': stats['sessions'],
        })

    return {
        'total_duration': total_duration,
        'total_duration_display': format_duration(total_duration),
        'today_duration': today_duration,
        'today_duration_display': format_duration(today_duration),
        'today_sessions': today_sessions,
        'week_duration': week_duration,
        'week_duration_display': format_duration(week_duration),
        'average_duration': average_duration,
        'average_duration_display': format_duration(average_duration),
        'completed_sessions': completed_sessions,
        'open_sessions': sum(1 for value in open_entries.values() if value is not None),
        'daily_breakdown': daily_breakdown,
        'user_duration_map': dict(user_durations),
        'user_duration_display_map': {user_id: format_duration(duration) for user_id, duration in user_durations.items()},
    }
