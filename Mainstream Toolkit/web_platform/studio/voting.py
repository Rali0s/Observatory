from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Value, BooleanField
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .models import Publication, Upvote


def with_votes(posts,user):
    return posts.annotate(vote_count=Count('upvotes',distinct=True),
        has_upvoted=Exists(Upvote.objects.filter(publication_id=OuterRef('pk'),user=user)) if user.is_authenticated else Value(False,output_field=BooleanField()))


@login_required
@require_POST
def vote(request,publication_id):
    action=request.POST.get('action')
    if action not in ('upvote','remove'): return HttpResponseBadRequest('Choose upvote or remove.')
    with transaction.atomic():
        post=get_object_or_404(Publication.objects.select_for_update(),pk=publication_id,is_visible=True)
        if post.author.user_id!=request.user.pk:
            if action=='upvote': Upvote.objects.get_or_create(user=request.user,publication=post)
            else: Upvote.objects.filter(user=request.user,publication=post).delete()
    target=request.POST.get('next','')
    if target.startswith('/') and url_has_allowed_host_and_scheme(target,{request.get_host()},require_https=request.is_secure()):
        return redirect(target)
    return redirect('read',publication_id=post.pk)
