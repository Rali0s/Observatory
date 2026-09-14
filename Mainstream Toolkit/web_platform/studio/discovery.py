from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import AuthorProfile, OrdinalEdition


@never_cache
@require_GET
def authors(request):
    query = request.GET.get('q', '').strip()[:100]
    profiles = AuthorProfile.objects.filter(user__is_active=True)
    if query:
        profiles = profiles.filter(Q(pen_name__icontains=query) | Q(bio__icontains=query))
    profiles = profiles.annotate(
        publication_count=Count('publications', filter=Q(publications__is_visible=True), distinct=True),
        ordinal_count=Count('publications', filter=Q(publications__is_visible=True, publications__ordinal__status='minted'), distinct=True),
        follower_count=Count('followers', distinct=True))
    if request.GET.get('ordinals') == '1':
        profiles = profiles.filter(ordinal_count__gt=0)
    return render(request, 'community/authors.html', {'q': query, 'ordinals_only': request.GET.get('ordinals') == '1',
        'filter_query': urlencode({'q': query, 'ordinals': request.GET.get('ordinals', '')}),
        'page': Paginator(profiles.order_by('pen_name', 'pk'), 24).get_page(request.GET.get('page'))})


@never_cache
@require_GET
def ordinals(request):
    query = request.GET.get('q', '').strip()[:100]
    editions = OrdinalEdition.objects.filter(status='minted', publication__is_visible=True).select_related('publication__author')
    if query:
        editions = editions.filter(Q(publication__title__icontains=query) | Q(publication__author__pen_name__icontains=query) | Q(inscription_id__icontains=query))
    if request.GET.get('sale') == '1':
        editions = editions.filter(listings__status='active').distinct()
    return render(request, 'community/ordinal_directory.html', {'q': query, 'sale_only': request.GET.get('sale') == '1',
        'filter_query': urlencode({'q': query, 'sale': request.GET.get('sale', '')}),
        'page': Paginator(editions.order_by('-minted_at', 'pk'), 24).get_page(request.GET.get('page'))})
