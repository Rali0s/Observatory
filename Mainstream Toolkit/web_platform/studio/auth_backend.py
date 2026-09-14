from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from .merging import canonical_user


class MergedAccountBackend(ModelBackend):
    """A retired username/password authenticates its active, verified merge target.

    get_user intentionally stays unchanged: old sessions on retired accounts fail.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        try:
            original = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist:
            get_user_model()().set_password(password)
            return None
        if original.check_password(password):
            target = canonical_user(original)
            if self.user_can_authenticate(target):
                return target
        return None
