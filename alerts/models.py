import uuid
from django.conf import settings
from django.db import models


class Alerte(models.Model):
    """
    Modèle ALERTES selon le MLD
    Alertes automatiques : retard, absence, reconnaissance échouée, etc.
    """
    STATUT_CHOICES = [
        ('NOUVELLE', 'NOUVELLE'),
        ('VUE', 'VUE'),
        ('TRAITEE', 'TRAITEE'),
    ]
    TYPE_CHOICES = [
        ('RETARD', 'RETARD'),
        ('ABSENCE', 'ABSENCE'),
        ('UTILISATEUR_INCONNU', 'UTILISATEUR_INCONNU'),
        ('ECHEC_RECONNAISSANCE', 'ECHEC_RECONNAISSANCE'),
        ('TENTATIVE_FRAUDE', 'TENTATIVE_FRAUDE'),
        ('DOUBLE_POINTAGE', 'DOUBLE_POINTAGE'),
    ]
    EVENT_STATUS_CHOICES = [
        ('ERROR', 'ERROR'),
        ('REJECTED', 'REJECTED'),
        ('BLOCKED', 'BLOCKED'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alertes',
    )
    pointage = models.ForeignKey(
        'attendance.Pointage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alertes',
    )
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    description = models.TextField()
    event_status = models.CharField(max_length=20, choices=EVENT_STATUS_CHOICES, blank=True)
    device_name = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='NOUVELLE')

    class Meta:
        db_table = 'alerte'
        ordering = ['-date_creation']

    def __str__(self):
        return f"[{self.statut}] {self.type}"
