from django.contrib import admin
from .models import Alerte


@admin.register(Alerte)
class AlerteAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'utilisateur', 'pointage', 'date_creation')
    list_filter = ('type',)
    search_fields = ('utilisateur__username', 'utilisateur__email', 'description')
    date_hierarchy = 'date_creation'
