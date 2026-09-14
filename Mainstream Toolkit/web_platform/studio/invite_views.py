from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from . import invites
from .access import is_admin
from .models import Invitation, InviteSettings


class IssueForm(forms.Form):
    label = forms.CharField(max_length=100, label='Campaign name')
    kind = forms.ChoiceField(choices=Invitation.Kind.choices, label='Access pass')
    max_uses = forms.IntegerField(min_value=1, max_value=10000, initial=1, label='Maximum people')
    redeem_before = forms.DateTimeField(required=False, label='Redeem before (UTC, optional)',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def dashboard(request):
    if not invites.can_issue(request.user):
        raise PermissionDenied
    code = None
    form = IssueForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            _, code = invites.issue(request.user, **form.cleaned_data)
            form = IssueForm()
        except ValueError as exc:
            form.add_error(None, str(exc))
    items = Invitation.objects.select_related('created_by').order_by('-created_at')
    if not is_admin(request.user):
        items = items.filter(created_by=request.user)
    return render(request, 'community/invites.html', {'form': form, 'code': code,
        'invitations': items[:100], 'is_invite_admin': is_admin(request.user),
        'member_issuers_enabled': InviteSettings.objects.filter(pk=1, member_issuers_enabled=True).exists()})


@login_required
@require_POST
def settings(request):
    if not is_admin(request.user):
        raise PermissionDenied
    InviteSettings.objects.update_or_create(pk=1, defaults={
        'member_issuers_enabled': request.POST.get('enabled') == 'yes'})
    messages.success(request, 'Invite issuing permissions updated.')
    return redirect('invites')


@login_required
@require_POST
def revoke(request, invitation_id):
    if not invites.can_issue(request.user):
        raise PermissionDenied
    items = Invitation.objects.all()
    if not is_admin(request.user):
        items = items.filter(created_by=request.user)
    invitation = get_object_or_404(items, pk=invitation_id)
    # UPDATE waits on any redemption lock; existing access remains intact.
    items.filter(pk=invitation.pk).update(enabled=False)
    messages.success(request, 'Code disabled. Previously redeemed passes remain active.')
    return redirect('invites')


@login_required
@require_POST
def redeem(request):
    key = f'invite-redeem:{request.user.pk}'
    cache.add(key, 0, 3600)
    try:
        attempts = cache.incr(key)
    except ValueError:
        cache.set(key, 1, 3600)
        attempts = 1
    if attempts > 20:
        messages.error(request, 'Too many invite attempts. Try again in an hour.')
    else:
        try:
            code = request.POST.get('code', '')
            if not 10 <= len(code) <= 100:
                raise ValueError('Enter a valid invite code.')
            access = invites.redeem(request.user, code)
            messages.success(request, 'Lifetime publishing access unlocked.' if access.lifetime
                else f'Free publishing access unlocked until {access.expires_at:%B %d, %Y}.')
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect('membership')
