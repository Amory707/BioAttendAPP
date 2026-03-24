from django.contrib import admin
from .models import Role, Utilisateur, RoleUtilisateur, Pointage, Alerte


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "nom")
    search_fields = ("nom",)


@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "login_utilisateur",
        "nom",
        "prenom",
        "email",
        "departement",
    )
    search_fields = ("login_utilisateur", "nom", "prenom", "email")
    list_filter = ("departement",)


@admin.register(RoleUtilisateur)
class RoleUtilisateurAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "utilisateur")
    search_fields = ("role__nom", "utilisateur__login_utilisateur", "utilisateur__email")


@admin.register(Pointage)
class PointageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "utilisateur",
        "type",
        "statut",
        "horodatage",
        "score_confiance",
    )
    list_filter = ("type", "statut")
    search_fields = ("utilisateur__login_utilisateur", "utilisateur__email")


@admin.register(Alerte)
class AlerteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "type",
        "statut",
        "utilisateur",
        "pointage",
        "date_creation",
    )
    list_filter = ("type", "statut")
    search_fields = ("utilisateur__login_utilisateur", "utilisateur__email", "description")

