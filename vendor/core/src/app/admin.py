from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Profil, Utilisateur


class ProfilInline(admin.StackedInline):
    model = Profil
    can_delete = False
    verbose_name_plural = 'Profil'


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    model = Utilisateur
    inlines = [ProfilInline]
    ordering = ['-date_joined']
    list_display = ['email', 'nom', 'prenom', 'telephone', 'type_compte', 'statut_compte', 'is_active', 'date_joined']
    list_filter = ['type_compte', 'statut_compte', 'is_active', 'is_staff']
    search_fields = ['email', 'nom', 'prenom', 'telephone']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations', {'fields': ('nom', 'prenom', 'telephone', 'type_compte', 'statut_compte')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nom', 'prenom', 'telephone', 'type_compte', 'password1', 'password2'),
        }),
    )


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'ville', 'two_factor_enabled', 'langue')
    search_fields = ('user__email', 'user__nom', 'user__prenom')

