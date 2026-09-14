"""Milestones use owned content; snapshots never multiply a manuscript's word count."""
import re
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Achievement, ProfileUnlock, Project, Revision, DraftChapter, StoryWorkspace, RevisionNote, Publication, Upvote, OrdinalEdition

STAGES = ['The quiet desk','First light','A living garden','Wings over the valley','A sky of stories','The illuminated Observatory']
BADGES = [
    {'code':'begin','title':'Seed keeper','description':'Create your first manuscript project.','target':1,'unit':'project','core':True,'icon':'seed'},
    {'code':'pages','title':'Page maker','description':'Save 500 words across your current manuscripts.','target':500,'unit':'words','core':True,'icon':'book'},
    {'code':'insight','title':'Pattern reader','description':'Save your first manuscript analysis.','target':1,'unit':'analysis','core':True,'icon':'lens'},
    {'code':'shape','title':'Story architect','description':'Place three scene cards on one board, or save three revision notes.','target':3,'unit':'cards or notes','core':True,'icon':'map'},
    {'code':'voice','title':'Observatory fellow','description':'Save 3,000 manuscript words or publish your first post.','target':3000,'unit':'words (or one post)','core':True,'icon':'dome'},
    {'code':'published','title':'First release','description':'Publish your first post in the Reading Room.','target':1,'unit':'post','core':False,'icon':'quill'},
    {'code':'shelf','title':'Growing shelf','description':'Publish three posts in the Reading Room.','target':3,'unit':'posts','core':False,'icon':'shelf'},
    {'code':'resonance','title':'Resonance','description':'Receive likes from ten different readers across your visible posts.','target':10,'unit':'readers','core':False,'icon':'star'},
    {'code':'bitcoin','title':'Written on Bitcoin','description':'Have an ordinal edition verified on Bitcoin.','target':1,'unit':'verified edition','core':False,'icon':'bitcoin'},
]

def metrics(user):
    projects=Project.objects.filter(owner=user)
    words=0; chapter_projects=set()
    for project_id, markdown in DraftChapter.objects.filter(project__owner=user).values_list('project_id','markdown').iterator():
        chapter_projects.add(project_id);words+=len(re.findall(r"\b\w+(?:['’-]\w+)*\b",markdown))
    seen=set(chapter_projects)
    for project_id,count in Revision.objects.filter(project__owner=user).order_by('project_id','-created_at','-pk').values_list('project_id','word_count').iterator():
        if project_id not in seen: words+=count;seen.add(project_id)
    scenes=max((len(board.get('nodes',[])) for board in StoryWorkspace.objects.filter(project__owner=user).values_list('board',flat=True) if isinstance(board,dict)),default=0)
    notes=RevisionNote.objects.filter(revision__project__owner=user).count()
    posts=Publication.objects.filter(author__user=user,is_visible=True).count()
    return {'begin':projects.count(),'pages':words,'insight':Revision.objects.filter(project__owner=user).count(),
        'shape':max(scenes,notes),'voice':max(words,3000 if posts else 0),'published':posts,'shelf':posts,
        'resonance':Upvote.objects.filter(publication__author__user=user,publication__is_visible=True).exclude(user=user).values('user_id').distinct().count(),
        'bitcoin':OrdinalEdition.objects.filter(publication__author__user=user,status='minted').count()}

def progress(user):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        counts=metrics(user)
        existing={a.code:a for a in Achievement.objects.filter(user=user)}
        for badge in BADGES:
            if badge['code'] not in existing and counts[badge['code']]>=badge['target']:
                existing[badge['code']],_=Achievement.objects.get_or_create(user=user,code=badge['code'])
        cards=[]
        for badge in BADGES:
            current=min(counts[badge['code']],badge['target'])
            earned=existing.get(badge['code'])
            cards.append({**badge,'unlocked':bool(earned),'date':earned.unlocked_at if earned else None,
                'current':current,'percent':100 if earned else int(100*current/badge['target']), 'icon_path':'achievements/'+badge['icon']+'.svg'})
        level=sum(c['unlocked'] for c in cards if c['core'])
        return {'level':level,'stage_name':STAGES[level],'cards':cards,'earned':sum(c['unlocked'] for c in cards),
            'next':next((c for c in cards if c['core'] and not c['unlocked']),None),
            'stages':[{'level':i,'name':name,'unlocked':i<=level} for i,name in enumerate(STAGES)]}

def public_unlock(user):
    pref=ProfileUnlock.objects.filter(user=user).first()
    if not pref:return None
    earned=set(Achievement.objects.filter(user=user).values_list('code',flat=True))
    level=sum(b['core'] for b in BADGES if b['code'] in earned)
    badge=next(({**b,'icon_path':'achievements/'+b['icon']+'.svg'} for b in BADGES if b['code']==pref.badge and b['code'] in earned),None)
    scene=min(pref.scene,level)
    return {'badge':badge,'show_scene':pref.show_scene,'level':scene,'stage_name':STAGES[scene]}
