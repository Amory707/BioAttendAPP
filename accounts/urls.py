from django.urls import path
from django.contrib.auth import views as auth_views
from .views import CustomLoginView, settings_view, logout_all_sessions

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('settings/', settings_view, name='settings'),
    path('password/change/', auth_views.PasswordChangeView.as_view(template_name='accounts/password_change_form.html', success_url='/accounts/login/'), name='password_change'),
    path('password/change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='accounts/password_change_done.html'), name='password_change_done'),
    path('sessions/clear/', logout_all_sessions, name='logout_all_sessions'),
]
