from django.contrib.auth import get_user_model, logout
from django.db import transaction
from django.http import HttpResponse


class AccountWriteMiddleware:
    """Serialize signed-in writes with merging; stale requests cannot write to retired accounts."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ('GET','HEAD','OPTIONS') or not request.user.is_authenticated or request.path == '/account/merge/confirm/':
            return self.get_response(request)
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not user.is_active:
                logout(request)
                return HttpResponse('Your account changed. Sign in again to continue.',status=409)
            return self.get_response(request)
