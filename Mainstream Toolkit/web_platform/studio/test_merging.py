import base64
from datetime import timedelta
from decimal import Decimal
from coincurve import PrivateKey
from embit import ec, script
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from . import models as m
from .merging import primary_account, merge_accounts, lock_order
from .wallet_auth import message_hash
from .stripe_payments import fulfill


class MergeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.first=get_user_model().objects.create_user('writer',password='Writer-long-pass-4827')
        self.second=get_user_model().objects.create_user('wallet-account',password='Wallet-long-pass-4827')
        self.p1=m.AuthorProfile.objects.create(user=self.first,pen_name='Writer')
        self.p2=m.AuthorProfile.objects.create(user=self.second,pen_name='Wallet writer',bio='Keep this biography')
        self.client.force_login(self.first)
        self.key=PrivateKey(bytes.fromhex('77'*32))
        self.address=script.p2wpkh(ec.PublicKey.parse(self.key.public_key.format())).address()

    def attempt(self):
        self.client.get(reverse('account-merge'))
        return m.MergeAttempt.objects.get(pk=self.client.session['merge_attempt'])

    def passwords(self):
        attempt=self.attempt()
        self.client.post(reverse('account-merge'),{'slot':'owner','username':'writer','password':'Writer-long-pass-4827'})
        self.client.post(reverse('account-merge'),{'slot':'other','username':'wallet-account','password':'Wallet-long-pass-4827'})
        attempt.refresh_from_db()
        return attempt

    def confirm(self,target=None):
        return self.client.post(reverse('account-merge-confirm'),{'confirm':'yes','target':(target or self.first).pk})

    def test_priority_admin_then_paid_then_wallet(self):
        m.WalletIdentity.objects.create(user=self.second,address=self.address)
        self.assertEqual(primary_account(self.first,self.second),self.second)
        m.PublishingMembership.objects.create(user=self.first,expires_at_block=123)
        self.assertEqual(primary_account(self.first,self.second),self.first)
        self.second.is_staff=True; self.second.save()
        self.assertEqual(primary_account(self.first,self.second),self.second)

    def test_password_merge_moves_content_preserves_logins_and_retires_old_sessions(self):
        project=m.Project.objects.create(owner=self.second,title='Private manuscript')
        post=m.Publication.objects.create(author=self.p2,title='Published',body='Body',kind='story')
        m.WalletIdentity.objects.create(user=self.second,address=self.address)
        # Keep admin identity even though the other account owns the wallet.
        self.first.is_staff=True;self.first.is_superuser=True;self.first.save()
        old=Client(); old.force_login(self.second)
        self.passwords()
        self.assertFalse(m.AccountMerge.objects.exists())
        response=self.confirm()
        self.assertRedirects(response,reverse('account'))
        project.refresh_from_db();post.refresh_from_db();self.second.refresh_from_db()
        self.assertEqual(project.owner,self.first)
        self.assertEqual(post.author,self.p1)
        self.assertFalse(self.second.is_active)
        self.assertEqual(m.WalletIdentity.objects.get(address=self.address).user,self.first)
        self.assertRedirects(old.get(reverse('account')),reverse('login')+'?next='+reverse('account'))
        self.assertTrue(Client().login(username='writer',password='Writer-long-pass-4827'))
        alias=Client();self.assertTrue(alias.login(username='wallet-account',password='Wallet-long-pass-4827'))
        self.assertEqual(alias.session['_auth_user_id'],str(self.first.pk))
        self.assertRedirects(self.client.get(reverse('author',args=[self.p2.pk])),reverse('author',args=[self.p1.pk]))
        self.confirm();self.assertEqual(m.AccountMerge.objects.count(),1)

    def test_missing_wrong_expired_and_changed_proofs_cannot_merge(self):
        attempt=self.attempt()
        self.confirm();self.assertFalse(m.AccountMerge.objects.exists())
        self.client.post(reverse('account-merge'),{'slot':'other','username':'wallet-account','password':'wrong'})
        self.confirm();self.assertFalse(m.AccountMerge.objects.exists())
        attempt=self.passwords()
        attempt.expires_at=timezone.now()-timedelta(seconds=1);attempt.save()
        self.confirm();self.assertFalse(m.AccountMerge.objects.exists())
        self.passwords()
        self.second.set_password('Changed-password-3827');self.second.save()
        self.confirm();self.assertFalse(m.AccountMerge.objects.exists())

    def test_both_accounts_cannot_be_the_same_or_cross_session(self):
        attempt=self.attempt()
        response=self.client.post(reverse('account-merge'),{'slot':'other','username':'writer','password':'Writer-long-pass-4827'})
        self.assertContains(response,'different account')
        attempt=self.passwords()
        with self.assertRaises(ValueError):merge_accounts(attempt.pk,self.first.pk,'another-session',self.first.pk)
        self.assertFalse(m.AccountMerge.objects.exists())
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.first)
        self.assertEqual(csrf.post(reverse('account-merge-confirm'),{'confirm':'yes','target':self.first.pk}).status_code,403)

    def test_wallet_proof_and_conflict_are_actionable_without_automatic_merge(self):
        m.WalletIdentity.objects.create(user=self.second,address=self.address)
        attempt=self.attempt()
        proof=self.client.post(reverse('wallet-challenge'),{'address':self.address}).json()
        def sign(proof):
            raw=self.key.sign_recoverable(message_hash(proof['message']),hasher=None)
            return base64.b64encode(bytes([31+raw[-1]])+raw[:64]).decode()
        response=self.client.post(reverse('wallet-authenticate'),{'challenge_id':proof['id'],'signature':sign(proof)})
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json()['merge_url'],reverse('account-merge'))
        self.assertEqual(m.WalletIdentity.objects.get(address=self.address).user,self.second)
        proof=self.client.post(reverse('wallet-challenge'),{'address':self.address,'merge_attempt':attempt.pk,'merge_slot':'other'}).json()
        self.assertIn('account merge',proof['message'])
        response=self.client.post(reverse('wallet-authenticate'),{'challenge_id':proof['id'],'signature':sign(proof)})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.session['_auth_user_id'],str(self.first.pk))
        self.assertFalse(m.AccountMerge.objects.exists())
        self.client.post(reverse('account-merge'),{'slot':'owner','username':'writer','password':'Writer-long-pass-4827'})
        self.confirm(self.second)
        self.assertEqual(m.AccountMerge.objects.get().target,self.second)
        # New wallet sign-in resolves the same consolidated account.
        guest=Client()
        proof=guest.post(reverse('wallet-challenge'),{'address':self.address}).json()
        response=guest.post(reverse('wallet-authenticate'),{'challenge_id':proof['id'],'signature':sign(proof)})
        self.assertEqual(response.status_code,200)
        self.assertEqual(guest.session['_auth_user_id'],str(self.second.pk))

    def test_paid_and_invite_time_combine_and_original_stripe_identity_survives(self):
        now=timezone.now()
        m.ChainTip.objects.create(height=900005,block_hash='a'*64,observed_at=now)
        m.PublishingMembership.objects.create(user=self.first,expires_at_block=900100)
        m.PublishingMembership.objects.create(user=self.second,expires_at_block=900200)
        m.ComplimentaryAccess.objects.create(user=self.first,expires_at=now+timedelta(days=10))
        m.ComplimentaryAccess.objects.create(user=self.second,lifetime=True)
        order=m.PaymentOrder.objects.create(user=self.second,provider='stripe',amount_usd=Decimal('18'),provider_invoice_id='cs_merge')
        self.passwords(); self.confirm()
        self.assertEqual(m.PublishingMembership.objects.get(user=self.first).expires_at_block,900300)
        self.assertTrue(m.ComplimentaryAccess.objects.get(user=self.first).lifetime)
        order.refresh_from_db()
        self.assertEqual(order.user,self.first);self.assertEqual(order.billing_user_id,self.second.pk)
        session={'id':'cs_merge','mode':'payment','currency':'usd','amount_total':1800,
            'metadata':{'orderId':str(order.pk),'userId':str(self.second.pk)},'client_reference_id':str(order.pk),
            'status':'complete','payment_status':'paid'}
        fulfill(session);fulfill(session)
        self.assertEqual(m.PublishingMembership.objects.get(user=self.first).expires_at_block,904620)
        self.assertFalse(m.PublishingMembership.objects.filter(user=self.second).exists())

    def test_duplicate_relationships_and_invite_history_are_preserved(self):
        third=get_user_model().objects.create_user('third')
        profile=m.AuthorProfile.objects.create(user=third,pen_name='Third')
        post=m.Publication.objects.create(author=profile,title='Read',body='Text',kind='story')
        inviter=get_user_model().objects.create_user('inviter',is_staff=True)
        from .invites import issue,redeem
        _,code=issue(inviter,label='Both',kind='three_months',max_uses=2)
        for user in [self.first,self.second]:
            m.Bookmark.objects.create(user=user,publication=post)
            m.Upvote.objects.create(user=user,publication=post)
            m.Follow.objects.create(user=user,author=profile)
            redeem(user,code)
        m.Follow.objects.create(user=third,author=self.p1)
        m.Follow.objects.create(user=third,author=self.p2)
        self.passwords();self.confirm()
        self.assertEqual(m.Bookmark.objects.filter(user=self.first).count(),1)
        self.assertEqual(m.Upvote.objects.filter(user=self.first).count(),1)
        self.assertEqual(m.Follow.objects.filter(user=third).count(),1)
        self.assertEqual(m.InviteRedemption.objects.count(),2)
        with self.assertRaises(ValueError):redeem(self.first,code)

    def test_retired_alias_does_not_bypass_disabled_primary(self):
        self.passwords();self.confirm()
        self.first.is_active=False;self.first.save()
        self.assertFalse(Client().login(username='wallet-account',password='Wallet-long-pass-4827'))

    def test_cancel_and_unlinked_wallet_cannot_merge(self):
        attempt=self.passwords()
        self.client.post(reverse('account-merge-cancel'))
        with self.assertRaises(ValueError):merge_accounts(attempt.pk,self.first.pk,attempt.session_hash,self.first.pk)
        self.assertFalse(m.AccountMerge.objects.exists())

    def test_stale_payment_worker_must_retry_after_merge(self):
        order=m.PaymentOrder.objects.create(user=self.second,provider='stripe',amount_usd=18)
        self.passwords();self.confirm()
        with self.assertRaises(ValueError):lock_order(order)
        order.refresh_from_db()
        self.assertEqual(lock_order(order).user,self.first)

    def test_old_profile_follow_targets_consolidated_author(self):
        self.passwords();self.confirm()
        reader=get_user_model().objects.create_user('new-reader')
        self.client.force_login(reader)
        self.client.post(reverse('follow',args=[self.p2.pk]))
        self.assertTrue(m.Follow.objects.filter(user=reader,author=self.p1).exists())
        self.assertFalse(m.Follow.objects.filter(user=reader,author=self.p2).exists())

    def test_repeated_merges_flatten_password_aliases(self):
        self.passwords();self.confirm()
        admin=get_user_model().objects.create_user('final-admin',password='Final-Admin-4872',is_staff=True)
        self.client.get(reverse('account-merge'))
        self.client.post(reverse('account-merge'),{'slot':'owner','username':'wallet-account','password':'Wallet-long-pass-4827'})
        self.client.post(reverse('account-merge'),{'slot':'other','username':'final-admin','password':'Final-Admin-4872'})
        self.confirm(admin)
        for username,password in [('writer','Writer-long-pass-4827'),('wallet-account','Wallet-long-pass-4827')]:
            caller=Client();self.assertTrue(caller.login(username=username,password=password))
            self.assertEqual(caller.session['_auth_user_id'],str(admin.pk))
        self.assertEqual(m.AccountMerge.objects.filter(target=admin).count(),2)
