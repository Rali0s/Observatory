from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from . import invites, stripe_payments, payments, direct_payments
from .access import require_access, word_limit
from .membership import membership_state
from .models import ComplimentaryAccess, Invitation, InviteSettings, InviteRedemption, Project, PublishingMembership
from .storage import save_content, storage_state


class InviteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_user('admin', is_staff=True)
        self.user = get_user_model().objects.create_user('writer')

    def issue(self, **kwargs):
        return invites.issue(self.admin, label='Launch readers', kind=Invitation.Kind.THREE_MONTHS, **kwargs)

    def test_default_admin_only_and_explicit_member_permission_switch(self):
        self.assertTrue(invites.can_issue(self.admin))
        with self.assertRaises(PermissionDenied):
            invites.issue(self.user, label='Unauthorized', kind='lifetime')
        self.user.user_permissions.add(Permission.objects.get(codename='issue_invitations'))
        self.assertFalse(invites.can_issue(self.user))
        InviteSettings.objects.create(member_issuers_enabled=True)
        self.assertTrue(invites.can_issue(self.user))
        other = get_user_model().objects.create_user('other')
        self.assertFalse(invites.can_issue(other))
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('invites')).status_code, 403)
        self.assertEqual(self.client.post(reverse('invite-settings'), {'enabled':'yes'}).status_code, 403)

    def test_three_calendar_months_hashing_replay_and_capacity(self):
        item, code = self.issue()
        self.assertNotIn(code, item.code_hash)
        now = datetime(2026, 8, 31, 10, tzinfo=dt_timezone.utc)
        with patch('studio.invites.timezone.now', return_value=now):
            access = invites.redeem(self.user, code.lower())
        self.assertEqual(access.expires_at, datetime(2026, 11, 30, 10, tzinfo=dt_timezone.utc))
        with self.assertRaisesMessage(ValueError, 'already redeemed'):
            invites.redeem(self.user, code)
        other = get_user_model().objects.create_user('other')
        with self.assertRaisesMessage(ValueError, 'no uses remaining'):
            invites.redeem(other, code)
        self.assertEqual(InviteRedemption.objects.count(), 1)

    def test_stacking_lifetime_upgrade_and_no_admin_privileges(self):
        _, first = self.issue()
        initial = invites.redeem(self.user, first)
        initial_end = initial.expires_at
        _, second = self.issue()
        extended = invites.redeem(self.user, second)
        self.assertEqual(extended.expires_at, invites.add_three_months(initial_end))
        _, lifetime = invites.issue(self.admin, label='Founders', kind='lifetime')
        invites.redeem(self.user, lifetime)
        self.assertEqual(membership_state(self.user)['stage'], 'lifetime')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(invites.can_issue(self.user))
        self.assertIsNone(ComplimentaryAccess.objects.get(user=self.user).expires_at)

    def test_expiry_revocation_and_existing_paid_term_unchanged(self):
        paid = PublishingMembership.objects.create(user=self.user, expires_at_block=900000)
        item, code = self.issue()
        item.enabled = False; item.save()
        with self.assertRaises(ValueError): invites.redeem(self.user, code)
        item.enabled = True; item.redeem_before = timezone.now()-timedelta(seconds=1); item.save()
        with self.assertRaises(ValueError): invites.redeem(self.user, code)
        item.redeem_before = None; item.save()
        invites.redeem(self.user, code)
        item.enabled = False; item.save()
        self.assertTrue(membership_state(self.user)['can_publish'])
        ComplimentaryAccess.objects.filter(user=self.user).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertFalse(membership_state(self.user)['can_publish'])
        paid.refresh_from_db(); self.assertEqual(paid.expires_at_block, 900000)

    @override_settings(STORAGE_QUOTA_BYTES=1)
    def test_admin_unlimited_and_normal_user_limits(self):
        self.assertTrue(membership_state(self.admin)['can_publish'])
        self.assertIsNone(word_limit(require_access(self.admin)))
        self.assertIsNone(require_access(self.admin).max_projects)
        save_content(self.admin, lambda: Project.objects.create(owner=self.admin, title='Large enough'))
        self.assertTrue(storage_state(self.admin)['unlimited'])
        with self.assertRaises(ValueError):
            save_content(self.user, lambda: Project.objects.create(owner=self.user, title='Large enough'))
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('membership')), 'Unlimited admin access')
        self.assertNotContains(self.client.get(reverse('membership')), 'Pay by card')
        self.assertContains(self.client.get(reverse('storage')), 'Unlimited admin allowance')
        foreign = Project.objects.create(owner=self.user, title='Private')
        self.assertEqual(self.client.get(reverse('project', args=[foreign.pk])).status_code, 404)

    @override_settings(STRIPE_ENABLED=True, STRIPE_SECRET_KEY='test', STRIPE_WEBHOOK_SECRET='test',
        PUBLIC_BASE_URL='https://example.com', BTCPAY_URL='https://example.com', BTCPAY_STORE_ID='test',
        BTCPAY_API_KEY='test', DIRECT_BITCOIN_ENABLED=True)
    @patch('studio.direct_payments.spot_price', return_value=100000)
    def test_no_checkout_for_admins_or_active_invites(self, price):
        _, code = self.issue(); invites.redeem(self.user, code)
        for user in [self.admin, self.user]:
            for create in [stripe_payments.create_checkout, payments.create_checkout, direct_payments.create_order]:
                with self.assertRaisesMessage(ValueError, 'no payment is needed'):
                    create(user)

    def test_dashboard_redeem_csrf_and_revocation_ownership(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('invites'), {'label':'Three months','kind':'three_months','max_uses':2})
        self.assertEqual(response.status_code, 200)
        code = response.context['code']
        self.assertTrue(code)
        self.assertNotContains(self.client.get(reverse('invites')), code)
        InviteSettings.objects.create(member_issuers_enabled=True)
        self.user.user_permissions.add(Permission.objects.get(codename='issue_invitations'))
        self.client.force_login(self.user)
        item = Invitation.objects.get()
        self.assertEqual(self.client.post(reverse('invite-revoke',args=[item.pk])).status_code,404)
        self.client.post(reverse('invite-redeem'), {'code':code})
        self.assertTrue(membership_state(self.user)['can_publish'])
        secure = Client(enforce_csrf_checks=True); secure.force_login(self.admin)
        self.assertEqual(secure.post(reverse('invites'), {'label':'Forged'}).status_code,403)

    def test_admin_chapter_analysis_and_project_creation_have_no_plan_quota(self):
        from .models import DraftChapter
        for number in range(11):
            Project.objects.create(owner=self.admin, title=f'Project {number}')
        self.client.force_login(self.admin)
        response = self.client.post(reverse('library'), {'title':'Beyond free quota'})
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title='Beyond free quota')
        DraftChapter.objects.create(project=project, title='Opening', markdown='Ada chose hope by the river.')
        with override_settings(OBSERVATORY_MAX_WORDS=1):
            response = self.client.post(reverse('chapter-snapshot', args=[project.pk]), {'profile':'general'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(project.revisions.count(), 1)
