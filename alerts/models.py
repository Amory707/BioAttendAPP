import uuid
from django.conf import settings
from django.db import models


class Alerte(models.Model):
    """
    Modèle ALERTES selon le MLD
    Alertes automatiques : retard, absence, reconnaissance échouée, etc.
    """
    SECURITY_TYPES = (
        'UTILISATEUR_INCONNU',
        'ECHEC_RECONNAISSANCE',
        'TENTATIVE_FRAUDE',
    )

    TYPE_CHOICES = [
        ('RETARD', 'Retard'),
        ('ABSENCE', 'Absence'),
        ('DEPART_ANTICIPE', 'Départ anticipé'),
        ('JOURNEE_COURTE', 'Journée trop courte'),
        ('DEMANDE_PLANNING', 'Demande planning'),
        ('UTILISATEUR_INCONNU', 'Utilisateur inconnu'),
        ('ECHEC_RECONNAISSANCE', 'Visage non détecté'),
        ('TENTATIVE_FRAUDE', 'Tentative de fraude'),
        ('DOUBLE_POINTAGE', 'Double pointage'),
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
    masquee = models.BooleanField(default=False)

    class Meta:
        db_table = 'alerte'
        ordering = ['-date_creation']

    @classmethod
    def default_description_for_incident(cls, incident_type):
        descriptions = {
            'UTILISATEUR_INCONNU': "Utilisateur inconnu détecté par la borne.",
            'ECHEC_RECONNAISSANCE': "Visage non détecté ou reconnaissance échouée.",
            'TENTATIVE_FRAUDE': "Tentative de fraude détectée par le contrôle biométrique.",
        }
        return descriptions.get(incident_type, "Alerte de sécurité biométrique.")

    @classmethod
    def create_or_update_for_incident(
        cls,
        incident_type,
        description='',
        *,
        pointage=None,
        utilisateur=None,
        event_status='',
        device_name='',
        details=None,
    ):
        if details is None:
            details = {}

        if utilisateur is None and pointage is not None:
            utilisateur = getattr(pointage, 'utilisateur', None)

        if not device_name and pointage is not None:
            device_name = getattr(pointage, 'device_name', '') or ''

        if not event_status and pointage is not None and isinstance(getattr(pointage, 'details', {}), dict):
            event_status = pointage.details.get('status', '')

        payload = {
            'utilisateur': utilisateur,
            'type': incident_type,
            'description': (description or cls.default_description_for_incident(incident_type)).strip(),
            'event_status': event_status or '',
            'device_name': device_name or '',
            'details': details or {},
        }

        if pointage is not None:
            existing = cls.objects.filter(pointage=pointage).first()
            if existing is not None:
                updated_fields = []

                if existing.utilisateur is None and payload['utilisateur'] is not None:
                    existing.utilisateur = payload['utilisateur']
                    updated_fields.append('utilisateur')

                if existing.type != payload['type'] and payload['type']:
                    existing.type = payload['type']
                    updated_fields.append('type')

                if not existing.description and payload['description']:
                    existing.description = payload['description']
                    updated_fields.append('description')

                if not existing.event_status and payload['event_status']:
                    existing.event_status = payload['event_status']
                    updated_fields.append('event_status')

                if not existing.device_name and payload['device_name']:
                    existing.device_name = payload['device_name']
                    updated_fields.append('device_name')

                if (not existing.details) and payload['details']:
                    existing.details = payload['details']
                    updated_fields.append('details')

                if updated_fields:
                    existing.save(update_fields=updated_fields)
                return existing

        return cls.objects.create(pointage=pointage, **payload)

    def __str__(self):
        return self.type
