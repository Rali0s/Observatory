import hashlib
from .voting import with_votes
from . import stripe_payments, invites
from .invite_views import pending_code
from .achievements import public_unlock, progress
from .storage import budget
from .direct_payments import ready as direct_ready
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse, JsonResponse, Http404
from django.db.models import Count
from urllib.parse import urlencode
from .taxonomy import CHANNELS, apply_tags
from .forms import PublicationCategoryForm
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods
from .forms import ProfileForm, PublishForm, SignupForm
from .membership import membership_state
from .models import AuthorProfile, Bookmark, Follow, PaymentOrder, Publication, PublicationReport
from .payments import create_checkout, payments_ready, reconcile_order


def author_profile(user):
    return AuthorProfile.objects.get_or_create(user=user, defaults={'pen_name': 'An Observatory writer'})[0]


@require_http_methods(['GET'])
@never_cache
def feed(request):
    tab = request.GET.get('tab', 'ranked')
    posts = Publication.objects.filter(is_visible=True).select_related('author','ordinal').prefetch_related('tags')
    if tab in ('following', 'saved'):
        if not request.user.is_authenticated:
            return redirect('login')
        if tab == 'following':
            posts = posts.filter(author__followers__user=request.user)
        else:
            posts = posts.filter(bookmarks__user=request.user)
    elif tab not in ('latest','ranked'):
        tab = 'ranked'
    channel=request.GET.get('channel','')
    tag=request.GET.get('tag','').removeprefix('#').casefold()
    if channel and channel not in dict(CHANNELS): raise Http404('Channel not found.')
    counts=dict(posts.order_by().values('channel').annotate(total=Count('id')).values_list('channel','total'))
    if channel: posts=posts.filter(channel=channel)
    from .models import Tag
    popular=Tag.objects.filter(publications__in=posts).annotate(total=Count('publications',distinct=True)).order_by('-total','name')[:24]
    if tag: posts=posts.filter(tags__name=tag)
    filters=urlencode({'journey':progress(request.user) if request.user.is_authenticated else None, 'tab':tab,'channel':channel,'tag':tag})
    new_posts=posts.order_by('-published_at','-pk')[:3]
    posts=with_votes(posts,request.user)
    posts=posts.order_by('-vote_count','-published_at','-pk') if tab=='ranked' else posts.order_by('-published_at','-pk')
    page=Paginator(posts,12).get_page(request.GET.get('page'))
    return render(request,'community/feed.html',{'page':page,'new_posts':new_posts,'rank_offset':page.start_index()-1,
        'journey':progress(request.user) if request.user.is_authenticated else None, 'tab':tab,'channel':channel,'channel_label':dict(CHANNELS).get(channel,'All channels'),'tag':tag,'filter_query':filters,
        'channels':[{'slug':slug,'label':label,'count':counts.get(slug,0)} for slug,label in CHANNELS], 'popular_tags':popular})


@require_http_methods(['GET'])
@never_cache
def author(request, author_id):
    profile = get_object_or_404(AuthorProfile, pk=author_id)
    from .merging import canonical_user
    canonical = canonical_user(profile.user)
    if canonical.pk != profile.user_id:
        return redirect('author', author_id=canonical.author_profile.pk)
    posts = profile.publications.filter(is_visible=True).select_related('author','ordinal').prefetch_related('tags')
    ordinal_tab=request.GET.get('tab')=='ordinals'
    if ordinal_tab: posts=posts.filter(ordinal__status='minted')
    following = request.user.is_authenticated and Follow.objects.filter(user=request.user, author=profile).exists()
    return render(request, 'community/author.html', {'profile': profile, 'showcase':public_unlock(profile.user), 'following': following, 'ordinal_tab':ordinal_tab,
        'page': Paginator(with_votes(posts,request.user).order_by('-published_at','-pk'), 12).get_page(request.GET.get('page'))})


@require_http_methods(['GET'])
@never_cache
def read(request, publication_id):
    post = get_object_or_404(with_votes(Publication.objects.select_related('author','ordinal').prefetch_related('tags'),request.user), pk=publication_id, is_visible=True)
    saved = request.user.is_authenticated and Bookmark.objects.filter(user=request.user, publication=post).exists()
    return render(request, 'community/read.html', {'post': post, 'saved': saved})


@never_cache
@require_http_methods(['GET', 'POST'])
def signup(request):
    if request.user.is_authenticated:
        return redirect('invite-landing' if pending_code(request) else 'account')
    form = SignupForm(request.POST or None)
    if request.method == 'POST':
        # Rate-limit by connection address. Configure Redis for shared production limits.
        key = 'signup:'+hashlib.sha256(request.META.get('REMOTE_ADDR', '').encode()).hexdigest()
        cache.add(key, 0, 3600)
        try:
            attempts = cache.incr(key)
        except ValueError:
            attempts = 1
            cache.set(key, attempts, 3600)
        if attempts > 10:
            return HttpResponse('Too many account attempts. Please try again later.', status=429)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                AuthorProfile.objects.create(user=user, pen_name=form.cleaned_data['pen_name'])
            login(request, user, backend="studio.auth_backend.MergedAccountBackend")
            return redirect('invite-landing' if pending_code(request) else 'account')
    return render(request, 'community/signup.html', {'form': form})


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def account(request):
    profile = author_profile(request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your author profile has been updated.')
        return redirect('account')
    return render(request, 'community/account.html', {'form': form, 'profile': profile,
        'state': membership_state(request.user), 'posts': profile.publications.all()})


def membership_context(user):
    return {'stripe_ready': stripe_payments.ready(), 'direct_ready': direct_ready(), 'state': membership_state(user), 'payments_ready': payments_ready(),
            'can_issue_invites': invites.can_issue(user),
            'orders': PaymentOrder.objects.filter(user=user).order_by('-created_at')[:10]}


@login_required
@never_cache
@require_http_methods(['GET'])
def membership(request):
    return render(request, 'community/membership.html', membership_context(request.user))


@login_required
@never_cache
@require_http_methods(['GET'])
def lockout(request):
    context = membership_context(request.user)
    if context['state']['can_publish']:
        return redirect('publish')
    return render(request, 'community/lockout.html', context)


@login_required
@never_cache
@require_http_methods(['GET'])
def membership_status(request):
    state = membership_state(request.user)
    return JsonResponse({key: state[key] for key in ['stage', 'height', 'remaining', 'days', 'deadline']})


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
@budget
def publish(request):
    if not membership_state(request.user)['can_publish']:
        return redirect('lockout')
    form = PublishForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        if request.POST.get('action') == 'publish':
            # Check again on final submission; never rely on a prior preview or browser timer.
            if not membership_state(request.user)['can_publish']:
                return redirect('lockout')
            post = form.save(commit=False)
            post.author = author_profile(request.user)
            post.save()
            apply_tags(post, form.cleaned_data['hashtags'])
            return redirect('read', publication_id=post.pk)
        if request.POST.get('action') == 'edit':
            return render(request, 'community/publish.html', {'form': form})
        return render(request, 'community/publish.html', {'form': form, 'preview': form.cleaned_data})
    return render(request, 'community/publish.html', {'form': form})


@login_required
@require_POST
def withdraw(request, publication_id):
    post = get_object_or_404(Publication, pk=publication_id, author__user=request.user)
    post.is_visible = False
    post.save(update_fields=['is_visible'])
    messages.success(request, 'Publication withdrawn. Your private writing is retained.')
    return redirect('account')


@login_required
@require_POST
def follow(request, author_id):
    profile = get_object_or_404(AuthorProfile, pk=author_id)
    from .merging import canonical_user
    canonical = canonical_user(profile.user)
    if canonical.pk != profile.user_id:
        profile = canonical.author_profile
    if profile.user_id != request.user.id:
        relation, created = Follow.objects.get_or_create(user=request.user, author=profile)
        if not created:
            relation.delete()
    return redirect('author', author_id=profile.pk)


@login_required
@require_POST
def bookmark(request, publication_id):
    post = get_object_or_404(Publication, pk=publication_id, is_visible=True)
    relation, created = Bookmark.objects.get_or_create(user=request.user, publication=post)
    if not created:
        relation.delete()
    return redirect('read', publication_id=post.pk)


@login_required
@require_POST
def report(request, publication_id):
    post = get_object_or_404(Publication, pk=publication_id, is_visible=True)
    reason = request.POST.get('reason', '').strip()
    if 1 <= len(reason) <= 1000:
        PublicationReport.objects.update_or_create(reporter=request.user, publication=post, defaults={'reason': reason, 'resolved': False})
        messages.success(request, 'Report received for moderator review.')
    else:
        messages.error(request, 'Please give a reason of up to 1,000 characters.')
    return redirect('read', publication_id=post.pk)


@login_required
@require_POST
def checkout(request):
    try:
        order = create_checkout(request.user)
        return redirect(order.checkout_url)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('membership')


@login_required
@require_POST
def check_payment(request, order_id):
    order = get_object_or_404(PaymentOrder, pk=order_id, user=request.user)
    if order.provider == 'direct':
        return redirect('bitcoin-order', order_id=order.pk)
    if not cache.add('check-payment:'+str(order.id), True, 30):
        messages.info(request, 'Please wait a moment before checking again.')
    elif order.provider == 'stripe':
        try:
            stripe_payments.reconcile(order)
            messages.info(request, 'Card payment status checked.')
        except Exception:
            messages.info(request, 'Verification is pending. Your order is retained.')
    elif payments_ready():
        try:
            reconcile_order(order)
            messages.info(request, 'Payment status checked. Access updates after verified settlement.')
        except Exception:
            messages.info(request, 'Verification is temporarily unavailable. Your order is retained.')
    return redirect('membership')


@login_required
@never_cache
@require_http_methods(['GET','POST'])
@budget
def categorize(request,publication_id):
    post=get_object_or_404(Publication,pk=publication_id,author__user=request.user)
    form=PublicationCategoryForm(request.POST or None,instance=post,initial={'hashtags':' '.join('#'+tag.name for tag in post.tags.all())})
    if request.method=='POST' and form.is_valid():
        form.save()
        apply_tags(post,form.cleaned_data['hashtags'])
        messages.success(request,'Channel and hashtags updated.')
        return redirect('account')
    return render(request,'community/categorize.html',{'post':post,'form':form})
