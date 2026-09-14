"""Transparent planning estimates, never a claim about the wallet's final transaction."""
import math
from decimal import Decimal, InvalidOperation
from urllib.request import Request, urlopen
import json
from django.conf import settings
from django.core import signing
from django.core.cache import cache


def rate(value):
    try:
        result=Decimal(str(value))
        if not result.is_finite() or not Decimal('1') <= result <= Decimal('1000'):
            raise ValueError()
        return result.quantize(Decimal('.01'))
    except (InvalidOperation,ValueError):
        raise ValueError('Choose a fee rate between 1 and 1,000 sats/vB.')


def recommendations():
    saved=cache.get('ordinal-miner-rates')
    if saved: return saved
    with urlopen(Request(settings.BITCOIN_FEE_URL,headers={'User-Agent':'Observatory/1.0'}),timeout=8) as response:
        raw=response.read(20001)
    if len(raw)>20000:raise ValueError('Fee response too large.')
    data=json.loads(raw)
    saved={name:str(rate(data[key])) for name,key in [('economy','economyFee'),('standard','hourFee'),('fast','fastestFee')]}
    cache.set('ordinal-miner-rates',saved,60)
    return saved


def estimate(content, fee_rate, edition=None, *, external=False):
    chosen=rate(fee_rate)
    size=len(content.encode('utf-8'))
    if size>350000:raise ValueError('This edition exceeds the 350 KB single-inscription limit. Shorten it before minting.')
    # One reveal with chunked 520-byte pushes; funding input count and change vary by wallet.
    reveal=110+math.ceil((size+100+3*math.ceil(size/520))/4)
    low,high=reveal+153,reveal+350
    fee=0 if external else settings.ORDINAL_PLATFORM_FEE_SATS
    result={'content_bytes':size,'fee_rate':str(chosen),'vbytes_min':low,'vbytes_max':high,
        'miner_min':math.ceil(low*chosen),'miner_max':math.ceil(high*chosen),
        'postage_estimate':546,'platform_fee':fee,'platform_address':settings.ORDINAL_FEES_WALLET if fee else '',
        'provider_fee':'Confirmed in wallet; not included in this estimate.'}
    result['subtotal_min']=result['miner_min']+546+fee
    result['subtotal_max']=result['miner_max']+546+fee
    if edition and not external:
        result['quote']=signing.dumps({'edition':str(edition.pk),'hash':edition.content_hash,'rate':str(chosen),
            'fee':fee,'address':settings.ORDINAL_FEES_WALLET},salt='ordinal-fee-quote')
    return result


def wallet_fee_payload(edition,quote):
    try:
        data=signing.loads(quote,salt='ordinal-fee-quote',max_age=300)
        if data['edition']!=str(edition.pk) or data['hash']!=edition.content_hash or data['fee']!=settings.ORDINAL_PLATFORM_FEE_SATS or data['address']!=settings.ORDINAL_FEES_WALLET:
            raise ValueError()
        result={'suggestedMinerFeeRate':float(rate(data['rate']))}
        if data['fee']:
            result.update(appFee=data['fee'],appFeeAddress=data['address'])
        return result
    except (signing.BadSignature,KeyError,ValueError,TypeError):
        raise ValueError('Refresh the fee estimate and review it before opening Xverse.')
