from datetime import timedelta
from django import forms
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST
from .models import MergeAttempt, WalletIdentity
from .merging import merge_accounts, primary_account, proof_valid
from .wallet_auth import session_hash, limited


class PasswordProofForm(forms.Form):
    slot = forms.ChoiceField(choices=[('owner','Current account'),('other','Other account')],label='Account to verify')
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'autocomplete':'username'}))
    password = forms.CharField(max_length=1024, widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}))


def active_attempt(request, attempt_id=None, lock=False):
    items = MergeAttempt.objects.select_for_update() if lock else MergeAttempt.objects.all()
    try:
        item = items.get(pk=attempt_id or request.session.get('merge_attempt'),owner=request.user,
            session_hash=session_hash(request),consumed_at__isnull=True,expires_at__gt=timezone.now())
    except (MergeAttempt.DoesNotExist, ValueError, forms.ValidationError):
        raise ValueError('This merge session expired. Open Merge accounts to start again.')
    return item


def record_proof(attempt, slot, user, wallet=''):
    if not user.is_active or (slot == 'owner' and user.pk != attempt.owner_id) or (slot == 'other' and user.pk == attempt.owner_id):
        raise ValueError('Choose the current account for step one and a different account for step two.')
    if slot == 'other':
        attempt.other=user
    setattr(attempt,slot+'_auth_hash',user.get_session_auth_hash())
    setattr(attempt,slot+'_wallet',wallet)
    attempt.save()


def wallet_proof(request, challenge):
    try:
        attempt=active_attempt(request,challenge.merge_attempt_id,lock=True)
        identity=WalletIdentity.objects.select_related('user').filter(address=challenge.address).first()
        if not identity:
            raise ValueError('This wallet has no existing account to merge. Link it normally from Account instead.')
        record_proof(attempt,challenge.merge_slot,identity.user,challenge.address)
    except ValueError as exc:
        return JsonResponse({'error':str(exc)},status=400)
    return JsonResponse({'ok':True,'redirect':reverse('account-merge')})


@never_cache
@login_required
@sensitive_post_parameters('password')
@require_http_methods(['GET','POST'])
def overview(request):
    try:
        attempt=active_attempt(request)
    except ValueError:
        attempt=MergeAttempt.objects.create(owner=request.user,session_hash=session_hash(request),
            expires_at=timezone.now()+timedelta(minutes=10))
        request.session['merge_attempt']=str(attempt.pk)
    needs_owner = not proof_valid(attempt, 'owner', request.user)
    form=PasswordProofForm(request.POST if request.method=='POST' else None,
        initial={'slot':'owner' if needs_owner else 'other','username':request.user.username if needs_owner else ''})
    if request.method=='POST' and form.is_valid():
        if limited(request,'merge-password'):
            form.add_error(None,'Too many attempts. Try again in five minutes.')
        else:
            user=authenticate(request,username=form.cleaned_data['username'],password=form.cleaned_data['password'])
            if user is None:
                form.add_error(None,'The account could not be verified. Check its username and password.')
            else:
                try:
                    with transaction.atomic():
                        attempt=active_attempt(request,attempt.pk,lock=True)
                        record_proof(attempt,form.cleaned_data['slot'],user)
                    return redirect('account-merge')
                except ValueError as exc:
                    form.add_error(None,str(exc))
    attempt.refresh_from_db()
    owner_verified=proof_valid(attempt,'owner',request.user)
    other=attempt.other
    other_verified=bool(other and other.is_active and proof_valid(attempt,'other',other))
    target=primary_account(request.user,other) if owner_verified and other_verified else None
    return render(request,'community/merge.html',{'attempt':attempt,'form':form,'owner_verified':owner_verified,
        'other_verified':other_verified,'other':other if other_verified else None,'target':target})


@never_cache
@login_required
@require_POST
def confirm(request):
    if request.POST.get('confirm')!='yes':
        messages.error(request,'Review and confirm the account merge first.')
        return redirect('account-merge')
    try:
        attempt=active_attempt(request)
        target=merge_accounts(attempt.pk,request.user.pk,session_hash(request),request.POST.get('target'))
    except (ValueError,MergeAttempt.DoesNotExist) as exc:
        messages.error(request,str(exc))
        return redirect('account-merge')
    request.session.pop('merge_attempt',None)
    login(request,target,backend='studio.auth_backend.MergedAccountBackend')
    messages.success(request,'Accounts merged. Your writing, access, and linked wallets are together. Either original password login still works.')
    return redirect('account')


@never_cache
@login_required
@require_POST
def cancel(request):
    MergeAttempt.objects.filter(pk=request.session.pop('merge_attempt',None),owner=request.user,
        consumed_at__isnull=True).update(consumed_at=timezone.now())
    return redirect('account')
