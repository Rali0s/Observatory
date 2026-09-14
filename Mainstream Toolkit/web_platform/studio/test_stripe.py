import hashlib
import hmac
import json
import time
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from django.utils import timezone
from .models import ChainTip, PaymentOrder, PublishingMembership
from . import stripe_payments as payments


@override_settings(STRIPE_ENABLED=True, STRIPE_SECRET_KEY='sk_test_fake', STRIPE_WEBHOOK_SECRET='whsec_testing', PUBLIC_BASE_URL='https://observate.up.railway.app')
class StripeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('member')
        ChainTip.objects.create(height=900005, block_hash='a' * 64, observed_at=timezone.now())
        self.order = PaymentOrder.objects.create(user=self.user, provider='stripe', amount_usd='18.00', provider_invoice_id='cs_test_one')

    def session(self, **changes):
        result = {'id': 'cs_test_one', 'mode': 'payment', 'currency': 'usd', 'amount_total': 1800,
            'client_reference_id': str(self.order.pk), 'metadata': {'orderId': str(self.order.pk), 'userId': str(self.user.pk)},
            'status': 'complete', 'payment_status': 'paid'}
        result.update(changes)
        return result

    def test_paid_exact_order_extends_membership_once(self):
        PublishingMembership.objects.create(user=self.user, expires_at_block=901000)
        payments.fulfill(self.session())
        payments.fulfill(self.session())
        self.assertEqual(PublishingMembership.objects.get(user=self.user).expires_at_block, 905320)
        payments.fulfill(self.session(status='expired', payment_status='unpaid'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'Settled')

    def test_no_credit_for_unpaid_or_altered_identity_amount_currency(self):
        payments.fulfill(self.session(payment_status='unpaid'))
        self.assertFalse(PublishingMembership.objects.exists())
        for changes in ({'amount_total': 1}, {'currency': 'eur'}, {'client_reference_id': 'other'}, {'id': 'cs_other'}, {'mode': 'subscription'}):
            with self.assertRaises(ValueError):
                payments.fulfill(self.session(**changes))
        self.assertFalse(PublishingMembership.objects.exists())

    def test_payment_retained_until_fresh_block_height(self):
        ChainTip.objects.all().delete()
        payments.fulfill(self.session())
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid_pending_blocks')
        self.assertFalse(PublishingMembership.objects.exists())
        ChainTip.objects.create(height=910005, block_hash='b' * 64, observed_at=timezone.now())
        payments.fulfill(self.session())
        self.assertEqual(PublishingMembership.objects.get(user=self.user).expires_at_block, 914320)

    @patch('studio.stripe_payments.client')
    def test_checkout_uses_server_price_idempotency_and_reuses_open_order(self, client):
        self.order.delete()
        api = client.return_value.v1.checkout.sessions
        api.create.return_value = Mock(id='cs_test_created', url='https://checkout.stripe.com/c/pay/example')
        order = payments.create_checkout(self.user)
        self.assertEqual(payments.create_checkout(self.user).pk, order.pk)
        api.create.assert_called_once()
        args = api.create.call_args
        self.assertEqual(args.args[0]['line_items'][0]['price_data']['unit_amount'], 1800)
        self.assertEqual(args.kwargs['options']['idempotency_key'], 'membership:' + str(order.pk))

    @patch('studio.stripe_payments.client')
    def test_redemption_cost_is_45_dollars(self, client):
        self.order.delete()
        PublishingMembership.objects.create(user=self.user, expires_at_block=880000)
        client.return_value.v1.checkout.sessions.create.return_value = Mock(id='cs_redeem', url='https://checkout.stripe.com/c/pay/redeem')
        self.assertEqual(payments.create_checkout(self.user).amount_usd, 45)

    @patch('studio.stripe_payments.client')
    def test_uncertain_checkout_does_not_create_second_payment(self, client):
        self.order.delete()
        client.return_value.v1.checkout.sessions.create.side_effect = TimeoutError()
        with self.assertRaises(ValueError): payments.create_checkout(self.user)
        with self.assertRaises(ValueError): payments.create_checkout(self.user)
        self.assertEqual(PaymentOrder.objects.count(), 1)
        client.return_value.v1.checkout.sessions.create.assert_called_once()

    @patch('studio.stripe_payments.client')
    def test_signed_webhook_required_and_duplicates_credit_once(self, client):
        event = {'id': 'evt_1', 'type': 'checkout.session.completed', 'data': {'object': self.session()}}
        body = json.dumps(event).encode()
        timestamp = int(time.time())
        signature = hmac.new(b'whsec_testing', str(timestamp).encode() + b'.' + body, hashlib.sha256).hexdigest()
        client.return_value.v1.checkout.sessions.retrieve.return_value = self.session()
        csrf = Client(enforce_csrf_checks=True)
        url = reverse('stripe-webhook')
        self.assertEqual(csrf.post(url, body, content_type='application/json').status_code, 400)
        for _ in range(2):
            self.assertEqual(csrf.post(url, body, content_type='application/json', HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={signature}').status_code, 200)
        self.assertEqual(PublishingMembership.objects.get(user=self.user).expires_at_block, 904320)

    def test_other_users_cannot_verify_or_view_order(self):
        self.client.force_login(get_user_model().objects.create_user('other'))
        self.assertEqual(self.client.get(reverse('stripe-return', args=[self.order.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('check-payment', args=[self.order.pk])).status_code, 404)
