from datetime import time
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ScheduleSettings(models.Model):
    singleton_guard = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    is_enabled = models.BooleanField(default=True)
    arrival_window_start = models.TimeField(default=time(8, 0))
    arrival_window_end = models.TimeField(default=time(10, 0))
    departure_window_start = models.TimeField(default=time(16, 0))
    departure_window_end = models.TimeField(default=time(18, 0))
    required_daily_minutes = models.PositiveIntegerField(default=8 * 60)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'schedule_settings'
        verbose_name = 'Paramètre emploi du temps'
        verbose_name_plural = 'Paramètres emploi du temps'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'singleton_guard': 1})
        return obj

    def __str__(self):
        return f"Emploi du temps {'actif' if self.is_enabled else 'désactivé'}"


class ScheduleRequest(models.Model):
    CATEGORY_RETARD = 'RETARD'
    CATEGORY_CONGE = 'CONGE'
    CATEGORY_MALADIE = 'MALADIE'
    CATEGORY_AUTRE = 'AUTRE'

    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'

    CATEGORY_CHOICES = [
        (CATEGORY_RETARD, 'Retard'),
        (CATEGORY_CONGE, 'Congé'),
        (CATEGORY_MALADIE, 'Maladie'),
        (CATEGORY_AUTRE, 'Autre'),
    ]
    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_APPROVED, 'Approuvée'),
        (STATUS_REJECTED, 'Refusée'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='schedule_requests',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_schedule_requests',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_schedule_requests',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    description = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'schedule_request'
        ordering = ['-start_at', '-created_at']
        verbose_name = 'Demande planning'
        verbose_name_plural = 'Demandes planning'
        indexes = [
            models.Index(fields=['utilisateur', 'status', 'start_at', 'end_at'], name='sched_user_status_range_idx'),
            models.Index(fields=['status', 'start_at', 'created_at'], name='sched_status_time_idx'),
        ]

    def clean(self):
        if self.end_at <= self.start_at:
            raise ValidationError("La date de fin doit être postérieure à la date de début.")

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED

    def __str__(self):
        user_label = self.utilisateur.get_full_name() or self.utilisateur.username
        return f"{user_label} · {self.get_category_display()} · {self.get_status_display()}"
