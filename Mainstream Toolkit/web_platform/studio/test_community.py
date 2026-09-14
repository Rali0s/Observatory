from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .membership import membership_state, TERM, RENEWAL_WINDOW, FINAL_WINDOW
from .models import AuthorProfile, ChainTip, PaymentOrder, Publication, PublishingMembership, Project, Revision
from .payments import create_checkout, reconcile_order


class CommunityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.writer = get_user_model().objects.create_user('private-login-name', password='Testing-Passphrase-4382')
        cls.reader = get_user_model().objects.create_user('reader', password='Testing-Passphrase-5294')
        cls.author = AuthorProfile.objects.create(user=cls.writer, pen_name='Juniper Vale', bio='Fiction in quiet places.')

    def setUp(self):
        cache.clear()
        self.client.force_login(self.writer)

    def clock(self, height):
        ChainTip.objects.update_or_create(pk=1, defaults={'height': height+5, 'block_hash': 'a'*64, 'observed_at': timezone.now()})

    def member(self, expiry=10000):
        return PublishingMembership.objects.create(user=self.writer, expires_at_block=expiry)

    def publication(self):
        return Publication.objects.create(author=self.author, title='The Glass Garden', excerpt='A gate left open.',
            body='Mara chose to return. <script>alert(1)</script>', kind='story')

    def test_exact_block_boundaries_and_price(self):
        self.member()
        for height, stage, remaining, price in [(9999, 'active', 1, '18'), (10000, 'renewal', 4320, '18'),
            (14319, 'renewal', 1, '18'), (14320, 'final', 2160, '18'), (16479, 'final', 1, '18'),
            (16480, 'redemption', None, '45')]:
            self.clock(height)
            state = membership_state(self.writer)
            self.assertEqual(state['stage'], stage)
            self.assertEqual(state['remaining'], remaining)
            self.assertEqual(state['total'], Decimal(price))

    def test_stale_clock_never_invents_a_deadline(self):
        self.member()
        self.clock(11000)
        ChainTip.objects.update(observed_at=timezone.now()-timedelta(minutes=6))
        self.assertEqual(membership_state(self.writer)['stage'], 'syncing')
        self.assertRedirects(self.client.get(reverse('publish')), reverse('lockout'))
        self.assertEqual(self.client.get(reverse('library')).status_code, 200)

    def test_signup_creates_a_free_account(self):
        self.client.logout()
        response = self.client.post(reverse('signup'), {'username': 'new-writer', 'pen_name': 'New Voice',
            'password1': 'Another-Passphrase-9375', 'password2': 'Another-Passphrase-9375'})
        self.assertRedirects(response, reverse('account'))
        user = get_user_model().objects.get(username='new-writer')
        self.assertEqual(user.author_profile.pen_name, 'New Voice')
        self.assertFalse(PublishingMembership.objects.filter(user=user).exists())
        self.assertEqual(self.client.post(reverse('library'), {'title': 'Free manuscript'}).status_code, 302)

    def test_public_feed_exposes_only_public_text(self):
        post = self.publication()
        self.client.logout()
        response = self.client.get(reverse('feed'))
        self.assertContains(response, 'The Glass Garden')
        self.assertNotContains(response, self.writer.username)
        response = self.client.get(reverse('read', args=[post.pk]))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        post.is_visible = False
        post.save()
        self.assertNotContains(self.client.get(reverse('feed')), 'The Glass Garden')
        self.assertEqual(self.client.get(reverse('read', args=[post.pk])).status_code, 404)

    def test_preview_publish_and_expiry_gate(self):
        self.member()
        self.clock(9990)
        data = {'title': 'A selected passage', 'kind': 'excerpt', 'channel': 'fiction', 'hashtags':'#quiet', 'excerpt': 'A window opens.',
                'body': 'This exact text is public.', 'rights_confirmed': 'on', 'action': 'preview'}
        self.assertContains(self.client.post(reverse('publish'), data), 'NOT PUBLISHED')
        self.assertEqual(Publication.objects.count(), 0)
        data['action'] = 'edit'
        self.assertContains(self.client.post(reverse('publish'), data), 'Preview publication')
        data['action'] = 'publish'
        self.assertEqual(self.client.post(reverse('publish'), data).status_code, 302)
        self.clock(10000)
        self.assertRedirects(self.client.post(reverse('publish'), data), reverse('lockout'))
        self.assertEqual(Publication.objects.count(), 1)
        self.assertContains(self.client.get(reverse('feed')), 'A selected passage')

    def test_foreign_revision_cannot_be_attached(self):
        self.member()
        self.clock(9990)
        project = Project.objects.create(owner=self.reader, title='Secret project')
        revision = Revision.objects.create(project=project, label='Secret', manuscript='Private', fingerprint='b'*64,
            profile='general', word_count=1, engine_version='1.0', analysis={})
        response = self.client.post(reverse('publish'), {'title': 'Leak', 'kind': 'story', 'excerpt': 'x', 'body': 'x',
            'source_revision': revision.pk, 'rights_confirmed': 'on', 'action': 'publish'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Publication.objects.count(), 0)

    def test_reader_bookmarks_follows_and_reports(self):
        post = self.publication()
        self.client.force_login(self.reader)
        self.client.post(reverse('follow', args=[self.author.pk]))
        self.assertContains(self.client.get(reverse('feed'), {'tab': 'following'}), post.title)
        self.client.post(reverse('bookmark', args=[post.pk]))
        self.assertContains(self.client.get(reverse('feed'), {'tab': 'saved'}), post.title)
        self.client.post(reverse('report', args=[post.pk]), {'reason': 'Please review this.'})
        self.assertEqual(post.publicationreport_set.count(), 1)
        self.assertEqual(self.client.post(reverse('withdraw', args=[post.pk])).status_code, 404)

    def test_redemption_retains_account_and_publications(self):
        self.member()
        self.clock(20000)
        post = self.publication()
        response = self.client.get(reverse('lockout'))
        self.assertContains(response, '$45.00')
        self.assertContains(response, 'retained')
        self.assertEqual(self.client.get(reverse('account')).status_code, 200)
        self.assertEqual(self.client.get(reverse('library')).status_code, 200)
        self.assertEqual(self.client.get(reverse('read', args=[post.pk])).status_code, 200)
        self.client.post(reverse('withdraw', args=[post.pk]))
        self.assertTrue(get_user_model().objects.filter(pk=self.writer.pk).exists())
        self.assertTrue(Publication.objects.filter(pk=post.pk).exists())

    @patch('studio.payments.provider_request')
    def test_settlement_extends_once_and_preserves_unused_blocks(self, provider):
        self.member()
        self.clock(9900)
        order = PaymentOrder.objects.create(user=self.writer, amount_usd='18.00', provider_invoice_id='invoice-1')
        provider.return_value = {'id': 'invoice-1', 'currency': 'USD', 'amount': '18.00', 'status': 'Settled',
            'metadata': {'orderId': str(order.id)}}
        reconcile_order(order)
        reconcile_order(order)  # stale caller instance also must be idempotent
        self.assertEqual(PublishingMembership.objects.get(user=self.writer).expires_at_block, 10000+TERM)

    @patch('studio.payments.provider_request')
    def test_underpaid_or_unsettled_invoice_cannot_activate(self, provider):
        self.clock(9900)
        order = PaymentOrder.objects.create(user=self.writer, amount_usd='45.00', redemption=True, provider_invoice_id='invoice-2')
        provider.return_value = {'id': 'invoice-2', 'currency': 'USD', 'amount': '18.00', 'status': 'Settled', 'metadata': {'orderId': str(order.id)}}
        with self.assertRaises(ValueError):
            reconcile_order(order)
        provider.return_value['amount'] = '45.00'
        provider.return_value['status'] = 'Processing'
        reconcile_order(order)
        self.assertFalse(PublishingMembership.objects.filter(user=self.writer).exists())
        self.clock(20000)
        provider.return_value['status'] = 'Settled'
        reconcile_order(order)
        self.assertEqual(PublishingMembership.objects.get(user=self.writer).expires_at_block, 20000+TERM)

    def test_unconfigured_checkout_never_creates_payment(self):
        self.clock(9000)
        with self.assertRaises(ValueError):
            create_checkout(self.writer)
        self.assertEqual(PaymentOrder.objects.count(), 0)
