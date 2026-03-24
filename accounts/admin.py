from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, Role, RoleUtilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'departement', 'roles_list', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('departement', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Informations biométriques', {'fields': ('embedding_facial', 'departement', 'date_debut', 'date_fin')}),
    )
    inlines = ()

    def roles_list(self, obj):
        return ", ".join([r.nom for r in obj.roles.all()])
    roles_list.short_description = 'Rôles'


class RoleUtilisateurInline(admin.TabularInline):
    model = RoleUtilisateur
    fk_name = 'utilisateur'
    extra = 1
    autocomplete_fields = ('role',)


# re-register UtilisateurAdmin with inline
admin.site.unregister(Utilisateur)
@admin.register(Utilisateur)
class UtilisateurAdminWithInline(UserAdmin):
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'departement', 'roles_list', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('departement', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Informations biométriques', {'fields': ('embedding_facial', 'departement', 'date_debut', 'date_fin')}),
    )
    inlines = (RoleUtilisateurInline,)

    def roles_list(self, obj):
        return ", ".join([r.nom for r in obj.roles.all()])
    roles_list.short_description = 'Rôles'


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'nom')
    search_fields = ('nom',)


@admin.register(RoleUtilisateur)
class RoleUtilisateurAdmin(admin.ModelAdmin):
    list_display = ('id', 'role', 'utilisateur')
    search_fields = ('role__nom', 'utilisateur__username', 'utilisateur__email')
