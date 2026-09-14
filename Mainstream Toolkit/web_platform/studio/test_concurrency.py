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

    def test_concurrent_invite_last_use_cannot_be_oversubscribed(self):
        from .invites import issue, redeem
        from .models import InviteRedemption
        admin = get_user_model().objects.create_user('inviter', is_staff=True)
        users = [get_user_model().objects.create_user('recipient1'), get_user_model().objects.create_user('recipient2')]
        invitation, code = issue(admin, label='Last pass', kind='lifetime')
        from queue import Queue
        recipients = Queue()
        for user in users: recipients.put(user)
        def attempt():
            try:
                redeem(recipients.get_nowait(), code)
                return 'accepted'
            except ValueError:
                return 'rejected'
        self.assertEqual(sorted(self.run_concurrently(attempt)), ['accepted', 'rejected'])
        invitation.refresh_from_db()
        self.assertEqual(invitation.uses, 1)
        self.assertEqual(InviteRedemption.objects.count(), 1)

    def test_concurrent_merge_only_retires_account_once(self):
        from datetime import timedelta
        from .models import MergeAttempt,AccountMerge,Project
        from .merging import merge_accounts
        first=get_user_model().objects.create_user('merge1',password='First-pass-123')
        second=get_user_model().objects.create_user('merge2',password='Second-pass-123')
        project=Project.objects.create(owner=second,title='Keep this')
        attempt=MergeAttempt.objects.create(owner=first,other=second,session_hash='session',
            owner_auth_hash=first.get_session_auth_hash(),other_auth_hash=second.get_session_auth_hash(),
            expires_at=timezone.now()+timedelta(minutes=10))
        def merge():
            try:
                merge_accounts(attempt.pk,first.pk,'session',first.pk)
                return 'merged'
            except ValueError:return 'rejected'
        self.assertEqual(sorted(self.run_concurrently(merge)),['merged','rejected'])
        self.assertEqual(AccountMerge.objects.count(),1)
        project.refresh_from_db();self.assertEqual(project.owner_id,first.pk)

    def test_payment_arriving_during_merge_credits_survivor_once(self):
        from datetime import timedelta
        from queue import Queue
        from .models import MergeAttempt,AccountMerge
        from .merging import merge_accounts
        first=get_user_model().objects.create_user('keep-admin',is_staff=True)
        second=get_user_model().objects.create_user('merge-payer')
        ChainTip.objects.create(height=900005,block_hash='a'*64,observed_at=timezone.now())
        order=PaymentOrder.objects.create(user=second,provider='stripe',amount_usd=18,provider_invoice_id='cs_merge_race')
        payload={'id':'cs_merge_race','mode':'payment','currency':'usd','amount_total':1800,
            'metadata':{'orderId':str(order.pk),'userId':str(second.pk)},'client_reference_id':str(order.pk),
            'status':'complete','payment_status':'paid'}
        attempt=MergeAttempt.objects.create(owner=first,other=second,session_hash='session',
            owner_auth_hash=first.get_session_auth_hash(),other_auth_hash=second.get_session_auth_hash(),
            expires_at=timezone.now()+timedelta(minutes=10))
        operations=Queue()
        operations.put(lambda:merge_accounts(attempt.pk,first.pk,'session',first.pk))
        def credit():
            try:fulfill(payload)
            except ValueError:fulfill(payload)  # A stale worker snapshot retries against the new owner.
        operations.put(credit)
        self.run_concurrently(lambda:operations.get_nowait()())
        fulfill(payload)
        self.assertEqual(AccountMerge.objects.count(),1)
        self.assertEqual(PublishingMembership.objects.get(user=first).expires_at_block,904320)
        self.assertFalse(PublishingMembership.objects.filter(user=second).exists())
