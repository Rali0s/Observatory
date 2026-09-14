from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from . import invites
from .models import Invitation, InviteSettings, ComplimentaryAccess, AuthorProfile


class InviteManagementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('campaign-admin',is_staff=True)
        self.issuer = get_user_model().objects.create_user('campaign-issuer')
        self.reader = get_user_model().objects.create_user('private-reader-login')
        AuthorProfile.objects.create(user=self.reader,pen_name='Public reader name')
        self.issuer.user_permissions.add(Permission.objects.get(codename='issue_invitations'))
        InviteSettings.objects.update_or_create(pk=1,defaults={'member_issuers_enabled':True})
        self.item,self.code=invites.issue(self.issuer,label='Launch friends',kind='three_months',max_uses=3)
        self.foreign,_=invites.issue(self.admin,label='Private founders',kind='lifetime')
        self.detail=reverse('invite-detail',args=[self.item.pk])
        self.client.force_login(self.admin)

    def test_status_filters_totals_search_and_pagination(self):
        invites.redeem(self.reader,self.code)
        Invitation.objects.filter(pk=self.foreign.pk).update(uses=1)
        expired,_=invites.issue(self.admin,label='Expired campaign',kind='lifetime')
        Invitation.objects.filter(pk=expired.pk).update(redeem_before=timezone.now()-timedelta(days=1))
        disabled,_=invites.issue(self.admin,label='Disabled campaign',kind='lifetime')
        Invitation.objects.filter(pk=disabled.pk).update(enabled=False)
        url=reverse('invites')
        response=self.client.get(url)
        self.assertEqual(response.context['totals'],{'codes':4,'redemptions':2,'available':1})
        for status,pk in [('available',self.item.pk),('used',self.foreign.pk),('expired',expired.pk),('disabled',disabled.pk)]:
            response=self.client.get(url,{'status':status})
            self.assertEqual([i.pk for i in response.context['page']], [pk])
        response=self.client.get(url,{'q':'Launch','kind':'three_months'})
        self.assertEqual(response.context['page'].paginator.count,1)
        self.assertNotContains(response,self.code)
        for number in range(21):
            invites.issue(self.admin,label=f'Batch {number}',kind='lifetime')
        response=self.client.get(url,{'q':'Batch','kind':'lifetime','page':2})
        self.assertEqual(len(response.context['page']),1)
        self.assertContains(response,'q=Batch&amp;kind=lifetime')

    def test_management_preserves_existing_grants_and_serialized_capacity(self):
        access=invites.redeem(self.reader,self.code)
        end=access.expires_at
        data={'label':'Renamed launch','max_uses':1,'enabled':'on'}
        self.assertEqual(self.client.post(self.detail,data).status_code,302)
        self.item.refresh_from_db();self.assertEqual(self.item.kind,'three_months')
        response=self.client.post(self.detail,{**data,'max_uses':0})
        self.assertEqual(response.status_code,200)
        # Two redemptions prevent lowering capacity to one.
        self.client.post(self.detail,{**data,'max_uses':2})
        another=get_user_model().objects.create_user('second-reader')
        invites.redeem(another,self.code)
        self.assertContains(self.client.post(self.detail,data),'At least 2 places')
        self.client.post(self.detail,{'label':'Paused','max_uses':2})
        self.item.refresh_from_db();self.assertFalse(self.item.enabled)
        access.refresh_from_db();self.assertEqual(access.expires_at,end)
        self.assertEqual(self.client.post(self.detail,{**data,'max_uses':3,'kind':'lifetime'}).status_code,302)
        self.item.refresh_from_db();self.assertTrue(self.item.enabled)
        self.assertEqual(self.item.kind,'three_months')

    def test_expired_code_requires_future_deadline_to_reopen(self):
        past=(timezone.now()-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        data={'label':'Launch friends','max_uses':3,'enabled':'on','redeem_before':past}
        self.assertContains(self.client.post(self.detail,data),'Choose a future deadline')
        data.pop('enabled')
        self.assertEqual(self.client.post(self.detail,data).status_code,302)
        self.assertEqual(self.client.post(self.detail,{**data,'enabled':'on','redeem_before':''}).status_code,302)

    def test_history_identity_scope_and_grant_dates(self):
        invites.redeem(self.reader,self.code)
        response=self.client.get(self.detail)
        self.assertContains(response,'private-reader-login')
        self.assertContains(response,'Grant window active')
        self.assertNotContains(response,self.code)
        self.assertNotContains(response,self.item.code_hash)
        self.client.force_login(self.issuer)
        response=self.client.get(self.detail)
        self.assertContains(response,'Public reader name')
        self.assertNotContains(response,'private-reader-login')
        self.assertNotContains(self.client.get(reverse('invites')),'Private founders')
        foreign=reverse('invite-detail',args=[self.foreign.pk])
        self.assertEqual(self.client.get(foreign).status_code,404)
        self.assertEqual(self.client.post(foreign,{'label':'Intrusion','max_uses':10}).status_code,404)
        self.assertContains(self.client.get(reverse('account')),'Manage invite codes')
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(self.detail).status_code,403)
        self.assertNotContains(self.client.get(reverse('account')),'Manage invite codes')

    def test_lifetime_history_and_http_boundaries(self):
        lifetime,code=invites.issue(self.admin,label='Lifetime group',kind='lifetime')
        invites.redeem(self.reader,code)
        self.assertContains(self.client.get(reverse('invite-detail',args=[lifetime.pk])),'Lifetime grant')
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.admin)
        self.assertEqual(secure.post(self.detail,{'label':'Missing token','max_uses':2}).status_code,403)
        response=self.client.get(self.detail)
        self.assertIn('no-store',response['Cache-Control'])
        self.client.logout()
        self.assertEqual(self.client.get(self.detail).status_code,302)
