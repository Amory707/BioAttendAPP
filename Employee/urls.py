from django.urls import path
from . import views

app_name = 'employee'

urlpatterns = [
    # Utilisateurs
    path('utilisateurs/', views.utilisateur_list, name='utilisateur_list'),
    path('utilisateurs/<int:utilisateur_id>/', views.utilisateur_detail, name='utilisateur_detail'),
    path('utilisateurs/exporter-csv/', views.exporter_csv, name='exporter_csv'),

    # Pointages
    path('pointages/', views.pointage_list, name='pointage_list'),

    # Alertes
    path('alertes/', views.alerte_list, name='alerte_list'),

    # Rôles
    path('roles/', views.role_list, name='role_list'),
]
