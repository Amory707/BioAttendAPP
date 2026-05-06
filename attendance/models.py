import uuid
from django.conf import settings
from django.db import models


class Pointage(models.Model):

    STATUT_CHOICES = [('VALIDE', 'Validé'), ('NON_VALIDE', 'Non validé')]
    TYPE_CHOICES = [('ENTREE', 'ENTREE'), ('SORTIE', 'SORTIE')]
    ORIGINE_MANUEL = 'MANUEL'
    ORIGINE_POINTEUSE = 'POINTEUSE'
    ORIGINE_CHOICES = [
        (ORIGINE_MANUEL, 'Manuel'),
        (ORIGINE_POINTEUSE, 'Pointeuse'),
    ]
    INCIDENT_CHOICES = [
        ('UTILISATEUR_INCONNU', 'UTILISATEUR_INCONNU'),
        ('ECHEC_RECONNAISSANCE', 'ECHEC_RECONNAISSANCE'),
        ('TENTATIVE_FRAUDE', 'TENTATIVE_FRAUDE'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='pointages',
    )

    statut = models.CharField(max_length=20, choices=STATUT_CHOICES)

    horodatage = models.DateTimeField()

    type = models.CharField(max_length=10, choices=TYPE_CHOICES)

    score_confiance = models.FloatField()
    
    origine = models.CharField(max_length=20, choices=ORIGINE_CHOICES, default=ORIGINE_MANUEL)
    incident_type = models.CharField(max_length=50, choices=INCIDENT_CHOICES, blank=True)
    device_name = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'pointage'
        ordering = ['-horodatage']
        indexes = [
            models.Index(fields=['utilisateur', 'statut', 'horodatage'], name='point_user_stat_time_idx'),
            models.Index(fields=['utilisateur', 'origine', '-horodatage', '-id'], name='point_user_orig_time_idx'),
            models.Index(fields=['origine', 'statut', 'incident_type', 'horodatage'], name='point_security_time_idx'),
            models.Index(fields=['statut', 'horodatage'], name='point_stat_time_idx'),
        ]

    def __str__(self):
        return f"{self.utilisateur} - {self.type} @ {self.horodatage}"
