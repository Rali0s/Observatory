"""Immutable edition content and server-side inscription verification."""
import hashlib
import html
import json
import re
from urllib.request import Request, urlopen
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import OrdinalEdition, OrdinalSettings, Publication
from .membership import chain_height


def controls():
    return OrdinalSettings.objects.filter(pk=1).first() or OrdinalSettings()


def make_content(post, edition_id, data):
    metadata = {'name':post.title, 'author':post.author.pen_name, 'edition':data['edition_name'],
        'description':data['description'], 'attributes':data['attributes'],
        'observatory_edition':str(edition_id), 'publication':str(post.pk)}
    # Metadata is embedded in the immutable HTML; not protocol tag-5 CBOR metadata.
    meta = html.escape(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    content = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>'+html.escape(post.title)+
        '</title><style>body{max-width:44rem;margin:3rem auto;padding:1.5rem;background:#f4efdf;color:#233d30;font:18px/1.8 Georgia}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}details{font-size:14px}</style><body><header>The Observatory · '+
        html.escape(data['edition_name'])+'</header><h1>'+html.escape(post.title)+'</h1><p>'+html.escape(post.author.pen_name)+
        '</p><pre>'+html.escape(post.body)+'</pre><details><summary>Edition metadata</summary><pre>'+meta+'</pre></details></body></html>')
    return metadata, content


def fetch(path, *, chain=False, raw=False, limit=2000000):
    base = (settings.BITCOIN_ESPLORA_URL if chain else settings.ORDINAL_INDEX_URL).rstrip('/')
    if not base.startswith('https://'): raise ValueError('Configure an HTTPS mainnet ordinal index before minting.')
    with urlopen(Request(base+path, headers={'Accept':'application/json' if not raw else '*/*','User-Agent':'Observatory/1.0'}), timeout=12) as response:
        body = response.read(limit+1)
    if len(body)>limit: raise ValueError('Index response exceeds the limit.')
    return body if raw else json.loads(body)


def verify(edition):
    if not edition.inscription_id: return False
    iid = edition.inscription_id
    if not re.fullmatch(r'[0-9a-f]{64}i[0-9]{1,9}', iid): raise ValueError('Invalid inscription ID.')
    status = fetch('/status')
    height = chain_height()
    if status.get('chain')!='mainnet' or height is None or type(status.get('height')) is not int or status['height']<height:
        raise ValueError('Waiting for a synchronized mainnet index and confirmed block clock.')
    info = fetch('/inscription/'+iid)
    body = fetch('/content/'+iid, raw=True, limit=600000)
    if info.get('id')!=iid or hashlib.sha256(body).hexdigest()!=edition.content_hash:
        raise ValueError('Inscription content does not match this exact edition.')
    txid = iid.split('i')[0]
    tx = fetch('/tx/'+txid, chain=True)
    mined = tx.get('status',{})
    if tx.get('txid')!=txid or mined.get('confirmed') is not True or type(mined.get('block_height')) is not int or mined['block_height']>height:
        return False
    canonical = fetch('/block-height/'+str(mined['block_height']),chain=True,raw=True).decode().strip()
    if canonical!=mined.get('block_hash'): raise ValueError('Inscription block is not canonical.')
    sat = info.get('sat')
    rarity = ''
    if type(sat) is int:
        satinfo=fetch('/sat/'+str(sat))
        if satinfo.get('number')!=sat: raise ValueError('Invalid sat index response.')
        rarity=satinfo.get('rarity','')
        if rarity not in ('common','uncommon','rare','epic','legendary','mythic'): raise ValueError('Invalid sat rarity.')
    if edition.sat_mode=='special' and (type(sat) is not int or sat!=edition.requested_sat):
        raise ValueError('The inscription is not on your selected sat.')
    with transaction.atomic():
        locked = OrdinalEdition.objects.select_for_update().get(pk=edition.pk)
        if locked.inscription_id!=iid or locked.content_hash!=edition.content_hash: return False
        locked.status='minted'; locked.minted_at=locked.minted_at or timezone.now()
        locked.sat_number=sat; locked.sat_rarity=rarity; locked.txid=txid
        locked.save(update_fields=['status','minted_at','sat_number','sat_rarity','txid'])
        # The existing public post automatically displays its verified edition.
        # Never reverse withdrawal/moderation or bypass the publishing membership.
    return True
