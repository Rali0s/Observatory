from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, When, Value, CharField, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
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


class ManageForm(forms.Form):
    label = forms.CharField(max_length=100, label='Campaign name')
    max_uses = forms.IntegerField(min_value=1, max_value=10000, label='Maximum people')
    redeem_before = forms.DateTimeField(required=False, label='Redeem before (UTC, optional)',
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type':'datetime-local'}))
    enabled = forms.BooleanField(required=False, label='Allow new redemptions')


def managed_invitations(user):
    if not invites.can_issue(user):
        raise PermissionDenied
    items = Invitation.objects.select_related('created_by')
    if not is_admin(user):
        items = items.filter(created_by=user)
    return items.annotate(management_status=Case(
        When(enabled=False, then=Value('disabled')),
        When(redeem_before__lte=timezone.now(), then=Value('expired')),
        When(uses__gte=F('max_uses'), then=Value('used')),
        default=Value('available'), output_field=CharField()))


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
    items = managed_invitations(request.user)
    totals = {'codes':items.count(), 'redemptions':items.aggregate(total=Sum('uses'))['total'] or 0,
              'available':items.filter(management_status='available').count()}
    query = request.GET.get('q', '')[:100].strip()
    status = request.GET.get('status', '')
    kind = request.GET.get('kind', '')
    if query:
        items = items.filter(Q(label__icontains=query) | Q(code_hint__icontains=query))
    if status in ('available','used','expired','disabled'):
        items = items.filter(management_status=status)
    else: status = ''
    if kind in Invitation.Kind.values:
        items = items.filter(kind=kind)
    else: kind = ''
    page = Paginator(items.order_by('-created_at','-pk'), 20).get_page(request.GET.get('page'))
    filters = request.GET.copy(); filters.pop('page', None)
    return render(request, 'community/invites.html', {'form': form, 'code': code,
        'invitations': page, 'page':page, 'totals':totals, 'query':query, 'status':status, 'kind':kind,
        'filter_query':filters.urlencode(), 'is_invite_admin': is_admin(request.user),
        'invite_link': request.build_absolute_uri('/invite/')+'#code='+code if code else None,
        'member_issuers_enabled': InviteSettings.objects.filter(pk=1, member_issuers_enabled=True).exists()})


@login_required
@never_cache
@require_http_methods(['GET','POST'])
def detail(request, invitation_id):
    invitation = get_object_or_404(managed_invitations(request.user), pk=invitation_id)
    form = ManageForm(request.POST if request.method == 'POST' else None, initial={
        'label':invitation.label, 'max_uses':invitation.max_uses,
        'redeem_before':invitation.redeem_before, 'enabled':invitation.enabled})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Serializes limit edits with both redemption and revocation.
            locked = Invitation.objects.select_for_update().get(pk=invitation.pk)
            if form.cleaned_data['max_uses'] < locked.uses:
                form.add_error('max_uses', f'At least {locked.uses} places have already been redeemed.')
            deadline = form.cleaned_data['redeem_before']
            if form.cleaned_data['enabled'] and deadline and deadline <= timezone.now():
                form.add_error('redeem_before', 'Choose a future deadline, clear it, or disable new redemptions.')
            if not form.errors:
                for field, value in form.cleaned_data.items():
                    setattr(locked, field, value)
                locked.save(update_fields=list(form.cleaned_data))
                messages.success(request, 'Invite settings saved. Existing grants are unchanged.')
                return redirect('invite-detail', invitation_id=invitation.pk)
    history = invitation.redemptions.select_related('user','user__author_profile').order_by('-redeemed_at','-pk')
    page = Paginator(history, 25).get_page(request.GET.get('page'))
    return render(request, 'community/invite_detail.html', {'invitation':invitation, 'form':form,
        'remaining':max(0,invitation.max_uses-invitation.uses),
        'percent':round(100*invitation.uses/invitation.max_uses), 'page':page,
        'now':timezone.now(), 'is_invite_admin':is_admin(request.user)})


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
