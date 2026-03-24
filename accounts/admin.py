from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, Role, RoleUtilisateur
from django.core.exceptions import PermissionDenied


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
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'role' and not (request.user.is_superuser and request.user.username == 'bioattend'):
            kwargs['queryset'] = Role.objects.exclude(nom__iexact='acces_total')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


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

    def save_formset(self, request, form, formset, change):
        if hasattr(formset, 'forms'):
            for f in formset.forms:
                if not hasattr(f, 'cleaned_data'):
                    continue
                data = f.cleaned_data
                if not data or data.get('DELETE'):
                    continue
                role = data.get('role')
                if role and role.nom.lower() == 'acces_total' and not (request.user.is_superuser and request.user.username == 'bioattend'):
                    raise PermissionDenied("Seulement 'bioattend' peut attribuer le rôle acces_total.")
        return super().save_formset(request, form, formset, change)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'nom')
    search_fields = ('nom',)


@admin.register(RoleUtilisateur)
class RoleUtilisateurAdmin(admin.ModelAdmin):
    list_display = ('id', 'role', 'utilisateur')
    search_fields = ('role__nom', 'utilisateur__username', 'utilisateur__email')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'role' and not (request.user.is_superuser and request.user.username == 'bioattend'):
            kwargs['queryset'] = Role.objects.exclude(nom__iexact='acces_total')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if obj.role and obj.role.nom.lower() == 'acces_total' and not (request.user.is_superuser and request.user.username == 'bioattend'):
            raise PermissionDenied("Seulement 'bioattend' peut attribuer le rôle acces_total.")
        super().save_model(request, obj, form, change)
