"""Logical UTF-8 content allowance, not PostgreSQL disk size. Call under user lock."""
import json
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from .access import is_admin
from .models import Project, Revision, RevisionNote, Publication, StoryWorkspace, StoryEntry, DraftChapter, ClueAnnotation, SemanticReading, OrdinalEdition


def size(value):
    if isinstance(value, (bytes, memoryview)):
        return len(value)
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return len(value.encode('utf-8'))


def usage(user):
    groups = [
        (OrdinalEdition.objects.filter(publication__author__user=user), ['content','metadata']),
        (Project.objects.filter(owner=user), ['title']),
        (Revision.objects.filter(project__owner=user), ['label','manuscript','analysis']),
        (RevisionNote.objects.filter(revision__project__owner=user), ['text']),
        (Publication.objects.filter(author__user=user), ['title','excerpt','body']),
        (StoryWorkspace.objects.filter(project__owner=user), ['board','roster','clues']),
        (StoryEntry.objects.filter(project__owner=user), ['title','text','reference']),
        (DraftChapter.objects.filter(project__owner=user), ['title','section','markdown','art','art_alt']),
        (ClueAnnotation.objects.filter(revision__project__owner=user), ['clue','status','note']),
        (SemanticReading.objects.filter(revision__project__owner=user), ['result']),
    ]
    return sum(size(v) for qs, fields in groups for row in qs.values_list(*fields).iterator() for v in row) + sum(size(name) for name in Publication.objects.filter(author__user=user).values_list('tags__name',flat=True) if name)


def storage_state(user):
    used = usage(user)
    if is_admin(user):
        return {'used': used, 'limit': None, 'percent': 0, 'unlimited': True}
    limit = settings.STORAGE_QUOTA_BYTES
    return {'used': used, 'limit': limit, 'percent': min(100, round(100*used/limit, 1))}


def save_content(user, operation):
    """Serialize all content writes, roll back increases over the allowance."""
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        before = usage(user)
        result = operation()
        after = usage(user)
        if not is_admin(user) and after > settings.STORAGE_QUOTA_BYTES and after > before:
            raise ValueError('Your storage allowance is full. Export and remove an older draft or attachment before saving more.')
        return result


def budget(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method != 'POST': return view(request,*args,**kwargs)
        try:
            return save_content(request.user, lambda: view(request,*args,**kwargs))
        except ValueError as exc:
            # Discard success messages produced by a write that was rolled back.
            list(messages.get_messages(request))
            messages.error(request,str(exc))
            if view.__name__=='chapter_snapshot': return redirect('chapters',project_id=kwargs['project_id'])
            if view.__name__=='add_note': return redirect('revision',revision_id=kwargs['revision_id'])
            if view.__name__=='chapter_note':
                chapter=DraftChapter.objects.get(pk=kwargs['chapter_id'],project__owner=request.user)
                return redirect('chapter-edit',project_id=chapter.project_id,chapter_id=chapter.pk)
            if view.__name__=='revision_to_chapters': return redirect('revision',revision_id=kwargs['revision_id'])
            return redirect(request.path)
    return wrapped
