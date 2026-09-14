import json
from uuid import UUID
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods
from .access import require_access, word_limit
from .engine import analyze, fingerprint
from .forms import NoteForm, ProjectForm, RevisionForm
from .models import Project, Revision
from .storage import budget
from .achievements import progress


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
@budget
def library(request):
    form = ProjectForm(request.POST or None)
    if request.method == 'POST':
        with transaction.atomic():
            # Serializes project quota checks for the same owner on PostgreSQL.
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            grant = require_access(request.user)
            if grant.max_projects is not None and request.user.novel_projects.count() >= grant.max_projects:
                form.add_error(None, 'Your pilot project allowance is full.')
            elif form.is_valid():
                project = form.save(commit=False)
                project.owner = request.user
                project.save()
                return redirect('project', project_id=project.id)
    return render(request, 'studio/library.html', {'projects': request.user.novel_projects.all(), 'form': form, 'journey':progress(request.user)})


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
@budget
def project(request, project_id):
    project = get_object_or_404(Project, pk=project_id, owner=request.user)
    form = RevisionForm()
    if request.method == 'POST':
        grant = require_access(request.user)
        form = RevisionForm(request.POST, request.FILES, max_words=word_limit(grant))
        if form.is_valid():
            data = form.cleaned_data
            report = analyze(data['manuscript'], data['profile'])
            revision = Revision.objects.create(project=project, label=data['label'], manuscript=data['manuscript'],
                profile=data['profile'], fingerprint=fingerprint(data['manuscript'], data['profile']),
                word_count=report['word_count'], engine_version=report['engine_version'], analysis=report)
            messages.success(request, 'Revision and analysis saved.')
            return redirect('revision', revision_id=revision.id)
    return render(request, 'studio/project.html', {'project': project, 'form': form, 'revisions': project.revisions.all()})


def owned_revision(request, revision_id):
    return get_object_or_404(Revision.objects.select_related('project'), pk=revision_id, project__owner=request.user)


@login_required
@never_cache
@require_http_methods(['GET'])
def revision(request, revision_id):
    revision = owned_revision(request, revision_id)
    report = revision.analysis
    signals = list(report['scores'])
    signal = request.GET.get('signal', 'Hope')
    if signal not in signals:
        signal = signals[0]
    baseline = None
    if request.GET.get('compare'):
        # Limit comparison to this owner's same project, even for guessed IDs.
        try:
            baseline_id = UUID(request.GET['compare'])
        except ValueError:
            raise Http404('Revision not found.')
        baseline = get_object_or_404(Revision, pk=baseline_id, project=revision.project)
    rows = [{'signal': k, 'score': v, 'percent': round(v*100),
             'delta': round(v-baseline.analysis['scores'][k], 3) if baseline and k in baseline.analysis['scores'] else None}
            for k, v in report['scores'].items()]
    evidence = [{'position': u['position'], 'chapter': u['chapter'],
                 'score': u['analysis']['scores'][signal], 'text': u['text'],
                 'evidence': u['analysis']['evidence'][signal]}
                for u in report['units'] if u['analysis']['evidence'][signal]]
    chapter_rows = [{'label': c['label'], 'score': c['scores'][signal], 'percent': round(c['scores'][signal]*100)}
                    for c in report['chapters']]
    return render(request, 'studio/revision.html', {
        'revision': revision, 'rows': rows, 'signals': signals, 'signal': signal, 'evidence': evidence,
        'chapter_rows': chapter_rows, 'baseline': baseline,
        'baselines': revision.project.revisions.exclude(pk=revision.pk), 'note_form': NoteForm(),
    })


@login_required
@require_POST
@budget
def add_note(request, revision_id):
    revision = owned_revision(request, revision_id)
    require_access(request.user)
    form = NoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.revision = revision
        note.save()
        messages.success(request, 'Revision decision saved.')
    else:
        messages.error(request, 'Write a decision of 1–4,000 characters.')
    return redirect('revision', revision_id=revision.id)


@login_required
@never_cache
@require_http_methods(['GET'])
def export_revision(request, revision_id):
    revision = owned_revision(request, revision_id)
    response = HttpResponse(json.dumps({
        'schema_version': 1, 'project': revision.project.title, 'revision': revision.label,
        'created_at': revision.created_at.isoformat(), 'manuscript': revision.manuscript,
        'fingerprint': revision.fingerprint, 'analysis': revision.analysis,
        'notes': list(revision.notes.values('text')),
        'clue_annotations': list(revision.clue_annotations.values('clue','passage_id','status','note')),
        'semantic_readings': list(revision.semantic_readings.values('passage_id','model','result')),
    }, ensure_ascii=False, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="observatory-{revision.id}.json"'
    return response
