"""Block-based publishing entitlement. No account deletion, no wall-clock expiry."""
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .access import is_admin
from .models import ChainTip, PublishingMembership, ComplimentaryAccess

TERM = 4320
RENEWAL_WINDOW = 4320
FINAL_WINDOW = 2160
PRICE = Decimal('18.00')
REDEMPTION = Decimal('27.00')


def chain_height():
    tip = ChainTip.objects.filter(pk=1).first()
    if not tip or not 0 <= (timezone.now()-tip.observed_at).total_seconds() <= settings.BLOCK_MAX_AGE_SECONDS:
        return None
    return max(0, tip.height - 5)  # six-confirmation height; reduces reorg sensitivity


def membership_state(user):
    member = PublishingMembership.objects.filter(user=user).first()
    height = chain_height()
    result = {'height': height, 'expires': member.expires_at_block if member else None,
              'price': PRICE, 'redemption_fee': REDEMPTION, 'total': PRICE,
              'remaining': None, 'deadline': None, 'days': None, 'can_publish': False, 'complimentary': False}
    access = ComplimentaryAccess.objects.filter(user=user).first()
    if is_admin(user):
        result.update(stage='admin', label='Unlimited admin access', can_publish=True, complimentary=True, total=0, action='Publish')
        return result
    if access and (access.lifetime or (access.expires_at and access.expires_at > timezone.now())):
        result.update(stage='lifetime' if access.lifetime else 'invite', label='Lifetime invite access' if access.lifetime else 'Free invite access',
            can_publish=True, complimentary=True, total=0, access_expires_at=access.expires_at, action='Publish')
        return result
    if member is None:
        result.update(stage='free', label='Free account', action='Start publishing membership')
    elif height is None:
        result.update(stage='syncing', label='Checking Bitcoin block height', action='Waiting for block verification')
    else:
        expiry = member.expires_at_block
        if height < expiry:
            result.update(stage='active', label='Publishing active', deadline=expiry,
                          can_publish=True, action='Extend membership')
        elif height < expiry+RENEWAL_WINDOW:
            result.update(stage='renewal', label='Publishing paused', deadline=expiry+RENEWAL_WINDOW,
                          action='Renew publishing access')
        elif height < expiry+RENEWAL_WINDOW+FINAL_WINDOW:
            result.update(stage='final', label='Final renewal window', deadline=expiry+RENEWAL_WINDOW+FINAL_WINDOW,
                          action='Renew before redemption is required')
        else:
            result.update(stage='redemption', label='Redemption required', total=PRICE+REDEMPTION,
                          action='Redeem publishing access')
        if result['deadline'] is not None:
            result['remaining'] = max(0, result['deadline']-height)
            result['days'] = round(result['remaining']/144, 1)
    return result
