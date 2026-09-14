"""Optional BTCPay checkout. Settlement is always verified server-to-server."""
import json
from decimal import Decimal
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .membership import TERM, chain_height, membership_state
from .models import PaymentOrder, PublishingMembership


def payments_ready():
    return bool(settings.BTCPAY_URL and settings.BTCPAY_STORE_ID and settings.BTCPAY_API_KEY)


def provider_request(path, payload=None):
    base = settings.BTCPAY_URL.rstrip('/')
    if not base.startswith('https://'):
        raise ValueError('BTCPay requires HTTPS.')
    request = Request(base+'/api/v1/stores/'+quote(settings.BTCPAY_STORE_ID, safe='')+path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization': 'token '+settings.BTCPAY_API_KEY, 'Content-Type': 'application/json'})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read(200000))


def create_checkout(user):
    if not payments_ready():
        raise ValueError('Bitcoin checkout is not open yet.')
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        state = membership_state(user)
        if state['height'] is None:
            raise ValueError('Block verification is unavailable. Please try again shortly.')
        recent = PaymentOrder.objects.filter(user=user, created_at__gt=timezone.now()-timedelta(minutes=15),
            applied_at_block__isnull=True).exclude(status__in=['Expired', 'Invalid', 'failed']).first()
        if recent:
            if recent.checkout_url:
                return recent
            raise ValueError('Your previous checkout is being checked. Please wait before retrying.')
        order = PaymentOrder.objects.create(user=user, amount_usd=state['total'], redemption=state['stage']=='redemption')
    # Reserve first. An uncertain network response must not trigger duplicate invoices.
    try:
        invoice = provider_request('/invoices', {'amount': str(order.amount_usd), 'currency': 'USD',
            'metadata': {'orderId': str(order.id)}, 'checkout': {'expirationMinutes': 15}})
        checkout_url = invoice['checkoutLink']
        if urlsplit(checkout_url).scheme != 'https' or urlsplit(checkout_url).netloc != urlsplit(settings.BTCPAY_URL).netloc:
            raise ValueError('Unexpected checkout destination.')
        order.provider_invoice_id = invoice['id']
        order.checkout_url = checkout_url
        order.status = 'New'
        order.save()
        return order
    except Exception:
        order.status = 'uncertain'
        order.save(update_fields=['status'])
        raise ValueError('Checkout could not be confirmed. No access has changed; please retry later.')


def reconcile_order(order):
    if order.applied_at_block is not None or not order.provider_invoice_id:
        return
    invoice = provider_request('/invoices/'+quote(order.provider_invoice_id, safe=''))
    if (invoice.get('id') != order.provider_invoice_id or invoice.get('currency') != 'USD'
        or Decimal(str(invoice.get('amount'))) != Decimal(str(order.amount_usd))
        or invoice.get('metadata', {}).get('orderId') != str(order.id)):
        raise ValueError('Invoice identity or amount mismatch.')
    if invoice.get('status') != 'Settled':
        PaymentOrder.objects.filter(pk=order.pk, applied_at_block__isnull=True).update(status=invoice.get('status', 'unknown'))
        return
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=order.user_id)
        locked = PaymentOrder.objects.select_for_update().get(pk=order.pk)
        if locked.applied_at_block is not None:
            return
        height = chain_height()
        if height is None:
            raise ValueError('Settlement awaits fresh block verification.')
        member = PublishingMembership.objects.filter(user_id=order.user_id).first()
        expiry = max(height, member.expires_at_block if member else height)+TERM
        PublishingMembership.objects.update_or_create(user_id=order.user_id, defaults={'expires_at_block': expiry})
        locked.applied_at_block = height
        locked.status = 'Settled'
        locked.save(update_fields=['applied_at_block', 'status'])
