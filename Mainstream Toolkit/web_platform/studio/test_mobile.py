from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from .invites import issue
from .models import ComplimentaryAccess, InviteRedemption

class MobileReadingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin=get_user_model().objects.create_user('inviter',is_staff=True)
        _,self.code=issue(self.admin,label='Mobile launch',kind='three_months',max_uses=4)

    def remember(self, action='signup'):
        return self.client.post(reverse('invite-landing'),{'code':self.code.lower(),'action':action})

    def test_reading_auth_and_invite_pages_do_not_gate_mobile(self):
        for name in ['feed','authors','login','signup','invite-landing']:
            response=self.client.get(reverse(name))
            self.assertFalse(response.context['mobile_desktop_page'])
            self.assertContains(response,'Mobile navigation')
            self.assertNotContains(response,'class="mobile-limited-content"')
        self.client.force_login(self.admin)
        response=self.client.get(reverse('library'))
        self.assertTrue(response.context['mobile_desktop_page'])
        self.assertContains(response,'Open Observatory on a computer')
        self.assertContains(response,'class="mobile-limited-content"')
        self.assertFalse(self.client.get(reverse('account')).context['mobile_desktop_page'])

    def test_link_visit_does_not_redeem_and_is_not_cached(self):
        response=self.client.get(reverse('invite-landing'),{'code':self.code})
        self.assertEqual(response.status_code,200)
        self.assertFalse(InviteRedemption.objects.exists())
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertEqual(response.headers['Referrer-Policy'],'no-referrer')

    def test_signup_retains_invite_and_requires_explicit_redemption(self):
        self.assertRedirects(self.remember(),reverse('signup'))
        self.assertFalse(InviteRedemption.objects.exists())
        response=self.client.post(reverse('signup'),{'username':'mobile-reader','pen_name':'Mobile reader',
            'password1':'Some-long-uncommon-pass-4827','password2':'Some-long-uncommon-pass-4827'})
        self.assertRedirects(response,reverse('invite-landing'))
        self.assertFalse(InviteRedemption.objects.exists())
        response=self.client.get(reverse('invite-landing'))
        self.assertEqual(response.context['form']['code'].value(),self.code)
        response=self.client.post(reverse('invite-landing'),{'code':self.code,'action':'redeem'})
        self.assertRedirects(response,reverse('invite-landing'))
        self.assertEqual(InviteRedemption.objects.count(),1)
        self.assertNotIn('pending_invitation',self.client.session)
        self.assertTrue(ComplimentaryAccess.objects.filter(user__username='mobile-reader').exists())
        self.client.post(reverse('invite-landing'),{'code':self.code,'action':'redeem'})
        self.assertEqual(InviteRedemption.objects.count(),1)

    def test_password_login_returns_to_pending_invite(self):
        get_user_model().objects.create_user('existing',password='Long-password-4827')
        self.assertRedirects(self.remember('signin'),reverse('login')+'?next='+reverse('invite-landing'))
        response=self.client.post(reverse('login'),{'username':'existing','password':'Long-password-4827','next':reverse('invite-landing')})
        self.assertRedirects(response,reverse('invite-landing'))
        self.assertEqual(self.client.get(reverse('invite-landing')).context['form']['code'].value(),self.code)
        self.assertFalse(InviteRedemption.objects.exists())

    def test_expired_pending_invite_clears_and_post_requires_csrf(self):
        session=self.client.session
        session['pending_invitation']={'code':self.code,'expires':timezone.now().timestamp()-1}
        session.save()
        self.assertEqual(self.client.get(reverse('invite-landing')).context['form']['code'].value(),'')
        self.assertNotIn('pending_invitation',self.client.session)
        secure=Client(enforce_csrf_checks=True)
        self.assertEqual(secure.post(reverse('invite-landing'),{'code':self.code,'action':'signup'}).status_code,403)

    def test_bad_codes_and_rate_limits_do_not_grant_access(self):
        self.client.force_login(get_user_model().objects.create_user('reader'))
        for _ in range(20): self.client.post(reverse('invite-landing'),{'code':'OBS-'+'0'*32})
        response=self.client.post(reverse('invite-landing'),{'code':self.code})
        self.assertContains(response,'Too many invite attempts')
        self.assertFalse(InviteRedemption.objects.exists())

    def test_issued_links_use_fragment_and_are_only_shown_once(self):
        self.client.force_login(self.admin)
        response=self.client.post(reverse('invites'),{'label':'Phone','kind':'lifetime','max_uses':1})
        self.assertIn('/invite/#code=OBS-',response.context['invite_link'])
        self.assertNotContains(self.client.get(reverse('invites')),response.context['code'])
