import time
from django.core.management.base import BaseCommand
from studio.chain import sync_chain
from studio.models import PaymentOrder, OrdinalEdition
from studio.ordinals import verify as verify_ordinal
from studio.payments import payments_ready, reconcile_order
from studio.direct_payments import reconcile as reconcile_direct
from django.utils import timezone


class Command(BaseCommand):
    help = 'Verify Bitcoin height and reconcile unpaid BTCPay invoices. Never deletes accounts.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')

    def handle(self, *args, **options):
        while True:
            try:
                height = sync_chain()
                self.stdout.write(f'Bitcoin mainnet tip verified: {height}')
            except Exception:
                self.stderr.write('Block verification unavailable; publishing and new checkout wait for fresh data.')
            if payments_ready():
                orders = PaymentOrder.objects.filter(applied_at_block__isnull=True,
                    provider_invoice_id__isnull=False, provider='btcpay').order_by('last_checked_at', 'created_at')[:100]
                for order in orders:
                    try:
                        reconcile_order(order)
                    except Exception:
                        self.stderr.write(f'Invoice reconciliation deferred for order {order.id}.')
                    finally:
                        PaymentOrder.objects.filter(pk=order.pk).update(last_checked_at=timezone.now())
            for order in PaymentOrder.objects.filter(provider='direct', applied_at_block__isnull=True).order_by('last_checked_at','created_at')[:100]:
                try:
                    reconcile_direct(order)
                except Exception:
                    self.stderr.write(f'Direct order reconciliation deferred: {order.id}')
                finally:
                    PaymentOrder.objects.filter(pk=order.pk).update(last_checked_at=timezone.now())
            for edition in OrdinalEdition.objects.filter(status='submitted').order_by('checked_at','created_at')[:25]:
                try:
                    verify_ordinal(edition)
                except Exception:
                    self.stderr.write(f'Ordinal verification deferred: {edition.id}')
                finally:
                    OrdinalEdition.objects.filter(pk=edition.pk).update(checked_at=timezone.now())
            if not options['loop']:
                break
            time.sleep(60)
