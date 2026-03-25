import threading


class ThreadLocalMiddleware:
    """
    Stocke la requête courante dans un thread-local pour y accéder depuis les modèles.

    Usage: ajouter 'accounts.middleware.ThreadLocalMiddleware' dans MIDDLEWARE.
    """
    _thread_locals = threading.local()

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        type(self)._thread_locals.request = request
        response = self.get_response(request)
        return response

    @classmethod
    def get_current_request(cls):
        return getattr(cls._thread_locals, 'request', None)
from django.shortcuts import render

class EmployeeAdminAccessMiddleware:
    """
    Block /admin/ pages for users with role 'employé' who are not staff.

    If an authenticated user has role 'employé' and tries to access any URL
    under /admin/ while not being staff, show a friendly access-denied page.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        user = getattr(request, 'user', None)
        if path.startswith('/admin/') and user and user.is_authenticated:
            try:
                is_employe = getattr(user, 'is_employe', False)
            except Exception:
                is_employe = False
            if is_employe and not user.is_staff:
                return render(request, 'access_denied_employee.html', status=403)
        return self.get_response(request)
