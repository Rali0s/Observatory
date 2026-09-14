"""Exercise production row locks on PostgreSQL, not SQLite's global write lock."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
import base64
from coincurve import PrivateKey
from embit import ec, script
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import Client, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from .models import ChainTip, PaymentOrder, PublishingMembership, WalletIdentity
from .stripe_payments import fulfill
from .wallet_auth import message_hash


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row-lock test')
class ConcurrencyTests(TransactionTestCase):
    def run_concurrently(self, operation):
        barrier = Barrier(2)
        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            return [future.result(timeout=15) for future in futures]

    def test_concurrent_duplicate_payment_only_grants_one_term(self):
        user = get_user_model().objects.create_user('payer')
        ChainTip.objects.create(height=900005, block_hash='a' * 64, observed_at=timezone.now())
        order = PaymentOrder.objects.create(user=user, provider='stripe', amount_usd=18, provider_invoice_id='cs_concurrent')
        session = {'id': 'cs_concurrent', 'mode': 'payment', 'currency': 'usd', 'amount_total': 1800,
            'metadata': {'orderId': str(order.pk), 'userId': str(user.pk)}, 'client_reference_id': str(order.pk),
            'status': 'complete', 'payment_status': 'paid'}
        self.run_concurrently(lambda: fulfill(session))
        self.assertEqual(PublishingMembership.objects.get(user=user).expires_at_block, 904320)

    def test_concurrent_wallet_replay_succeeds_exactly_once(self):
        key = PrivateKey(bytes.fromhex('66' * 32))
        address = script.p2wpkh(ec.PublicKey.parse(key.public_key.format())).address()
        client = Client()
        proof = client.post(reverse('wallet-challenge'), {'address': address}).json()
        raw = key.sign_recoverable(message_hash(proof['message']), hasher=None)
        signature = base64.b64encode(bytes([31 + raw[-1]]) + raw[:64]).decode()
        cookies = client.cookies.copy()
        def submit():
            caller = Client()
            caller.cookies = cookies.copy()
            return caller.post(reverse('wallet-authenticate'), {'challenge_id': proof['id'], 'signature': signature}).status_code
        results = self.run_concurrently(submit)
        self.assertEqual(sorted(results), [200, 400])
        self.assertEqual(WalletIdentity.objects.count(), 1)
