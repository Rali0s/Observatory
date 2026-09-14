from django.db import transaction
from django.db.models.signals import post_save
from .models import Project, Revision, DraftChapter, StoryWorkspace, RevisionNote, Publication, Upvote, OrdinalEdition


def observe(sender, instance, raw=False, **kwargs):
    if raw:return
    if sender==Project: user_id=instance.owner_id
    elif sender in (Revision,DraftChapter,StoryWorkspace):user_id=instance.project.owner_id
    elif sender==RevisionNote:user_id=instance.revision.project.owner_id
    elif sender==Publication:user_id=instance.author.user_id
    else:user_id=instance.publication.author.user_id
    def award():
        from django.contrib.auth import get_user_model
        from .achievements import progress
        user=get_user_model().objects.filter(pk=user_id).first()
        if user:progress(user)
    transaction.on_commit(award)

for model in (Project,Revision,DraftChapter,StoryWorkspace,RevisionNote,Publication,Upvote,OrdinalEdition):
    post_save.connect(observe,sender=model,dispatch_uid='observatory-achievements-'+model.__name__)
