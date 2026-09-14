"""Direct Bitcoin orders. No wallet secrets, no browser-trusted settlement."""
import json
import re
from datetime import timedelta, datetime, timezone as dt_timezone
from decimal import Decimal, ROUND_CEILING
from urllib.request import Request, urlopen
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from .membership import chain_height, membership_state, TERM
from .merging import lock_order
from .models import PaymentOrder, ReceivingAddress, PublishingMembership


def ready():
    return settings.DIRECT_BITCOIN_ENABLED and ReceivingAddress.objects.filter(order__isnull=True).exists()


def get_json(url):
    if not url.startswith('https://'): raise ValueError('Payment data requires HTTPS.')
    with urlopen(Request(url,headers={'User-Agent':'Observatory/1.0'}),timeout=12) as response:
        return json.loads(response.read(2000000))


def spot_price():
    data=get_json('https://api.coinbase.com/v2/prices/BTC-USD/spot')['data']
    rate=Decimal(data['amount'])
    if data.get('currency')!='USD' or not rate.is_finite() or rate<=0: raise ValueError('Invalid exchange quote.')
    return rate


def create_order(user):
    if not settings.DIRECT_BITCOIN_ENABLED: raise ValueError('Direct Bitcoin checkout is not enabled yet.')
    rate=spot_price()
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        state=membership_state(user)
        if state['complimentary']:
            raise ValueError('Your complimentary access is active; no payment is needed.')
        if state['height'] is None: raise ValueError('Waiting for a fresh confirmed block height.')
        recent=PaymentOrder.objects.filter(user=user,provider='direct',applied_at_block__isnull=True,quote_expires__gt=timezone.now()).order_by('-created_at').first()
        if recent: return recent
        address=ReceivingAddress.objects.select_for_update().filter(order__isnull=True).order_by('pk').first()
        if not address: raise ValueError('No receiving addresses are available. Please try again later.')
        sats=int((state['total']/rate*Decimal(100000000)).to_integral_value(rounding=ROUND_CEILING))
        if not 546<=sats<=2100000000000000: raise ValueError('Quote outside supported transaction limits.')
        order=PaymentOrder.objects.create(user=user,provider='direct',address=address.address,amount_sats=sats,
            amount_usd=state['total'],redemption=state['stage']=='redemption',quote_expires=timezone.now()+timedelta(minutes=15),status='Awaiting payment')
        address.order=order;address.save(update_fields=['order'])
        return order


def verify_transaction(order, tx):
    if not re.fullmatch('[0-9a-f]{64}',tx.get('txid','')): raise ValueError('Invalid transaction ID.')
    outputs=tx.get('vout',[])
    paid=sum(o['value'] for o in outputs if o.get('scriptpubkey_address')==order.address and type(o.get('value')) is int and o['value']>0)
    if paid<order.amount_sats:
        return 'Underpaid' if paid else 'Awaiting payment'
    status=tx.get('status',{})
    with transaction.atomic():
        locked=lock_order(order)
        if locked.applied_at_block is not None: return 'Settled'
        now=timezone.now()
        # New/replaced transactions need their own timely observation; a previous
        # txid cannot make an unrelated late transaction qualify for an old quote.
        first=locked.first_seen if locked.txid==tx['txid'] else None
        first=first or now
        block_time=status.get('block_time')
        mined_in_time=status.get('confirmed') is True and type(block_time) is int and locked.created_at.timestamp()-7200<=block_time<=locked.quote_expires.timestamp()
        timely=first<=locked.quote_expires or mined_in_time
        locked.txid=tx['txid'];locked.first_seen=first
        height=chain_height(); mined=status.get('block_height')
        result='Confirming'
        if not timely: result='Late payment review'
        elif status.get('confirmed') is True and type(mined) is int and height is not None and 0<=mined<=height:
            # Independently ensure the claimed block is still in the canonical chain.
            block_hash=status.get('block_hash','')
            if not re.fullmatch('[0-9a-f]{64}',block_hash): raise ValueError('Invalid block hash.')
            base=settings.BITCOIN_ESPLORA_URL.rstrip('/')
            with urlopen(base+'/block-height/'+str(mined),timeout=12) as response:
                canonical=response.read(100).decode().strip()
            if canonical!=block_hash: raise ValueError('Payment block is not canonical.')
            member=PublishingMembership.objects.filter(user_id=order.user_id).first()
            expiry=max(height,member.expires_at_block if member else height)+TERM
            PublishingMembership.objects.update_or_create(user_id=order.user_id,defaults={'expires_at_block':expiry})
            locked.applied_at_block=height;result='Settled'
        locked.status=result;locked.save(update_fields=['status','txid','first_seen','applied_at_block'])
        return result


def reconcile(order):
    if order.applied_at_block is not None: return
    base=settings.BITCOIN_ESPLORA_URL.rstrip('/')
    if not base.startswith('https://'): raise ValueError('Chain source requires HTTPS.')
    transactions=get_json(base+'/address/'+order.address+'/txs')
    if not isinstance(transactions,list): raise ValueError('Invalid chain response.')
    result='Quote expired' if timezone.now()>order.quote_expires else 'Awaiting payment'
    # A unique address is never reassigned. Discovery also works after a browser closes.
    # If >25 payments reach an invoice address, require support reconciliation.
    if len(transactions)>=25: result='Payment review'
    else:
        for tx in transactions:
            state=verify_transaction(order,tx)
            if state=='Settled': return
            if state!='Awaiting payment': result=state
    PaymentOrder.objects.filter(pk=order.pk,applied_at_block__isnull=True).update(status=result)
