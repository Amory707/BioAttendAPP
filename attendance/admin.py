from django.contrib import admin
from .models import Pointage


@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    list_display = ('id', 'utilisateur', 'type', 'statut', 'origine', 'horodatage', 'score_confiance')
    list_filter = ('type', 'statut', 'origine')
    search_fields = ('utilisateur__username', 'utilisateur__email')
    date_hierarchy = 'horodatage'
