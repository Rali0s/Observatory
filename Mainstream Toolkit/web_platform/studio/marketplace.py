"""Noncustodial single-inscription sales, using Taproot SINGLE|ANYONECANPAY.

The buyer prepends a cardinal input and a receiving output. Output zero contains
that entire input plus the entire inscription UTXO, preserving all its sats.
The seller's signature moves from index zero to one and still commits to the
same exact payout. Buyer inputs sign ALL. No private keys enter this service.
"""
import base64
from io import BytesIO
import re
from urllib.request import Request, urlopen
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from embit import ec, psbt, script
from embit.networks import NETWORKS
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from .membership import chain_height
from .models import OrdinalEdition, OrdinalHolding, OrdinalListing, OrdinalTrade, WalletIdentity
from .ordinals import fetch

SALE_SIGHASH = 0x83
DUST = 546


def ready():
    return bool(settings.ORDINAL_TRADING_ENABLED and settings.ORDINAL_INDEX_URL)


def enabled():
    if not ready():
        raise ValueError('Trading is awaiting the operator’s Bitcoin index and wallet verification.')


def decode(value):
    if not isinstance(value, str) or len(value) > 100000:
        raise ValueError('Invalid transaction size.')
    try:
        raw = base64.b64decode(value, validate=True)
        stream = BytesIO(raw)
        result = psbt.PSBT.read_from(stream)
        if stream.read(1):
            raise ValueError('Trailing PSBT bytes.')
        return result
    except Exception as exc:
        raise ValueError('Invalid Bitcoin transaction.') from exc


def encode(value):
    return base64.b64encode(value.serialize()).decode()


def address_script(address, allowed=('p2tr', 'p2sh', 'p2wpkh')):
    try:
        result = script.address_to_scriptpubkey(address)
        if result.script_type() not in allowed or result.address(NETWORKS['main']) != address:
            raise ValueError()
        return result
    except Exception as exc:
        raise ValueError('Use a supported Bitcoin mainnet address.') from exc


def outpoint_parts(outpoint):
    if not re.fullmatch(r'[0-9a-f]{64}:[0-9]{1,10}', outpoint):
        raise ValueError('Invalid outpoint.')
    txid, index = outpoint.split(':')
    if int(index) > 0xffffffff:
        raise ValueError('Invalid output index.')
    return txid, int(index)


def synced_index():
    height = chain_height()
    status = fetch('/status')
    if (height is None or status.get('chain') != 'mainnet' or type(status.get('height')) is not int
            or status['height'] < height or status.get('rune_index') is not True):
        raise ValueError('A synchronized mainnet index with rune indexing is required for safe trading.')
    return height


def output_info(outpoint):
    txid, index = outpoint_parts(outpoint)
    info = fetch('/output/' + outpoint)
    tx = fetch('/tx/' + txid, chain=True)
    spent = fetch(f'/tx/{txid}/outspend/{index}', chain=True)
    height = chain_height()
    if (height is None or tx.get('txid') != txid or spent.get('spent') is not False
            or not tx.get('status', {}).get('confirmed')
            or type(tx['status'].get('block_height')) is not int or tx['status']['block_height'] > height
            or info.get('outpoint') != outpoint or info.get('spent') is not False or info.get('indexed') is not True):
        raise ValueError('This output is spent, unconfirmed, or not fully indexed.')
    canonical = fetch('/block-height/' + str(tx['status']['block_height']), chain=True, raw=True).decode().strip()
    if canonical != tx['status'].get('block_hash'):
        raise ValueError('Output confirmation is not on the canonical chain.')
    outputs = tx.get('vout', [])
    if index >= len(outputs):
        raise ValueError('Output does not exist.')
    actual = outputs[index]
    if (type(info.get('value')) is not int or info['value'] <= 0
            or info['value'] != actual.get('value') or info.get('address') != actual.get('scriptpubkey_address')):
        raise ValueError('Index output does not match Bitcoin.')
    actual_script = script.Script(bytes.fromhex(actual['scriptpubkey']))
    if address_script(info['address']).data != actual_script.data:
        raise ValueError('Output script mismatch.')
    return info, TransactionOutput(info['value'], actual_script)


def holding(edition):
    synced_index()
    info = fetch('/inscription/' + edition.inscription_id)
    point = info.get('satpoint', '')
    if info.get('id') != edition.inscription_id or not re.fullmatch(r'[0-9a-f]{64}:[0-9]{1,10}:[0-9]{1,16}', point):
        raise ValueError('The inscription location could not be verified.')
    outpoint, offset = point.rsplit(':', 1)
    output, utxo = output_info(outpoint)
    if (info.get('address') != output['address'] or output.get('inscriptions') != [edition.inscription_id]
            or output.get('runes') != {} or int(offset) >= utxo.value):
        raise ValueError('Trading requires an output containing only this inscription and no runes.')
    OrdinalHolding.objects.update_or_create(edition=edition, defaults={
        'address': output['address'], 'outpoint': outpoint, 'checked_at': timezone.now()})
    return output, utxo


def owned_wallet(user, address):
    if not WalletIdentity.objects.filter(user=user, address=address).exists():
        raise ValueError('Link this wallet address to your account with a signed message first.')


def create_listing(user, edition, price, payout_address):
    enabled()
    if type(price) is not int or not DUST <= price <= settings.ORDINAL_MAX_PRICE_SATS:
        raise ValueError(f'Choose a price between {DUST} and {settings.ORDINAL_MAX_PRICE_SATS} sats.')
    if edition.status != 'minted' or not edition.publication.is_visible:
        raise ValueError('Only verified public editions can be sold.')
    output, utxo = holding(edition)
    owned_wallet(user, output['address'])
    address_script(output['address'], ('p2tr',))
    payout = address_script(payout_address)
    owned_wallet(user, payout_address)
    txid, index = outpoint_parts(output['outpoint'])
    unsigned = psbt.PSBT(Transaction(vin=[TransactionInput(bytes.fromhex(txid), index)],
        vout=[TransactionOutput(price, payout)]))
    unsigned.inputs[0].witness_utxo = utxo
    unsigned.inputs[0].sighash_type = SALE_SIGHASH
    with transaction.atomic():
        OrdinalEdition.objects.select_for_update().get(pk=edition.pk)
        if OrdinalListing.objects.filter(edition=edition, status__in=['draft', 'active']).exists():
            raise ValueError('An open listing already exists. Resume it or delist it first.')
        return OrdinalListing.objects.create(edition=edition, seller=user, seller_address=output['address'],
            payout_address=payout_address, price_sats=price, outpoint=output['outpoint'], postage_sats=utxo.value,
            unsigned_psbt=encode(unsigned))


def tap_signature(signed, index):
    scope = signed.inputs[index]
    witness = scope.final_scriptwitness
    signature = scope.unknown.get(b'\x13')
    if witness is not None:
        if len(witness.items) != 1:
            raise ValueError('Only Taproot key-path signatures are supported.')
        signature = witness.items[0]
    if not signature:
        raise ValueError('The seller signature is missing.')
    return signature


def verify_tap_signature(unsigned, index, signature, required_sighash):
    if len(signature) != 65 or signature[-1] != required_sighash:
        raise ValueError('The wallet used an unsupported signature mode.')
    scripts = [inp.witness_utxo.script_pubkey for inp in unsigned.inputs]
    values = [inp.witness_utxo.value for inp in unsigned.inputs]
    if scripts[index].script_type() != 'p2tr':
        raise ValueError('The inscription must use a Taproot address.')
    digest = unsigned.tx.sighash_taproot(index, scripts, values, sighash=required_sighash)
    if not ec.PublicKey.from_xonly(scripts[index].data[2:]).schnorr_verify(ec.SchnorrSig.parse(signature[:64]), digest):
        raise ValueError('The seller signature is invalid.')


def activate_listing(listing, supplied):
    enabled()
    unsigned, signed = decode(listing.unsigned_psbt), decode(supplied)
    if unsigned.tx.serialize() != signed.tx.serialize():
        raise ValueError('The listing transaction was changed.')
    signature = tap_signature(signed, 0)
    verify_tap_signature(unsigned, 0, signature, SALE_SIGHASH)
    output, _ = holding(listing.edition)
    if output['outpoint'] != listing.outpoint or output['address'] != listing.seller_address:
        raise ValueError('The inscription has moved since this listing was prepared.')
    # Store only the verified canonical transaction and its signature.
    unsigned.inputs[0].final_scriptwitness = script.Witness([signature])
    with transaction.atomic():
        locked = OrdinalListing.objects.select_for_update().get(pk=listing.pk)
        if locked.status != 'draft':
            raise ValueError('This listing is no longer awaiting a signature.')
        locked.signed_psbt = encode(unsigned)
        locked.status = 'active'
        locked.save(update_fields=['signed_psbt', 'status'])


def cardinal_inputs(address, minimum):
    outputs = fetch('/outputs/' + address + '?type=cardinal')
    if not isinstance(outputs, list):
        raise ValueError('The wallet balance could not be verified.')
    candidates = sorted([o for o in outputs if isinstance(o, dict) and type(o.get('value')) is int and o['value'] >= DUST], key=lambda o: o['value'])
    selected, seen, total = [], set(), 0
    for candidate in candidates[:50]:
        point = candidate.get('outpoint', '')
        if point in seen:
            continue
        info, utxo = output_info(point)
        if info['address'] != address or info.get('inscriptions') != [] or info.get('runes') != {}:
            continue
        seen.add(point)
        selected.append((point, utxo))
        if len(selected) > 1:
            total += utxo.value
        if len(selected) >= 2 and total >= minimum:
            return selected
        if len(selected) >= 10:
            break
    raise ValueError('The payment wallet needs at least two confirmed cardinal outputs and enough Bitcoin for the price, fee, and change. No inscriptions or runes will be used for funding.')


def create_trade(user, listing, payment_address, receive_address, fee_sats, payment_public_key):
    enabled()
    if listing.status != 'active' or listing.seller_id == user.pk or not listing.edition.publication.is_visible:
        raise ValueError('This listing is not available to this buyer.')
    if type(fee_sats) is not int or not 500 <= fee_sats <= settings.ORDINAL_MAX_FEE_SATS:
        raise ValueError('Choose a network fee between 500 and 100,000 sats.')
    owned_wallet(user, receive_address)
    owned_wallet(user, payment_address)
    receive = address_script(receive_address, ('p2tr',))
    payment = address_script(payment_address, ('p2sh', 'p2wpkh'))
    try:
        pub = ec.PublicKey.parse(bytes.fromhex(payment_public_key))
    except Exception as exc:
        raise ValueError('A valid payment public key is required.') from exc
    witness = script.p2wpkh(pub)
    expected = script.p2sh(witness) if payment.script_type() == 'p2sh' else witness
    if expected.data != payment.data:
        raise ValueError('Payment public key does not match your wallet.')
    output, _ = holding(listing.edition)
    if output['outpoint'] != listing.outpoint or output['address'] != listing.seller_address:
        OrdinalListing.objects.filter(pk=listing.pk, status='active').update(status='stale')
        raise ValueError('This inscription is no longer at the listed output.')
    selected = cardinal_inputs(payment_address, listing.price_sats + fee_sats + DUST)
    seller = decode(listing.signed_psbt)
    inputs = [selected[0], (listing.outpoint, seller.inputs[0].witness_utxo)] + selected[1:]
    vins = [TransactionInput(bytes.fromhex(outpoint_parts(point)[0]), outpoint_parts(point)[1]) for point, _ in inputs]
    # All sats preceding and within the inscription output stay with the buyer.
    receive_value = selected[0][1].value + listing.postage_sats
    change = sum(utxo.value for _, utxo in selected[1:]) - listing.price_sats - fee_sats
    unsigned = psbt.PSBT(Transaction(vin=vins, vout=[TransactionOutput(receive_value, receive),
        TransactionOutput(listing.price_sats, address_script(listing.payout_address)), TransactionOutput(change, payment)]))
    for index, (_, utxo) in enumerate(inputs):
        unsigned.inputs[index].witness_utxo = utxo
        unsigned.inputs[index].sighash_type = SALE_SIGHASH if index == 1 else 1
        if index != 1 and payment.script_type() == 'p2sh':
            unsigned.inputs[index].redeem_script = witness
    signature = tap_signature(seller, 0)
    verify_tap_signature(unsigned, 1, signature, SALE_SIGHASH)
    unsigned.inputs[1].final_scriptwitness = script.Witness([signature])
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        locked = OrdinalListing.objects.select_for_update().get(pk=listing.pk)
        if locked.status != 'active':
            raise ValueError('The listing is no longer available.')
        previous = OrdinalTrade.objects.filter(listing=locked, buyer=user).exclude(status='conflict').order_by('-created_at').first()
        if previous:
            raise ValueError('A purchase attempt already exists. Open it to finish or check its status.')
        return OrdinalTrade.objects.create(listing=locked, buyer=user, receive_address=receive_address,
            payment_address=payment_address, unsigned_psbt=encode(unsigned), fee_sats=fee_sats)


def finalize_trade(trade, supplied):
    expected, signed = decode(trade.unsigned_psbt), decode(supplied)
    if expected.tx.serialize() != signed.tx.serialize():
        raise ValueError('The purchase transaction, price, recipient, or fee was changed.')
    final = Transaction.parse(expected.tx.serialize())
    for index, scope in enumerate(expected.inputs):
        if index == 1:
            signature = tap_signature(expected, index)
            verify_tap_signature(expected, index, signature, SALE_SIGHASH)
            final.vin[index].witness = script.Witness([signature])
            continue
        candidate = signed.inputs[index]
        witness = candidate.final_scriptwitness
        if witness is not None:
            if len(witness.items) != 2:
                raise ValueError('Unsupported payment witness.')
            sig, public = witness.items
            pub = ec.PublicKey.parse(public)
        else:
            if len(candidate.partial_sigs) != 1:
                raise ValueError('A buyer signature is missing.')
            pub, sig = next(iter(candidate.partial_sigs.items()))
        if len(pub.sec()) != 33 or not sig or sig[-1] != 1:
            raise ValueError('Buyer signatures must commit to the entire purchase.')
        payment_witness = script.p2wpkh(pub)
        output_script = scope.witness_utxo.script_pubkey
        key_script = script.p2sh(payment_witness) if output_script.script_type() == 'p2sh' else payment_witness
        if key_script.data != output_script.data:
            raise ValueError('Buyer signature key does not match the funding output.')
        digest = expected.tx.sighash_segwit(index, script.p2pkh(pub), scope.witness_utxo.value, sighash=1)
        if not pub.verify(ec.Signature.parse(sig[:-1]), digest):
            raise ValueError('Invalid buyer signature.')
        final.vin[index].witness = script.Witness([sig, pub.sec()])
        if output_script.script_type() == 'p2sh':
            final.vin[index].script_sig = script.Script(payment_witness.serialize())
    fee = sum(inp.witness_utxo.value for inp in expected.inputs) - sum(out.value for out in final.vout)
    if fee != trade.fee_sats or fee > settings.ORDINAL_MAX_FEE_SATS:
        raise ValueError('Unexpected transaction fee.')
    return final


def submit_trade(trade, supplied):
    enabled()
    if trade.status not in ('prepared', 'broadcasting', 'broadcast'):
        raise ValueError('This purchase attempt is already closed.')
    if not trade.raw_transaction:
        final = finalize_trade(trade, supplied)
        # Recheck asset safety and unspent inputs immediately before recording a broadcast.
        synced_index()
        for index, inp in enumerate(final.vin):
            info, utxo = output_info(f'{inp.txid.hex()}:{inp.vout}')
            if index == 1 and (info.get('inscriptions') != [trade.listing.edition.inscription_id] or info.get('runes') != {}):
                raise ValueError('The inscription output no longer matches the sale.')
            if index != 1 and (info.get('inscriptions') != [] or info.get('runes') != {}):
                raise ValueError('A funding output contains another asset.')
        with transaction.atomic():
            locked = OrdinalTrade.objects.select_for_update().get(pk=trade.pk)
            listing = OrdinalListing.objects.select_for_update().get(pk=locked.listing_id)
            if locked.status != 'prepared' or listing.status != 'active' or not listing.edition.publication.is_visible:
                raise ValueError('This purchase is no longer available.')
            locked.raw_transaction = final.serialize().hex()
            locked.txid = final.txid().hex()
            locked.status = 'broadcasting'
            locked.save(update_fields=['raw_transaction', 'txid', 'status'])
        trade.refresh_from_db()
    # Retrying always submits the same bytes/txid, never a second payment.
    base = settings.BITCOIN_ESPLORA_URL.rstrip('/')
    if not base.startswith('https://'):
        raise ValueError('An HTTPS Bitcoin endpoint is required.')
    try:
        with urlopen(Request(base + '/tx', data=trade.raw_transaction.encode(), headers={'Content-Type': 'text/plain'}), timeout=15) as response:
            returned = response.read(256).decode().strip()
        if returned != trade.txid:
            raise ValueError('Unexpected broadcast transaction ID.')
        OrdinalTrade.objects.filter(pk=trade.pk, status='broadcasting').update(status='broadcast')
    except Exception as exc:
        raise ValueError('Broadcast status is uncertain. Your exact transaction is retained. Check status before retrying; no new payment will be constructed.') from exc


def reconcile_trade(trade):
    if not trade.txid or trade.status == 'confirmed':
        return
    tx = fetch('/tx/' + trade.txid, chain=True)
    if tx.get('txid') != trade.txid:
        raise ValueError('Unexpected transaction.')
    height = chain_height()
    status = tx.get('status', {})
    if height is None or status.get('confirmed') is not True or type(status.get('block_height')) is not int or status['block_height'] > height:
        return
    canonical = fetch('/block-height/' + str(status['block_height']), chain=True, raw=True).decode().strip()
    if canonical != status.get('block_hash'):
        raise ValueError('Purchase confirmation is not canonical.')
    # Compare the mined transaction bytes to the exact approved transaction.
    raw = fetch('/tx/' + trade.txid + '/hex', chain=True, raw=True).decode().strip()
    if raw != trade.raw_transaction:
        raise ValueError('Confirmed transaction differs from the approved purchase.')
    with transaction.atomic():
        locked = OrdinalTrade.objects.select_for_update().get(pk=trade.pk)
        listing = OrdinalListing.objects.select_for_update().get(pk=locked.listing_id)
        locked.status = 'confirmed'
        locked.confirmed_at = timezone.now()
        locked.save(update_fields=['status', 'confirmed_at'])
        listing.status = 'sold'
        listing.save(update_fields=['status'])
    # Current holdings can move again after collection. Refresh separately from history.
