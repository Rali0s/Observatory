import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from .models import PaymentOrder
from .stripe_payments import create_checkout, fulfill, reconcile


@login_required
@require_POST
def checkout(request):
    if not cache.add(f'stripe-checkout:{request.user.pk}', True, 10):
        messages.info(request, 'Please wait a moment before opening checkout again.')
        return redirect('membership')
    try:
        return redirect(create_checkout(request.user).checkout_url)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('membership')


@login_required
@never_cache
@require_GET
def returned(request, order_id):
    order = get_object_or_404(PaymentOrder, pk=order_id, user=request.user, provider='stripe')
    if cache.add('stripe-return:' + str(order.pk), True, 15):
        try:
            reconcile(order)
        except Exception:
            messages.info(request, 'Payment verification is pending. Your order is retained and will be checked automatically.')
    return redirect('membership')


@csrf_exempt
@require_POST
def webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=503)
    try:
        event = stripe.Webhook.construct_event(request.body, request.headers.get('Stripe-Signature', ''), settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponse(status=400)
    if event['type'] in ('checkout.session.completed', 'checkout.session.async_payment_succeeded', 'checkout.session.expired'):
        try:
            # Retrieve current provider state so out-of-order events cannot regress an order.
            session = event['data']['object']
            if not session.get('metadata', {}).get('orderId'):
                return HttpResponse(status=200)
            from .stripe_payments import client
            fulfill(client().v1.checkout.sessions.retrieve(session['id']))
        except (ValueError, ValidationError):
            return HttpResponse(status=400)
        except Exception:
            return HttpResponse(status=503)
    return HttpResponse(status=200)
