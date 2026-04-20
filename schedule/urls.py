from django.urls import path

from . import views

app_name = 'schedule'

urlpatterns = [
    path('', views.schedule_home, name='home'),
    path('submit/', views.submit_request, name='submit'),
    path('export/csv/', views.export_schedule_csv, name='export_csv'),
    path('settings/', views.schedule_settings_view, name='settings'),
    path('settings/toggle/', views.toggle_schedule_features, name='toggle'),
    path('requests/<uuid:request_id>/approve/', views.review_request, {'decision': 'approve'}, name='approve'),
    path('requests/<uuid:request_id>/reject/', views.review_request, {'decision': 'reject'}, name='reject'),
]
