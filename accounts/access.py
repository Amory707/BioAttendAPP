ACTIVE_SPACE_SESSION_KEY = 'active_dashboard_space'
EMPLOYEE_SPACE = 'employee'
ADMIN_SPACE = 'admin'


def user_can_access_employee_space(user):
    return bool(getattr(user, 'is_employe', False) or getattr(user, 'is_platform_admin', False))


def user_can_access_admin_space(user):
    return bool(getattr(user, 'is_platform_admin', False))


def get_default_space_for_user(user):
    if user_can_access_employee_space(user) and not user_can_access_admin_space(user):
        return EMPLOYEE_SPACE
    if user_can_access_admin_space(user):
        return ADMIN_SPACE
    return None


def get_allowed_spaces_for_user(user):
    allowed_spaces = []
    if user_can_access_employee_space(user):
        allowed_spaces.append(EMPLOYEE_SPACE)
    if user_can_access_admin_space(user):
        allowed_spaces.append(ADMIN_SPACE)
    return allowed_spaces


def get_active_space(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return None

    allowed_spaces = get_allowed_spaces_for_user(request.user)
    session_space = request.session.get(ACTIVE_SPACE_SESSION_KEY)

    if session_space in allowed_spaces:
        return session_space

    default_space = get_default_space_for_user(request.user)
    if default_space:
        request.session[ACTIVE_SPACE_SESSION_KEY] = default_space
    return default_space


def set_active_space(request, space):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return None

    allowed_spaces = get_allowed_spaces_for_user(request.user)
    if space not in allowed_spaces:
        return get_active_space(request)

    request.session[ACTIVE_SPACE_SESSION_KEY] = space
    return space


def is_employee_space_active(request):
    return get_active_space(request) == EMPLOYEE_SPACE
