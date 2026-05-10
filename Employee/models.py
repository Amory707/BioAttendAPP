from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class BiometricSettings(models.Model):
    singleton_guard = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    photo_similarity_threshold = models.FloatField(
        default=50.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'biometric_settings'
        verbose_name = 'Paramètre biométrique'
        verbose_name_plural = 'Paramètres biométriques'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'singleton_guard': 1})
        return obj

    def __str__(self):
        return f"Seuil similarité photos: {self.photo_similarity_threshold:.1f}%"
