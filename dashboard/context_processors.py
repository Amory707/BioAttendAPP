from alerts.models import Alerte

from accounts.access import EMPLOYEE_SPACE, get_active_space

def topbar_alert_count(request):
    """Expose le nombre d'alertes non traitées pour le badge de la topbar."""
    
    user = getattr(request, "user", None)
    
    if not user or not user.is_authenticated: return {"topbar_alert_count": 0}

    if get_active_space(request) == EMPLOYEE_SPACE or (getattr(user, "is_employe", False) and not getattr(user, "is_platform_admin", False)): count = Alerte.objects.filter(utilisateur=user, masquee=False).exclude(statut="TRAITEE").count()
    
    else: count = Alerte.objects.filter(masquee=False).exclude(statut="TRAITEE").count()

    return {"topbar_alert_count": count}
