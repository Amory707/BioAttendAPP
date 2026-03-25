from django.contrib import admin
from django.utils.html import format_html
from .models import Utilisateur, Pointage, Alerte, Role
import csv
from django.http import HttpResponse
from datetime import date

# 1. Filtre personnalisé pour la biométrie
class BiometricFilter(admin.SimpleListFilter):
    title = 'Statut biométrique'
    parameter_name = 'biometrique'

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
        return queryset

# 2. Action d'exportation CSV
def exporter_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="utilisateurs_bioattend.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID_Utilisateur', 'Nom', 'Prénom', 'Email', 'Département'])
    for obj in queryset:
        writer.writerow([obj.ID_Utilisateur, obj.Nom, obj.Prenom, obj.Email, obj.Departement])
    return response
exporter_csv.short_description = "Exporter la sélection en CSV"

# 3. Affichage des pointages directement dans la fiche utilisateur
class PointageInline(admin.TabularInline):
    model = Pointage
    extra = 0
    readonly_fields = ('horodatage', 'type', 'score_confiance')

# 4. Configuration de l'administration Utilisateur
@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):
    list_display = ('ID_Utilisateur', 'afficher_nom_complet', 'Departement', 'statut_ia', 'badge_presence', 'Date_debut')
    list_filter = ('Departement', 'Date_debut', BiometricFilter)
    search_fields = ('Nom', 'Prenom', 'Email')
    actions = [exporter_csv]
    filter_horizontal = ('roles',)
    list_editable = ('Departement',)
    inlines = [PointageInline]

    def afficher_nom_complet(self, obj):
        return f"{obj.Prenom} {obj.Nom}"
    afficher_nom_complet.short_description = "Identité"

    def statut_ia(self, obj):
        if obj.Embedding_facial:
            return format_html('<span style="color: green;">✔ Enrôlé</span>')
        return format_html('<span style="color: red;">✘ À faire</span>')
    statut_ia.short_description = "IA Ready"

    def badge_presence(self, obj):
        today = date.today()
        dernier = Pointage.objects.filter(utilisateur=obj, horodatage__date=today).last()
        if dernier and dernier.type == 'ENTREE':
            return format_html('<b style="background: #d4edda; color: #155724; padding: 5px; border-radius: 5px;">Présent</b>')
        return format_html('<b style="background: #f8d7da; color: #721c24; padding: 5px; border-radius: 5px;">Absent</b>')
    badge_presence.short_description = "Statut"

# 5. Administration des Pointages
@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    list_display = ('ID_Pointage', 'utilisateur', 'type', 'horodatage', 'score_confiance', 'statut')
    list_filter = ('type', 'statut', 'horodatage')
    search_fields = ('utilisateur__Nom', 'utilisateur__Prenom')

# 6. Administration des Alertes
@admin.register(Alerte)
class AlerteAdmin(admin.ModelAdmin):
    list_display = ('ID_Alerte', 'Type', 'Statut', 'utilisateur', 'Date_creation')
    list_filter = ('Statut', 'Type', 'Date_creation')
    list_editable = ('Statut',)
    search_fields = ('utilisateur__Nom', 'Description')

# 7. Administration des Rôles
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('ID_Role', 'Nom')