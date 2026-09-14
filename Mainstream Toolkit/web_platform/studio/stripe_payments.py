"""One-time card checkout for the existing block-based publishing membership."""
from datetime import timedelta
from urllib.parse import urlsplit
import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from .membership import TERM, chain_height, membership_state
from .models import PaymentOrder, PublishingMembership


def ready():
    return bool(settings.STRIPE_ENABLED and settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET)


def client():
    return stripe.StripeClient(settings.STRIPE_SECRET_KEY, max_network_retries=2)


def create_checkout(user):
    if not ready():
        raise ValueError('Card checkout is not configured yet.')
    base = settings.PUBLIC_BASE_URL
    origin = urlsplit(base)
    if not origin.netloc or (origin.scheme != 'https' and not settings.DEBUG):
        raise ValueError('Configure the public HTTPS address before opening checkout.')
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        state = membership_state(user)
        if state['complimentary']:
            raise ValueError('Your complimentary access is active; no payment is needed.')
        if state['height'] is None:
            raise ValueError('Checkout awaits fresh block verification.')
        order = PaymentOrder.objects.filter(user=user, provider='stripe', applied_at_block__isnull=True).exclude(
            status__in=['Expired', 'failed']).order_by('-created_at').first()
        if order:
            if order.checkout_url and order.quote_expires > timezone.now():
                return order
            raise ValueError('Your previous card checkout is awaiting verification. Check its status before starting another.')
        order = PaymentOrder.objects.create(user=user, provider='stripe', amount_usd=state['total'],
            redemption=state['stage'] == 'redemption', quote_expires=timezone.now() + timedelta(hours=1))
    params = {'mode': 'payment', 'payment_method_types': ['card'], 'currency': 'usd',
        'client_reference_id': str(order.pk), 'metadata': {'orderId': str(order.pk), 'userId': str(user.pk)},
        'line_items': [{'price_data': {'currency': 'usd', 'unit_amount': int(order.amount_usd * 100),
            'product_data': {'name': 'Observatory publishing membership' + (' + redemption' if order.redemption else ''),
                'description': '4,320 Bitcoin blocks of publishing access. No automatic renewal.'}}, 'quantity': 1}],
        'expires_at': int(order.quote_expires.timestamp()),
        'success_url': base + reverse('stripe-return', args=[order.pk]),
        'cancel_url': base + reverse('membership')}
    try:
        session = client().v1.checkout.sessions.create(params, options={'idempotency_key': 'membership:' + str(order.pk)})
        destination = urlsplit(session.url)
        if destination.scheme != 'https' or destination.hostname != 'checkout.stripe.com' or destination.username:
            raise ValueError('Unexpected checkout destination.')
        # A webhook may already have credited the order; never overwrite settlement.
        PaymentOrder.objects.filter(pk=order.pk, applied_at_block__isnull=True).update(
            provider_invoice_id=session.id, checkout_url=session.url, status='New')
        order.refresh_from_db()
        return order
    except Exception as exc:
        PaymentOrder.objects.filter(pk=order.pk, applied_at_block__isnull=True).update(status='uncertain')
        raise ValueError('Checkout could not be confirmed. The order is retained for reconciliation; do not pay twice.') from exc


def fulfill(session):
    try:
        order_id = session.get('metadata', {}).get('orderId')
        order = PaymentOrder.objects.get(pk=order_id, provider='stripe')
    except (PaymentOrder.DoesNotExist, ValueError, TypeError):
        raise ValueError('Unknown membership order.')
    if (session.get('mode') != 'payment' or session.get('currency') != 'usd'
            or session.get('amount_total') != int(order.amount_usd * 100)
            or session.get('client_reference_id') != str(order.pk)
            or session.get('metadata', {}).get('userId') != str(order.user_id)
            or not session.get('id')
            or (order.provider_invoice_id and order.provider_invoice_id != session['id'])):
        raise ValueError('Checkout identity or amount mismatch.')
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=order.user_id)
        locked = PaymentOrder.objects.select_for_update().get(pk=order.pk)
        if locked.applied_at_block is not None:
            return
        if locked.provider_invoice_id and locked.provider_invoice_id != session['id']:
            raise ValueError('Checkout session mismatch.')
        locked.provider_invoice_id = session['id']
        checkout_url = session.get('url')
        if checkout_url:
            destination = urlsplit(checkout_url)
            if destination.scheme != 'https' or destination.hostname != 'checkout.stripe.com' or destination.username:
                raise ValueError('Unexpected checkout destination.')
            locked.checkout_url = checkout_url
        if session.get('payment_status') == 'paid' and session.get('status') == 'complete':
            height = chain_height()
            if height is None:
                locked.status = 'paid_pending_blocks'
            else:
                member = PublishingMembership.objects.filter(user_id=order.user_id).first()
                expiry = max(height, member.expires_at_block if member else height) + TERM
                PublishingMembership.objects.update_or_create(user_id=order.user_id, defaults={'expires_at_block': expiry})
                locked.applied_at_block = height
                locked.status = 'Settled'
        elif session.get('status') == 'expired':
            locked.status = 'Expired'
        else:
            locked.status = 'New'
        locked.save(update_fields=['provider_invoice_id', 'checkout_url', 'status', 'applied_at_block'])


def reconcile(order):
    if order.applied_at_block is not None or order.provider != 'stripe':
        return
    if not settings.STRIPE_SECRET_KEY:
        raise ValueError('Card payment verification is unavailable.')
    api = client().v1.checkout.sessions
    if order.provider_invoice_id:
        fulfill(api.retrieve(order.provider_invoice_id))
    else:
        # Recover uncertain create responses from Stripe without creating another charge.
        sessions = api.list({'created': {'gte': int(order.created_at.timestamp()) - 5}, 'limit': 100})
        for session in sessions.auto_paging_iter():
            if session.get('metadata', {}).get('orderId') == str(order.pk):
                fulfill(session)
                return
        raise ValueError('No checkout session confirmed yet; operator reconciliation is required.')
