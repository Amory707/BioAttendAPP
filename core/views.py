from django.shortcuts import redirect

from accounts.access import EMPLOYEE_SPACE, get_default_space_for_user, set_active_space

def home(request):

    if request.user.is_authenticated:
        
        default_space = get_default_space_for_user(request.user)
        
        if default_space: set_active_space(request, default_space)
        if default_space == EMPLOYEE_SPACE: return redirect('dashboard:employee_home')

        return redirect('dashboard:index')
    
    return redirect('login')

