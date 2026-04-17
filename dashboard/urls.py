from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='index'), 
    path('employe/', views.employee_home, name='employee_home'),
    path('employe/pointages/', views.employee_pointages, name='employee_pointages'),
    path('employe/prestations/', views.employee_prestations, name='employee_prestations'),
    path('employe/heures/export-csv/', views.employee_work_hours_csv, name='employee_work_hours_csv'),
    path('employe/alertes/', views.employee_alertes, name='employee_alertes'),
    path('espace/<str:space>/', views.switch_space, name='switch_space'),
    path('logout/', views.logout_view, name='logout'),
]