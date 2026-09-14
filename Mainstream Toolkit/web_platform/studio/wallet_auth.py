"""Xverse payment-address authentication using explicit ECDSA message signatures."""
import base64
import hashlib
import secrets
import uuid
from datetime import timedelta

from coincurve import PublicKey
from embit import compact, ec, script
from embit.networks import NETWORKS
from django.contrib.auth import get_user_model, login
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from . import bip322
from .models import AuthorProfile, WalletChallenge, WalletIdentity


def message_hash(message):
    raw = message.encode('utf-8')
    return hashlib.sha256(hashlib.sha256(b'\x18Bitcoin Signed Message:\n' + compact.to_bytes(len(raw)) + raw).digest()).digest()


def valid_address(address):
    try:
        output = script.address_to_scriptpubkey(address)
        return output.script_type() in ('p2sh', 'p2wpkh', 'p2tr') and output.address(NETWORKS['main']) == address
    except Exception:
        return False


def verify_signature(address, message, signature):
    """Recover the signer, then derive the requested mainnet payment address.

    Xverse ECDSA can use the legacy compressed header for SegWit addresses.
    The recovered key must still produce the exact challenge address.
    """
    if address.startswith('bc1p'):
        return bip322.verify(address, message, signature)
    try:
        raw = base64.b64decode(signature, validate=True)
        if len(raw) != 65 or not 31 <= raw[0] <= 42 or not valid_address(address):
            return False
        recovery = (raw[0] - 27) % 4
        pub = PublicKey.from_signature_and_message(raw[1:] + bytes([recovery]), message_hash(message), hasher=None)
        key = ec.PublicKey.parse(pub.format(compressed=True))
        witness = script.p2wpkh(key)
        expected = script.p2sh(witness) if address.startswith('3') else witness
        return secrets.compare_digest(expected.address(NETWORKS['main']), address)
    except Exception:
        return False


def session_hash(request):
    if not request.session.session_key:
        request.session.create()
    return hashlib.sha256(request.session.session_key.encode()).hexdigest()


def limited(request, action):
    key = 'wallet-auth:' + action + ':' + hashlib.sha256(request.META.get('REMOTE_ADDR', '').encode()).hexdigest()
    cache.add(key, 0, 300)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, 300)
        count = 1
    return count > 30


@never_cache
@require_POST
def challenge(request):
    if limited(request, 'challenge'):
        return JsonResponse({'error': 'Too many requests. Try again in five minutes.'}, status=429)
    address = request.POST.get('address', '')
    if not valid_address(address):
        return JsonResponse({'error': 'Choose an Xverse mainnet payment address (P2SH or P2WPKH).'}, status=400)
    bound_session = session_hash(request)
    now = timezone.now()
    expires = now + timedelta(minutes=5)
    purpose = 'Link this wallet to your signed-in Observatory account.' if request.user.is_authenticated else 'Sign in or create your Observatory account.'
    merge_attempt = None
    merge_slot = request.POST.get('merge_slot', '')
    if request.POST.get('merge_attempt'):
        if not request.user.is_authenticated or merge_slot not in ('owner', 'other'):
            return JsonResponse({'error': 'Sign in and choose an account to verify.'}, status=400)
        from .merge_views import active_attempt
        try:
            merge_attempt = active_attempt(request, request.POST['merge_attempt'])
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        purpose = ('Verify ownership of the '+ ('current' if merge_slot == 'owner' else 'other') +
            ' account for an Observatory account merge. Accounts change only after a separate review and confirmation.\n'
            f'Merge request: {merge_attempt.pk}')
    message = (f'{request.get_host()} requests your Bitcoin wallet signature.\n\n{purpose}\n'
               f'No payment or Bitcoin transaction is authorized.\n\nAddress: {address}\n'
               f'URI: {request.build_absolute_uri("/")}\nNetwork: Bitcoin Mainnet\n'
               f'Nonce: {secrets.token_hex(32)}\nIssued at: {now.isoformat()}\nExpires at: {expires.isoformat()}')
    item = WalletChallenge.objects.create(address=address, message=message, session_hash=bound_session,
        user=request.user if request.user.is_authenticated else None, expires_at=expires,
        merge_attempt=merge_attempt, merge_slot=merge_slot if merge_attempt else '')
    return JsonResponse({'id': str(item.pk), 'message': message, 'address': address, 'protocol': 'BIP322' if address.startswith('bc1p') else 'ECDSA'})


@never_cache
@require_POST
def authenticate(request):
    if limited(request, 'verify'):
        return JsonResponse({'error': 'Too many requests. Try again in five minutes.'}, status=429)
    try:
        challenge_id = uuid.UUID(request.POST.get('challenge_id', ''))
    except ValueError:
        return JsonResponse({'error': 'Invalid challenge.'}, status=400)
    user_id = request.user.pk if request.user.is_authenticated else None
    bound_session = session_hash(request)
    with transaction.atomic():
        item = WalletChallenge.objects.select_for_update().filter(pk=challenge_id).first()
        if (not item or item.consumed_at or item.expires_at <= timezone.now()
                or item.session_hash != bound_session or item.user_id != user_id):
            return JsonResponse({'error': 'This sign-in request expired or was already used. Connect again.'}, status=400)
        # Consume even a failed signature; database locking prevents concurrent replay.
        item.consumed_at = timezone.now()
        item.save(update_fields=['consumed_at'])
        if not verify_signature(item.address, item.message, request.POST.get('signature', '')[:1024]):
            return JsonResponse({'error': 'Wallet signature could not be verified. Connect again.'}, status=400)
        if item.merge_attempt_id:
            from .merge_views import wallet_proof
            return wallet_proof(request, item)
        try:
            with transaction.atomic():
                identity = WalletIdentity.objects.select_related('user').filter(address=item.address).first()
                if identity:
                    if user_id and identity.user_id != user_id:
                        return JsonResponse({'error': 'This wallet already has an account. Verify both accounts to merge your writing and access.',
                            'merge_url': '/account/merge/'}, status=409)
                    user = identity.user
                else:
                    user = request.user if user_id else get_user_model().objects.create_user(
                        username='wallet_' + uuid.uuid4().hex, password=None)
                    WalletIdentity.objects.create(user=user, address=item.address)
                    AuthorProfile.objects.get_or_create(user=user, defaults={'pen_name': 'An Observatory writer'})
        except IntegrityError:
            return JsonResponse({'error': 'This wallet was just linked. Connect again to sign in.'}, status=409)
        if not user.is_active:
            return JsonResponse({'error': 'This account is inactive.'}, status=403)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    destination = '/account/collection/' if item.address.startswith('bc1p') and user_id else '/account/'
    from .invite_views import pending_code
    if pending_code(request):
        destination = '/invite/'
    from django.middleware.csrf import get_token
    return JsonResponse({'ok': True, 'redirect': destination, 'csrf_token': get_token(request)})
