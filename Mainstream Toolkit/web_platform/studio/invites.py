"""Hashed bearer codes, with serialized capacity and per-account redemption."""
import calendar
import hashlib
import secrets
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from .access import is_admin
from .models import ComplimentaryAccess, Invitation, InviteRedemption, InviteSettings


def can_issue(user):
    return bool(user.is_authenticated and user.is_active and (is_admin(user) or (
        InviteSettings.objects.filter(pk=1, member_issuers_enabled=True).exists()
        and user.has_perm('studio.issue_invitations'))))


def digest(code):
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def issue(user, *, label, kind, max_uses=1, redeem_before=None):
    if not can_issue(user):
        raise PermissionDenied
    if kind not in Invitation.Kind.values or not label.strip() or not 1 <= max_uses <= 10000:
        raise ValueError('Choose an access type, a label, and between 1 and 10,000 uses.')
    if redeem_before and redeem_before <= timezone.now():
        raise ValueError('The redemption deadline must be in the future.')
    code = 'OBS-' + secrets.token_hex(16).upper()
    invitation = Invitation.objects.create(created_by=user, label=label.strip(), kind=kind,
        max_uses=max_uses, redeem_before=redeem_before, code_hash=digest(code), code_hint=code[:10])
    return invitation, code


def add_three_months(value):
    month_index = value.year * 12 + value.month - 1 + 3
    year, month = divmod(month_index, 12)
    month += 1
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


def redeem(user, code):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied
    with transaction.atomic():
        # Match the user-first lock order used by payment and content writes.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        invitation = Invitation.objects.select_for_update().filter(code_hash=digest(code)).first()
        now = timezone.now()
        if not invitation or not invitation.enabled or (invitation.redeem_before and invitation.redeem_before <= now):
            raise ValueError('This invite code is invalid, disabled, or expired.')
        if InviteRedemption.objects.filter(invitation=invitation, user=user).exists():
            raise ValueError('You have already redeemed this code.')
        if invitation.uses >= invitation.max_uses:
            raise ValueError('This invite code has no uses remaining.')
        access, _ = ComplimentaryAccess.objects.get_or_create(user=user)
        if access.lifetime:
            raise ValueError('You already have lifetime invite access.')
        if is_admin(user):
            raise ValueError('Admins already have unlimited access. Save this invite for someone else.')
        if invitation.kind == Invitation.Kind.LIFETIME:
            access.lifetime, access.expires_at = True, None
        else:
            access.expires_at = add_three_months(max(now, access.expires_at or now))
        access.save()
        InviteRedemption.objects.create(invitation=invitation, user=user,
            granted_until=access.expires_at, lifetime=access.lifetime)
        invitation.uses += 1
        invitation.save(update_fields=['uses'])
        return access
