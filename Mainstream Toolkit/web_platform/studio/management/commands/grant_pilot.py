from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from studio.models import AccessGrant


class Command(BaseCommand):
    help = 'Grant pilot capabilities to an existing account. Does not create a payment or subscription.'

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['username'])
        except get_user_model().DoesNotExist:
            raise CommandError('Create this account first with createsuperuser or the Django admin.')
        grant, created = AccessGrant.objects.get_or_create(user=user)
        if not created:
            self.stdout.write('A grant already exists; inspect its limits and status in the admin.')
        else:
            self.stdout.write(self.style.SUCCESS('Pilot access granted: 3 projects, up to 20,000 words per revision.'))
