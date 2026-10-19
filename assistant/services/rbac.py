from django.contrib.auth.models import User
from assistant.models import UserProfile


def get_or_create_user_profile(user: User) -> UserProfile:
    """Retrieves or creates a UserProfile for the given Django user."""
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'role': 'admin' if user.is_superuser else 'employee',
            'department': 'Operations' if user.is_superuser else 'General'
        }
    )
    return profile


def get_allowed_access_roles(user: User) -> list:
    """
    Returns list of Document.access_role choices this user is permitted to see:
    - employee: ['all']
    - manager: ['all', 'manager_plus']
    - admin: ['all', 'manager_plus', 'admin_only']
    """
    if not user.is_authenticated:
        return ['all']

    profile = get_or_create_user_profile(user)
    if profile.role == 'admin' or user.is_superuser:
        return ['all', 'manager_plus', 'admin_only']
    elif profile.role == 'manager':
        return ['all', 'manager_plus']
    else:
        return ['all']


def is_admin_or_manager(user: User) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = get_or_create_user_profile(user)
    return profile.role in ['admin', 'manager']
