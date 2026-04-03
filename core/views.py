from django.shortcuts import redirect


def home(request):
    if request.user.is_authenticated:
        if request.user.is_employe and not request.user.is_platform_admin:
            return redirect('dashboard:employee_home')
        return redirect('dashboard:index')
    return redirect('login')

