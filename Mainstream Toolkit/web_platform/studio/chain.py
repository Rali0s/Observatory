"""Fetch public chain data only; sends no account or manuscript information."""
import json
import re
from urllib.request import urlopen
from django.conf import settings
from django.utils import timezone
from .models import ChainTip


def sync_chain():
    base = settings.BITCOIN_ESPLORA_URL.rstrip('/')
    if not base.startswith('https://'):
        raise ValueError('Use an HTTPS Bitcoin mainnet Esplora endpoint.')
    def get(path):
        with urlopen(base+path, timeout=10) as response:
            return response.read(20000).decode('utf-8')
    block_hash = get('/blocks/tip/hash').strip()
    if not re.fullmatch('[0-9a-f]{64}', block_hash):
        raise ValueError('Invalid tip hash.')
    block = json.loads(get('/block/'+block_hash))
    height = block['height']
    if type(height) is not int or height < 0 or block['id'] != block_hash:
        raise ValueError('Invalid tip response.')
    if get('/block-height/'+str(height)).strip() != block_hash:
        raise ValueError('Tip changed during verification; retry later.')
    ChainTip.objects.update_or_create(pk=1, defaults={'height': height, 'block_hash': block_hash, 'observed_at': timezone.now()})
    return height
