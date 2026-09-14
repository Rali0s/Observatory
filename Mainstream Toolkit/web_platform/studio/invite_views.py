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
        'invite_link': request.build_absolute_uri('/invite/')+'#code='+code if code else None,
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
    try:
        access = redeem_access(request, request.POST.get('code', '')[:100])
        messages.success(request, 'Lifetime publishing access unlocked.' if access.lifetime
            else f'Free publishing access unlocked until {access.expires_at:%B %d, %Y}.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('membership')


class RedeemForm(forms.Form):
    code = forms.RegexField(regex=r'(?i)^OBS-[A-F0-9]{32}$', max_length=36, label='Invite code',
        widget=forms.TextInput(attrs={'autocomplete':'off','spellcheck':'false','autocapitalize':'characters'}),
        error_messages={'invalid':'Enter the full invite code beginning with OBS-.'})

    def clean_code(self):
        return self.cleaned_data['code'].upper()


def pending_code(request):
    from django.utils import timezone
    pending = request.session.get('pending_invitation', {})
    if isinstance(pending, dict) and pending.get('expires', 0) > timezone.now().timestamp():
        return pending.get('code', '')
    request.session.pop('pending_invitation', None)
    return ''


def redeem_access(request, code):
    key = f'invite-redeem:{request.user.pk}'
    cache.add(key, 0, 3600)
    try:
        attempts = cache.incr(key)
    except ValueError:
        cache.set(key, 1, 3600)
        attempts = 1
    if attempts > 20:
        raise ValueError('Too many invite attempts. Try again in an hour.')
    access = invites.redeem(request.user, code)
    request.session.pop('pending_invitation', None)
    return access


@never_cache
@require_http_methods(['GET', 'POST'])
def landing(request):
    from django.urls import reverse
    from django.utils import timezone
    from .membership import membership_state
    remembered = pending_code(request)
    form = RedeemForm(request.POST if request.method == 'POST' else None, initial={'code': remembered})
    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code']
        if request.user.is_authenticated:
            try:
                access = redeem_access(request, code)
                messages.success(request, 'Lifetime publishing access unlocked.' if access.lifetime
                    else f'Free publishing access unlocked until {access.expires_at:%B %d, %Y}.')
                return redirect('invite-landing')
            except ValueError as exc:
                form.add_error('code', str(exc))
        else:
            action = request.POST.get('action')
            if action in ('signup', 'signin'):
                request.session['pending_invitation'] = {'code': code, 'expires': timezone.now().timestamp()+3600}
                return redirect(reverse('signup') if action == 'signup' else reverse('login')+'?next='+reverse('invite-landing'))
            form.add_error(None, 'Choose Create account or Sign in to continue.')
    response = render(request, 'community/invite_landing.html', {'form': form,
        'state': membership_state(request.user) if request.user.is_authenticated else None})
    response['Referrer-Policy'] = 'no-referrer'
    return response
