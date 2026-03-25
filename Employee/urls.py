from django.urls import path
from . import views

app_name = 'Employee'

urlpatterns = [
    path('utilisateurs/', views.utilisateur_list, name='utilisateur_list'),
    path('utilisateurs/ajouter/', views.create_utilisateur, name='utilisateur_create'),
    path('utilisateurs/<uuid:utilisateur_id>/modifier/', views.update_utilisateur, name='utilisateur_update'),
    path('utilisateurs/<uuid:utilisateur_id>/supprimer/', views.delete_utilisateur, name='utilisateur_delete'),
    path('utilisateurs/<uuid:utilisateur_id>/', views.utilisateur_detail, name='utilisateur_detail'),
    path('utilisateurs/exporter-csv/', views.exporter_csv, name='exporter_csv'),
    # Par la suite faudra peut-être changer cela de place.
    path('pointages/', views.pointage_list, name='pointage_list'),
    path('alertes/', views.alerte_list, name='alerte_list'), 
    path('roles/', views.role_list, name='role_list'),
]
