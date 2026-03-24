from django.contrib import admin
from .models import Alerte


@admin.register(Alerte)
class AlerteAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'statut', 'utilisateur', 'pointage', 'date_creation')
    list_filter = ('type', 'statut')
    search_fields = ('utilisateur__username', 'utilisateur__email', 'description')
    date_hierarchy = 'date_creation'
