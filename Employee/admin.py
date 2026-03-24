from django.contrib import admin

from django.utils.html import format_html
from .models import Employee,Pointage
import csv
from django.http import HttpResponse
from datetime import date


class BiometricFilter(admin.SimpleListFilter):
    title = 'Statut biométrique'
    parameter_name = 'biometric'

    def lookups(self, request, model_admin):
        return (
            ('enrolled', 'Enrôlé'),
            ('not_enrolled', 'Non enrôlé'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'enrolled':
            return queryset.filter(Embedding_facial__isnull=False)
        if self.value() == 'not_enrolled':
            return queryset.filter(Embedding_facial__isnull=True)


def export_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="employees.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Nom', 'Prenom', 'Email', 'Departement'])
    for employee in queryset:
        writer.writerow([employee.ID_Utilisateur, employee.Nom, employee.Prenom, employee.Email, employee.Departement])
    return response
export_csv.short_description = "Exporter les employés sélectionnés en CSV"


# Pour voir l'historique directement DANS la fiche de l'employé
class PointageInline(admin.TabularInline):
    model = Pointage
    extra = 0 # Ne pas afficher de lignes vides par défaut
    readonly_fields = ('horodatage', 'type', 'score_confiance')

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    # Colonnes affichées avec indicateurs visuels
    list_display = ('ID_Utilisateur', 'display_full_name', 'Departement', 'status_biometric', 'presence_badge', 'Date_debut')
    
    # Filtres latéraux pour une navigation rapide
    list_filter = ('Departement', 'Date_debut', BiometricFilter)
    
    # Recherche par nom, prénom ou email
    search_fields = ('Nom', 'Prenom', 'Email')

    # Actions
    actions = [export_csv]

    # 1. Fonction pour afficher le nom complet plus proprement
    def display_full_name(self, obj):
        return f"{obj.Prenom} {obj.Nom}"
    display_full_name.short_description = "Employé"

    # 2. Indicateur Biométrique : l'employé est-il enregistré dans l'IA ?
    def status_biometric(self, obj):
        if obj.Embedding_facial:
            return format_html('<span style="color: green;">✔ Enrôlé</span>')
        return format_html('<span style="color: red;">✘ À faire</span>')
    status_biometric.short_description = "IA Ready"

    # 3. Badge de présence basé sur le dernier pointage du jour
    def presence_badge(self, obj):
        today = date.today()
        last_pointage = Pointage.objects.filter(employee=obj, horodatage__date=today).last()
        if last_pointage and last_pointage.type == 'ENTREE':
            return format_html('<b style="background: #d4edda; color: #155724; padding: 5px; border-radius: 5px;">Présent</b>')
        return format_html('<b style="background: #f8d7da; color: #721c24; padding: 5px; border-radius: 5px;">Absent</b>')
    presence_badge.short_description = "Statut"

    # Permet de modifier le département directement depuis la liste sans ouvrir la fiche
    list_editable = ('Departement',)

    inlines = [PointageInline] # <--- Ceci ajoute l'historique en bas de la fiche employé !



@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    list_display = ('employee', 'type', 'horodatage', 'score_confiance', 'statut')
    list_filter = ('type', 'statut', 'horodatage')
    search_fields = ('employee__Nom', 'employee__Prenom')

