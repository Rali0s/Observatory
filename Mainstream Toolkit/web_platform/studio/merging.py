"""Verified, transactional consolidation. Retired accounts retain login aliases and audit data."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from . import models as m


def canonical_user(user):
    # Targets are flattened when a previously consolidated account merges again.
    merge = m.AccountMerge.objects.filter(source=user).first()
    return merge.target if merge else user


def priority(user):
    return (int(user.is_superuser), int(user.is_staff),
        int(m.PublishingMembership.objects.filter(user=user).exists() or
            m.PaymentOrder.objects.filter(user=user, applied_at_block__isnull=False).exists()),
        int(m.WalletIdentity.objects.filter(user=user).exists()))


def primary_account(first, second):
    return second if priority(second) > priority(first) else first


def lock_order(order):
    """Reject a stale worker snapshot after a merge; retry with the current owner."""
    get_user_model().objects.select_for_update().get(pk=order.user_id)
    locked = m.PaymentOrder.objects.select_for_update().get(pk=order.pk)
    if locked.user_id != order.user_id:
        raise ValueError('Order owner changed. Retry payment verification.')
    return locked


def proof_valid(attempt, slot, user):
    if getattr(attempt, slot+'_auth_hash') != user.get_session_auth_hash():
        return False
    address = getattr(attempt, slot+'_wallet')
    return not address or m.WalletIdentity.objects.filter(user=user, address=address).exists()


def move_unique(model, source, target, keys, field='user', retain_duplicates=False):
    for row in model.objects.filter(**{field: source}).order_by('pk'):
        match = {field: target, **{key: getattr(row, key) for key in keys}}
        if model.objects.filter(**match).exists():
            if not retain_duplicates:
                row.delete()
        else:
            setattr(row, field, target)
            row.save(update_fields=[field])


def merge_accounts(attempt_id, owner_id, bound_session, expected_target):
    with transaction.atomic():
        # Always lock account IDs in ascending order, then the attempt.
        snapshot = m.MergeAttempt.objects.get(pk=attempt_id, owner_id=owner_id)
        if not snapshot.other_id:
            raise ValueError('Verify both accounts before merging.')
        users = {u.pk: u for u in get_user_model().objects.select_for_update().filter(
            pk__in=[owner_id, snapshot.other_id]).order_by('pk')}
        attempt = m.MergeAttempt.objects.select_for_update().get(pk=attempt_id)
        first, second = users[owner_id], users[snapshot.other_id]
        if (attempt.consumed_at or attempt.expires_at <= timezone.now() or
            attempt.session_hash != bound_session or attempt.other_id != second.pk or
            not first.is_active or not second.is_active or first.pk == second.pk or
            not proof_valid(attempt, 'owner', first) or not proof_valid(attempt, 'other', second)):
            raise ValueError('Account verification expired or changed. Start again and verify both accounts.')
        target = primary_account(first, second)
        if str(target.pk) != str(expected_target):
            raise ValueError('Account priority changed. Review the accounts again before merging.')
        source = second if target.pk == first.pk else first
        # Signed marketplace operations must finish first; no transaction can change hands mid-broadcast.
        if m.OrdinalTrade.objects.filter(Q(buyer__in=[source,target]) | Q(listing__seller__in=[source,target]),
                status__in=['prepared','broadcasting','broadcast']).exists():
            raise ValueError('Finish or resolve pending ordinal trades before merging accounts.')
        members = list(m.PublishingMembership.objects.filter(user__in=[source,target]))
        expiry = max((item.expires_at_block for item in members), default=None)
        if len(members) == 2:
            from .membership import chain_height
            height = chain_height()
            if height is None:
                raise ValueError('Combining paid time needs a fresh Bitcoin block check. Try again shortly.')
            remaining = sum(max(0, item.expires_at_block-height) for item in members)
            if remaining:
                expiry = height+remaining
        if expiry is not None:
            m.PublishingMembership.objects.update_or_create(user=target, defaults={'expires_at_block':expiry})
            m.PublishingMembership.objects.filter(user=source).delete()
        passes = list(m.ComplimentaryAccess.objects.filter(user__in=[source,target]))
        if passes:
            now = timezone.now()
            from datetime import timedelta
            remaining = sum((max(timedelta(0), p.expires_at-now) for p in passes if p.expires_at), timedelta(0))
            lifetime = any(p.lifetime for p in passes)
            dates = [p.expires_at for p in passes if p.expires_at]
            expires = None if lifetime else (now+remaining if remaining else max(dates, default=None))
            m.ComplimentaryAccess.objects.update_or_create(user=target, defaults={'lifetime':lifetime,'expires_at':expires})
            m.ComplimentaryAccess.objects.filter(user=source).delete()
        target_profile, _ = m.AuthorProfile.objects.get_or_create(user=target, defaults={'pen_name':target.username})
        source_profile = m.AuthorProfile.objects.filter(user=source).first()
        audit = {'source_username':source.username,'target_username':target.username,
                 'source_profile': {'pen_name':source_profile.pen_name,'bio':source_profile.bio} if source_profile else None,
                 'paid_expiry':expiry}
        if source_profile:
            # Keep the original profile row and URL as a redirect, preserving its biography for audit.
            m.Publication.objects.filter(author=source_profile).update(author=target_profile)
            for follow in m.Follow.objects.filter(author=source_profile):
                if m.Follow.objects.filter(user=follow.user, author=target_profile).exists(): follow.delete()
                else:
                    follow.author=target_profile
                    follow.save(update_fields=['author'])
            if not target_profile.bio and source_profile.bio:
                target_profile.bio=source_profile.bio
                target_profile.save(update_fields=['bio'])
        for model, field in [(m.Project,'owner'),(m.WalletIdentity,'user'),(m.Invitation,'created_by'),
                             (m.OrdinalListing,'seller'),(m.OrdinalTrade,'buyer')]:
            model.objects.filter(**{field:source}).update(**{field:target})
        # Stripe's original checkout identity must stay verifiable after ownership moves.
        m.PaymentOrder.objects.filter(user=source, billing_user_id__isnull=True).update(billing_user_id=F('user_id'))
        m.PaymentOrder.objects.filter(user=source).update(user=target)
        for model, keys in [(m.Upvote,['publication_id']),(m.Bookmark,['publication_id']),
                            (m.Follow,['author_id']),(m.Achievement,['code'])]:
            move_unique(model,source,target,keys)
        move_unique(m.PublicationReport,source,target,['publication_id'],field='reporter',retain_duplicates=True)
        move_unique(m.InviteRedemption,source,target,['invitation_id'],retain_duplicates=True)
        m.Follow.objects.filter(user=target,author=target_profile).delete()
        m.Upvote.objects.filter(user=target,publication__author=target_profile).delete()
        for model in [m.AccessGrant,m.ProfileUnlock]:
            item=model.objects.filter(user=source).first()
            existing=model.objects.filter(user=target).first()
            if item and not existing:
                if model == m.AccessGrant:
                    from django.conf import settings
                    item.max_projects=max(10,item.max_projects)
                    item.max_words_per_revision=max(settings.OBSERVATORY_MAX_WORDS,item.max_words_per_revision)
                item.user=target; item.save()
            elif item and model == m.AccessGrant:
                existing.max_projects=max(existing.max_projects,item.max_projects)
                existing.max_words_per_revision=max(existing.max_words_per_revision,item.max_words_per_revision)
                existing.save(update_fields=['max_projects','max_words_per_revision'])
        target.groups.add(*source.groups.all())
        target.user_permissions.add(*source.user_permissions.all())
        m.AccountMerge.objects.filter(target=source).update(target=target)
        m.AccountMerge.objects.create(source=source,target=target,details=audit)
        source.is_active=False
        source.save(update_fields=['is_active'])
        m.WalletChallenge.objects.filter(user__in=[source,target],consumed_at__isnull=True).update(consumed_at=timezone.now())
        m.MergeAttempt.objects.filter(Q(owner__in=[source,target]) | Q(other__in=[source,target]),
            consumed_at__isnull=True).update(consumed_at=timezone.now())
        return target
