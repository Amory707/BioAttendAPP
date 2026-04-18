from django.contrib import admin

from .models import ScheduleRequest, ScheduleSettings


@admin.register(ScheduleRequest)
class ScheduleRequestAdmin(admin.ModelAdmin):
    list_display = (
        "utilisateur",
        "category",
        "status",
        "start_at",
        "end_at",
        "created_by",
        "reviewed_by",
    )
    list_filter = ("category", "status")
    search_fields = (
        "utilisateur__username",
        "utilisateur__first_name",
        "utilisateur__last_name",
        "description",
    )


@admin.register(ScheduleSettings)
class ScheduleSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "is_enabled",
        "arrival_window_start",
        "arrival_window_end",
        "departure_window_start",
        "departure_window_end",
        "required_daily_minutes",
        "updated_at",
    )
