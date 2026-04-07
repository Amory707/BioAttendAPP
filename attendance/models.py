import uuid
from django.conf import settings
from django.db import models


class Pointage(models.Model):
    """
    Modèle POINTAGE selon le MLD
    Enregistre entrée/sortie avec reconnaissance faciale
    """
    STATUT_CHOICES = [('VALIDE', 'Validé'), ('NON_VALIDE', 'Non validé')]
    TYPE_CHOICES = [('ENTREE', 'ENTREE'), ('SORTIE', 'SORTIE')]
    ORIGINE_MANUEL = 'MANUEL'
    ORIGINE_POINTEUSE = 'POINTEUSE'
    ORIGINE_CHOICES = [
        (ORIGINE_MANUEL, 'Manuel'),
        (ORIGINE_POINTEUSE, 'Pointeuse'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pointages',
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES)
    horodatage = models.DateTimeField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    score_confiance = models.FloatField()
    origine = models.CharField(max_length=20, choices=ORIGINE_CHOICES, default=ORIGINE_MANUEL)

    class Meta:
        db_table = 'pointage'
        ordering = ['-horodatage']

    def __str__(self):
        return f"{self.utilisateur} - {self.type} @ {self.horodatage}"
