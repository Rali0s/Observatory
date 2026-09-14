from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from . import marketplace as market
from .models import OrdinalEdition, OrdinalHolding, OrdinalListing, OrdinalTrade


@never_cache
@require_GET
def edition(request, edition_id):
    item = get_object_or_404(OrdinalEdition.objects.select_related('publication__author'), pk=edition_id,
        status='minted', publication__is_visible=True)
    listing = item.listings.filter(status__in=['active', 'draft']).first()
    owns = request.user.is_authenticated and OrdinalHolding.objects.filter(edition=item,
        address__in=request.user.wallet_identities.values('address')).exists()
    return render(request, 'community/market_edition.html', {'edition': item, 'listing': listing,
        'trading_ready': market.ready(), 'owns': owns,
        'attempts': OrdinalTrade.objects.filter(listing__edition=item, buyer=request.user).order_by('-created_at')[:10] if request.user.is_authenticated else []})


def limit(request):
    if not cache.add(f'market-action:{request.user.pk}:{request.path}:{request.POST.get("action", "prepare")}', True, 3):
        raise ValueError('Please wait a few seconds before trying again.')


@login_required
@require_POST
def listing_action(request, edition_id):
    item = get_object_or_404(OrdinalEdition, pk=edition_id, status='minted', publication__is_visible=True)
    try:
        limit(request)
        action = request.POST.get('action')
        if action == 'prepare':
            listing = market.create_listing(request.user, item, int(request.POST.get('price_sats', '0')), request.POST.get('payout_address', ''))
            return JsonResponse({'id': str(listing.pk), 'psbt': listing.unsigned_psbt, 'address': listing.seller_address})
        listing = get_object_or_404(OrdinalListing, pk=request.POST.get('listing_id'), edition=item, seller=request.user)
        if action == 'activate':
            market.activate_listing(listing, request.POST.get('psbt', ''))
            return JsonResponse({'ok': True})
        if action == 'resume' and listing.status == 'draft':
            return JsonResponse({'id': str(listing.pk), 'psbt': listing.unsigned_psbt, 'address': listing.seller_address})
        if action == 'cancel':
            with transaction.atomic():
                locked = OrdinalListing.objects.select_for_update().get(pk=listing.pk)
                if locked.status not in ('draft', 'active'):
                    raise ValueError('This listing is already closed.')
                locked.status = 'cancelled'
                locked.save(update_fields=['status'])
            return JsonResponse({'ok': True})
        raise ValueError('Invalid listing action.')
    except (ValueError, TypeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception:
        return JsonResponse({'error': 'The Bitcoin index is unavailable. No listing was changed.'}, status=503)


@login_required
@require_POST
def purchase(request, listing_id):
    listing = get_object_or_404(OrdinalListing.objects.select_related('edition__publication'), pk=listing_id)
    try:
        limit(request)
        trade = market.create_trade(request.user, listing, request.POST.get('payment_address', ''),
            request.POST.get('receive_address', ''), int(request.POST.get('fee_sats', '0')), request.POST.get('payment_public_key', ''))
        from django.urls import reverse
        return JsonResponse({'redirect': reverse('market-trade', args=[trade.pk])})
    except (ValueError, TypeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception:
        return JsonResponse({'error': 'Purchase preparation is unavailable. Check your existing attempts before retrying.'}, status=503)


@login_required
@never_cache
@require_GET
def trade(request, trade_id):
    item = get_object_or_404(OrdinalTrade.objects.select_related('listing__edition__publication'), pk=trade_id, buyer=request.user)
    return render(request, 'community/market_trade.html', {'trade': item, 'trading_ready': market.ready(),
        'payment_indexes': [i for i in range(len(market.decode(item.unsigned_psbt).inputs)) if i != 1]})


@login_required
@require_POST
def trade_action(request, trade_id):
    item = get_object_or_404(OrdinalTrade, pk=trade_id, buyer=request.user)
    try:
        limit(request)
        action = request.POST.get('action')
        if action == 'submit':
            market.submit_trade(item, request.POST.get('psbt', ''))
        elif action == 'check':
            market.reconcile_trade(item)
        elif action == 'abandon':
            # Only unbroadcast attempts can be replaced. No signed bytes were accepted.
            with transaction.atomic():
                locked = OrdinalTrade.objects.select_for_update().get(pk=item.pk)
                if locked.status != 'prepared' or locked.raw_transaction:
                    raise ValueError('A broadcast attempt cannot be abandoned. Check its status.')
                locked.status = 'conflict'
                locked.save(update_fields=['status'])
        else:
            raise ValueError('Invalid purchase action.')
        item.refresh_from_db()
        return JsonResponse({'ok': True, 'status': item.get_status_display(), 'txid': item.txid})
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception:
        return JsonResponse({'error': 'Verification is temporarily unavailable. Your purchase attempt is retained.'}, status=503)


@login_required
@never_cache
@require_GET
def collection(request):
    addresses = request.user.wallet_identities.filter(address__startswith='bc1p').values_list('address', flat=True)
    holdings = OrdinalHolding.objects.filter(address__in=addresses, edition__publication__is_visible=True).select_related('edition__publication__author').order_by('-checked_at', 'pk')
    return render(request, 'community/collection.html', {'addresses': addresses,
        'page': Paginator(holdings, 24).get_page(request.GET.get('page')), 'index_ready': bool(settings.ORDINAL_INDEX_URL)})


@login_required
@require_POST
def refresh_collection(request):
    if not cache.add('collection-refresh:' + str(request.user.pk), True, 60):
        messages.info(request, 'Please wait one minute between collection checks.')
        return redirect('collection')
    addresses = list(request.user.wallet_identities.filter(address__startswith='bc1p').values_list('address', flat=True))
    try:
        market.synced_index()
        # Discover inscriptions held by proven ordinal addresses; only map known editions.
        ids = set()
        for address in addresses:
            outputs = market.fetch('/outputs/' + address + '?type=inscribed')
            if not isinstance(outputs, list) or len(outputs) > 1000:
                raise ValueError('Collection exceeds the supported index response size.')
            for output in outputs:
                ids.update(output.get('inscriptions', []))
        known = OrdinalEdition.objects.filter(status='minted', inscription_id__in=ids)
        # Also recheck prior holdings so outgoing transfers do not remain in the collection.
        previous = OrdinalEdition.objects.filter(holding__address__in=addresses)
        for item in (known | previous).distinct()[:100]:
            market.holding(item)
        messages.success(request, 'Collection checked against the Bitcoin index.')
    except Exception:
        messages.error(request, 'Collection verification is unavailable or an output is unsupported. Previous observations are retained with their check time; they are not proof of current ownership.')
    return redirect('collection')
