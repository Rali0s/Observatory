from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from embit.script import address_to_scriptpubkey
from embit.networks import NETWORKS
from studio.models import ReceivingAddress


class Command(BaseCommand):
    help='Import unused mainnet receiving addresses from your own watch-only wallet export (one address per line). Never import seeds or private keys.'

    def add_arguments(self,parser): parser.add_argument('file')

    @transaction.atomic
    def handle(self,*args,**options):
        values=Path(options['file']).read_text(encoding='utf-8').splitlines()
        count=0
        for value in values:
            address=value.strip()
            if not address: continue
            try:
                script=address_to_scriptpubkey(address)
                if script.address(NETWORKS['main'])!=address: raise ValueError()
            except Exception: raise CommandError('File contains an invalid or non-mainnet address; nothing was imported.')
            _,created=ReceivingAddress.objects.get_or_create(address=address);count+=created
        self.stdout.write(f'Imported {count} unique receiving addresses. Confirm these are unused addresses from a wallet you control before enabling checkout.')
