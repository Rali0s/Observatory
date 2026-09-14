"""The future billing adapter changes grants; views only ask about capabilities."""
from django.conf import settings
from types import SimpleNamespace
from .models import AccessGrant


def is_admin(user):
    return bool(user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser))


def require_access(user):
    if is_admin(user):
        return SimpleNamespace(max_projects=None, max_words_per_revision=None)
    # Tools are free. Legacy grants only supply optional resource limits;
    # payment, enabled, and expiry never revoke private writing access.
    grant = AccessGrant.objects.filter(user=user).first()
    return SimpleNamespace(max_projects=grant.max_projects if grant else 10,
        max_words_per_revision=grant.max_words_per_revision if grant else settings.OBSERVATORY_MAX_WORDS)


def word_limit(grant):
    return None if grant.max_words_per_revision is None else min(grant.max_words_per_revision, settings.OBSERVATORY_MAX_WORDS)
