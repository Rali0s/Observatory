import base64
from datetime import timedelta
from coincurve import PrivateKey
from embit import ec, script
from embit.networks import NETWORKS
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from . import bip322
from .models import WalletChallenge, WalletIdentity
from .wallet_auth import message_hash, verify_signature


class WalletAuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.key = PrivateKey(bytes.fromhex('11' * 32))
        self.pub = ec.PublicKey.parse(self.key.public_key.format())
        self.address = script.p2sh(script.p2wpkh(self.pub)).address(NETWORKS['main'])

    def challenge(self, client=None):
        return (client or self.client).post(reverse('wallet-challenge'), {'address': self.address}).json()

    def signed(self, challenge):
        raw = self.key.sign_recoverable(message_hash(challenge['message']), hasher=None)
        return base64.b64encode(bytes([31 + raw[-1]]) + raw[:64]).decode()

    def submit(self, challenge, client=None, signature=None):
        return (client or self.client).post(reverse('wallet-authenticate'), {
            'challenge_id': challenge['id'], 'signature': signature or self.signed(challenge)})

    def test_real_signature_creates_passwordless_account_and_replay_fails(self):
        proof = self.challenge()
        self.assertEqual(self.submit(proof).status_code, 200)
        identity = WalletIdentity.objects.get(address=self.address)
        self.assertFalse(identity.user.has_usable_password())
        self.assertEqual(self.client.session['_auth_user_id'], str(identity.user_id))
        self.assertEqual(self.submit(proof).status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_wallet_login_returns_to_invite_without_redeeming(self):
        from .invites import issue
        from .models import InviteRedemption
        admin = get_user_model().objects.create_user('inviter', is_staff=True)
        _, code = issue(admin, label='Wallet invitation', kind='lifetime', max_uses=1)
        self.client.post(reverse('invite-landing'), {'code': code, 'action': 'signin'})
        response = self.submit(self.challenge())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect'], reverse('invite-landing'))
        self.assertEqual(self.client.get(reverse('invite-landing')).context['form']['code'].value(), code)
        self.assertFalse(InviteRedemption.objects.exists())
        self.client.post(reverse('invite-landing'), {'code': code, 'action': 'redeem'})
        self.assertEqual(InviteRedemption.objects.count(), 1)

    def test_signature_is_bound_to_address_message_session_and_expiry(self):
        proof = self.challenge()
        self.assertEqual(self.submit(proof, Client()).status_code, 400)
        self.assertFalse(verify_signature(self.address, proof['message'] + 'changed', self.signed(proof)))
        self.assertEqual(self.submit(proof, signature='invalid').status_code, 400)
        self.assertEqual(self.submit(proof).status_code, 400)
        proof = self.challenge()
        WalletChallenge.objects.filter(pk=proof['id']).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.submit(proof).status_code, 400)
        self.assertEqual(WalletIdentity.objects.count(), 0)

    def test_link_existing_account_never_transfers_another_users_wallet(self):
        alice = get_user_model().objects.create_user('alice')
        bob = get_user_model().objects.create_user('bob')
        self.client.force_login(alice)
        self.assertEqual(self.submit(self.challenge()).status_code, 200)
        self.client.force_login(bob)
        self.assertEqual(self.submit(self.challenge()).status_code, 409)
        self.assertEqual(WalletIdentity.objects.get(address=self.address).user, alice)

    def test_returning_wallet_logs_in_same_user_and_inactive_account_is_rejected(self):
        self.submit(self.challenge())
        user = WalletIdentity.objects.get(address=self.address).user
        self.client.logout()
        self.assertEqual(self.submit(self.challenge()).status_code, 200)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.client.logout()
        user.is_active = False
        user.save()
        self.assertEqual(self.submit(self.challenge()).status_code, 403)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_csrf_and_network_validation(self):
        csrf = Client(enforce_csrf_checks=True)
        self.assertEqual(csrf.post(reverse('wallet-challenge'), {'address': self.address}).status_code, 403)
        self.assertEqual(self.client.post(reverse('wallet-challenge'), {'address': script.p2wpkh(self.pub).address(NETWORKS['test'])}).status_code, 400)

    def test_official_bip322_taproot_vector_and_mutations(self):
        # bitcoin/bips bip-0322/basic-test-vectors.json: "No prefix fallback".
        address = 'bc1pss0zhytly75awhm6x2hhvd5lnzv3vssgrf9axfheq8ldyzn88ges79fler'
        signature = 'AUCJYOwOjxYAvatTAGYaVlNXBVyFuc4MwNQkOuK2tl8xhfKDONd0NjfYyNSYcRqeCp8hsAnCEPHAVEkO9h6vbQ/R'
        self.assertTrue(bip322.verify(address, 'No prefix fallback', signature))
        self.assertFalse(bip322.verify(address, 'Different message', signature))
        self.assertFalse(bip322.verify(address, 'No prefix fallback', signature + 'AA=='))
        self.assertFalse(bip322.verify(self.address, 'No prefix fallback', signature))

    def test_taproot_challenge_can_link_ordinal_address(self):
        key = ec.PrivateKey(bytes.fromhex('22' * 32))
        self.address = script.p2tr(key.get_public_key()).address(NETWORKS['main'])
        self.client.force_login(get_user_model().objects.create_user('collector'))
        proof = self.challenge()
        tx, output = bip322.signing_transaction(self.address, proof['message'])
        sig = key.taproot_tweak().schnorr_sign(tx.sighash_taproot(0, [output], [0])).serialize()
        signature = base64.b64encode(script.Witness([sig]).serialize()).decode()
        self.assertEqual(proof['protocol'], 'BIP322')
        self.assertEqual(self.submit(proof, signature=signature).status_code, 200)
