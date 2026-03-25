from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

@login_required(login_url='login')
def dashboard(request):
    is_platform_admin = (
        request.user.role_utilisateurs.filter(role__nom__iexact='admin').exists()
        or request.user.role_utilisateurs.filter(role__nom__iexact='acces_total').exists()
        or (request.user.is_superuser and request.user.username == 'bioattend')
    )
    if not is_platform_admin:
        messages.error(request, "Accès refusé : votre compte n'a pas les droits plateforme.")
        logout(request)
        return redirect('login')

    context = {
        'user': request.user,
    }
    return render(request, 'dashboard.html', context)

def logout_view(request):
    logout(request)
    return redirect('login')  
