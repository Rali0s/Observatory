"""Read classical Ordinal rarity from confirmed wallet outputs. Never move sats."""
import re
from django.core import signing
from .models import WalletIdentity
from .ordinals import fetch
from .membership import chain_height

MAX_SAT=2099999997689999
PAGE_SIZE=12


def boundaries(start,end,height):
    """Yield first sats of mined blocks in a range; all other sats are common."""
    base=0
    for epoch in range(33):
        subsidy=5000000000 >> epoch
        epoch_end=base+210000*subsidy
        lo,hi=max(start,base),min(end,epoch_end)
        if lo<hi:
            block=max(0,(lo-base+subsidy-1)//subsidy)
            last=min(209999,(hi-1-base)//subsidy,height-epoch*210000)
            while block<=last:
                number=base+block*subsidy
                h=epoch*210000+block
                rarity='mythic' if h==0 else 'legendary' if h%1260000==0 else 'epic' if h%210000==0 else 'rare' if h%2016==0 else 'uncommon'
                yield number,rarity,h
                block+=1
        base=epoch_end


def linked(user,address):
    if not WalletIdentity.objects.filter(user=user,address=address).exists():
        raise ValueError('Link this wallet with a signature before loading its sats.')


def synchronized():
    status=fetch('/status')
    height=chain_height()
    if height is None or status.get('chain')!='mainnet' or status.get('sat_index') is not True or status.get('rune_index') is not True or type(status.get('height')) is not int or status['height']<height or status.get('unrecoverably_reorged') is True:
        raise ValueError('Sat discovery is waiting for a synchronized Bitcoin index. Try again shortly.')
    return height


def output_ranges(info,address,outpoint,value):
    if (info.get('address')!=address or info.get('outpoint')!=outpoint or info.get('indexed') is not True or info.get('spent') is not False or
        info.get('value')!=value or type(value) is not int or value<=0):
        raise ValueError('The sat index does not match this wallet output.')
    # Do not suggest bundles that already contain inscriptions or runes.
    if info.get('inscriptions')!=[] or info.get('runes')!={}:return None
    ranges=info.get('sat_ranges')
    if not isinstance(ranges,list) or len(ranges)>10000:raise ValueError('Sat ranges are unavailable for this output.')
    total=0
    for pair in ranges:
        if not isinstance(pair,list) or len(pair)!=2 or any(type(n) is not int for n in pair) or not 0<=pair[0]<pair[1]<=MAX_SAT+1:
            raise ValueError('Invalid sat range response.')
        total+=pair[1]-pair[0]
    if total!=value:raise ValueError('Sat range total does not match the wallet balance.')
    return ranges


def inventory(user,address,page=0):
    linked(user,address)
    height=synchronized()
    outputs=fetch('/address/'+address+'/utxo',chain=True)
    if not isinstance(outputs,list) or len(outputs)>10000:raise ValueError('This wallet is too large for one scan.')
    confirmed=[u for u in outputs if isinstance(u,dict) and u.get('status',{}).get('confirmed') is True and type(u['status'].get('block_height')) is int and u['status']['block_height']<=height]
    confirmed.sort(key=lambda u:(str(u.get('txid')),u.get('vout',-1)))
    chosen=confirmed[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    candidates=[];excluded=0;incomplete=False
    for utxo in chosen:
        txid,index=utxo.get('txid'),utxo.get('vout')
        if not isinstance(txid,str) or not re.fullmatch('[0-9a-f]{64}',txid) or type(index) is not int or not 0<=index<=0xffffffff:
            raise ValueError('Invalid wallet output.')
        point=f'{txid}:{index}'
        ranges=output_ranges(fetch('/output/'+point),address,point,utxo.get('value'))
        if ranges is None:excluded+=1;continue
        offset=0
        for start,end in ranges:
            for sat,rarity,block in boundaries(start,end,height):
                if len(candidates)>=200:
                    incomplete=True;break
                data={'address':address,'outpoint':point,'sat':sat,'offset':offset+sat-start,'user':user.pk}
                candidates.append({'sat':sat,'rarity':rarity,'block':block,'offset':data['offset'],'outpoint':point,
                    'token':signing.dumps(data,salt='ordinal-sat-choice'),
                    'label':f'{rarity.title()} · sat {sat:,} · block {block:,} · offset {data["offset"]:,}'})
            offset+=end-start
    return {'items':candidates,'next_page':page+1 if (page+1)*PAGE_SIZE<len(confirmed) else None,
        'excluded_outputs':excluded,'truncated':incomplete,'scanned':len(chosen),'total_outputs':len(confirmed)}


def selection(user,token):
    try:
        data=signing.loads(token,salt='ordinal-sat-choice',max_age=600)
        if data.get('user')!=user.pk:raise ValueError()
        linked(user,data['address'])
        height=synchronized()
        txid,index=data['outpoint'].split(':')
        tx=fetch('/tx/'+txid,chain=True)
        status=tx.get('status',{})
        if tx.get('txid')!=txid or status.get('confirmed') is not True or type(status.get('block_height')) is not int or status['block_height']>height:
            raise ValueError()
        actual=tx['vout'][int(index)]
        if actual.get('scriptpubkey_address')!=data['address'] or fetch('/tx/'+txid+'/outspend/'+index,chain=True).get('spent') is not False:
            raise ValueError()
        canonical=fetch('/block-height/'+str(status['block_height']),chain=True,raw=True).decode().strip()
        if canonical!=status.get('block_hash'):raise ValueError()
        ranges=output_ranges(fetch('/output/'+data['outpoint']),data['address'],data['outpoint'],actual['value'])
        if ranges is None:raise ValueError()
        offset=0
        for start,end in ranges:
            if start<=data['sat']<end and offset+data['sat']-start==data['offset']:
                match=next(boundaries(data['sat'],data['sat']+1,height),None)
                if match:
                    return {**data,'rarity':match[1]}
            offset+=end-start
        raise ValueError()
    except (signing.BadSignature,KeyError,ValueError,TypeError,IndexError,AttributeError):
        raise ValueError('This sat selection expired, moved, or is no longer available. Load your wallet sats again.')
