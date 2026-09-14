import hashlib
import json
import re
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from .models import Publication, OrdinalEdition
from .ordinal_forms import EditionForm, InscriptionForm, ListingForm
from .ordinals import controls, make_content, verify
from .storage import budget


@never_cache
@require_http_methods(['GET','POST'])
def ordinal(request, publication_id):
    post=get_object_or_404(Publication.objects.select_related('author'),pk=publication_id,is_visible=True)
    owner=request.user.is_authenticated and post.author.user_id==request.user.pk
    edition=OrdinalEdition.objects.filter(publication=post).first()
    flags=controls()
    form=EditionForm()
    inscription_form=InscriptionForm()
    listing_form=ListingForm(initial={'marketplace_url':edition.marketplace_url if edition else ''})
    if request.method=='POST':
        if not owner: return HttpResponse('Only the author can manage this edition.',status=403)
        action=request.POST.get('action')
        if action=='prepare':
            if not flags.enabled: return HttpResponse('New minting is paused.',status=403)
            form=EditionForm(request.POST)
            if form.is_valid():
                if form.cleaned_data['sat_mode']=='special' and not flags.special_sats_enabled:
                    form.add_error('sat_mode','Special-sat minting is paused.')
                else:
                    from .storage import save_content
                    def create():
                        Publication.objects.select_for_update().get(pk=post.pk)
                        if OrdinalEdition.objects.filter(publication=post).exists(): return
                        item=OrdinalEdition(publication=post,sat_mode=form.cleaned_data['sat_mode'],requested_sat=form.cleaned_data['requested_sat'])
                        item.metadata,item.content=make_content(post,item.pk,form.cleaned_data)
                        item.content_hash=hashlib.sha256(item.content.encode()).hexdigest()
                        item.save()
                    try: save_content(request.user,create)
                    except ValueError as exc: form.add_error(None,str(exc))
                    else: return redirect('ordinal',publication_id=post.pk)
        elif action=='inscription' and edition and edition.status!='minted':
            inscription_form=InscriptionForm(request.POST)
            if inscription_form.is_valid():
                iid=inscription_form.cleaned_data['inscription_id']
                with transaction.atomic():
                    locked=OrdinalEdition.objects.select_for_update().get(pk=edition.pk)
                    if locked.status!='minted':
                        if OrdinalEdition.objects.filter(inscription_id=iid).exclude(pk=locked.pk).exists():
                            inscription_form.add_error('inscription_id','This inscription is already linked.')
                        else:
                            locked.inscription_id=iid; locked.status='submitted'; locked.save(update_fields=['inscription_id','status'])
                            return redirect('ordinal',publication_id=post.pk)
        elif action=='check' and edition:
            if cache.add('ordinal-check:'+str(edition.pk),True,30):
                try:
                    confirmed=verify(edition)
                    messages.success(request,'Edition verified and displayed on your public post.') if confirmed else messages.info(request,'Waiting for six confirmations or an inscription ID.')
                except Exception:
                    messages.error(request,'Not verified yet. Check the inscription ID, exact edition file, selected sat, and index configuration.')
            return redirect('ordinal',publication_id=post.pk)
        elif action=='listing' and edition and edition.status=='minted':
            listing_form=ListingForm(request.POST)
            if listing_form.is_valid():
                edition.marketplace_url=listing_form.cleaned_data['marketplace_url']; edition.save(update_fields=['marketplace_url'])
                return redirect('ordinal',publication_id=post.pk)
        else: return HttpResponse('Invalid action.',status=400)
    if not owner and (not edition or edition.status!='minted'): edition=None
    return render(request,'community/ordinal.html',{'post':post,'owner':owner,'edition':edition,'flags':flags,
        'form':form,'inscription_form':inscription_form,'listing_form':listing_form,'index_ready':bool(settings.ORDINAL_INDEX_URL)})


@login_required
@never_cache
@require_POST
def ordinal_wallet(request, publication_id):
    with transaction.atomic():
        edition=get_object_or_404(OrdinalEdition.objects.select_for_update(),publication_id=publication_id,publication__author__user=request.user,publication__is_visible=True)
        action=request.POST.get('action')
        if action=='begin':
            if not controls().enabled or not settings.ORDINAL_INDEX_URL: return JsonResponse({'error':'Minting is paused or verification is not configured.'},status=403)
            if edition.sat_mode!='regular' or edition.status!='prepared': return JsonResponse({'error':'This edition already has an attempt. Check its status before trying again.'},status=409)
            edition.status='awaiting'; edition.save(update_fields=['status'])
            return JsonResponse({'content':edition.content,'contentType':'text/html','payloadType':'PLAIN_TEXT'})
        if action=='broadcast' and edition.status=='awaiting':
            txid=request.POST.get('txid','')
            if not re.fullmatch('[0-9a-f]{64}',txid): return JsonResponse({'error':'Invalid transaction ID.'},status=400)
            edition.txid=txid; edition.save(update_fields=['txid'])
            # Wallet txId may be commit rather than reveal. Do not invent an i0 ID.
            return JsonResponse({'ok':True})
        return JsonResponse({'error':'Invalid transition.'},status=409)


@login_required
@never_cache
@require_http_methods(['GET'])
def ordinal_download(request, publication_id):
    edition=get_object_or_404(OrdinalEdition,publication_id=publication_id,publication__author__user=request.user)
    metadata=request.GET.get('format')=='metadata'
    response=HttpResponse(json.dumps(edition.metadata,ensure_ascii=False,indent=2) if metadata else edition.content,
        content_type='application/json' if metadata else 'text/html; charset=utf-8')
    response['Content-Disposition']='attachment; filename="observatory-edition.'+('json' if metadata else 'html')+'"'
    response['Content-Security-Policy']="sandbox; default-src 'none'; style-src 'unsafe-inline'"
    return response

@login_required
@never_cache
@require_http_methods(['GET'])
def ordinal_publish(request):
    from django.core.paginator import Paginator
    posts=Publication.objects.filter(author__user=request.user,is_visible=True).select_related('ordinal').order_by('-published_at','-pk')
    return render(request,'community/ordinal_publish.html',{'page':Paginator(posts,12).get_page(request.GET.get('page')),
        'flags':controls(),'index_ready':bool(settings.ORDINAL_INDEX_URL)})
