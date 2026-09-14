from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods
from .models import PaymentOrder
from .direct_payments import create_order,reconcile


@login_required
@never_cache
@require_http_methods(['GET'])
def wallet(request):
    from .direct_payments import ready
    return render(request,'community/wallet.html',{'checkout_ready':ready(),
        'orders':PaymentOrder.objects.filter(user=request.user,provider='direct').order_by('-created_at')[:5]})


@login_required
@require_POST
def start(request):
    if not cache.add(f'bitcoin-start:{request.user.pk}',True,15):
        messages.info(request,'Please wait a moment before requesting another quote.')
        return redirect('membership')
    try:
        order=create_order(request.user)
        return redirect('bitcoin-order',order_id=order.id)
    except Exception:
        messages.error(request,'Bitcoin checkout is unavailable. Your account has not been charged; please try again later.')
        return redirect('membership')


@login_required
@never_cache
@require_http_methods(['GET','POST'])
def order_view(request,order_id):
    order=get_object_or_404(PaymentOrder,pk=order_id,user=request.user,provider='direct')
    if request.method=='POST':
        if cache.add('direct-check:'+str(order.pk),True,20):
            try: reconcile(order)
            except Exception: messages.info(request,'Verification is unavailable. Your payment order is retained.')
        return redirect('bitcoin-order',order_id=order.pk)
    return render(request,'community/bitcoin.html',{'order':order,'expired':timezone.now()>=order.quote_expires,
        'payment':{'address':order.address,'sats':order.amount_sats,'expires':order.quote_expires.isoformat(),'paid':order.applied_at_block is not None}})
