from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from .achievements import progress
from .models import Project, Revision, DraftChapter, StoryWorkspace, Publication, AuthorProfile, Achievement, ProfileUnlock

class AchievementTests(TestCase):
    def setUp(self):
        self.writer=get_user_model().objects.create_user('journey-writer')
        self.other=get_user_model().objects.create_user('journey-other')
        self.author=AuthorProfile.objects.create(user=self.writer,pen_name='Quiet Author')
        self.client.force_login(self.writer)

    def revision(self,project,words):
        return Revision.objects.create(project=project,label='Snapshot',manuscript='word '*words,word_count=words,profile='general',fingerprint='a'*64,engine_version='1',analysis={})

    def test_initial_and_all_five_stages_free(self):
        self.assertEqual(progress(self.writer)['level'],0)
        project=Project.objects.create(owner=self.writer,title='One')
        self.assertEqual(progress(self.writer)['level'],1)
        DraftChapter.objects.create(project=project,title='Chapter',markdown='word '*500)
        self.assertEqual(progress(self.writer)['level'],2)
        self.revision(project,500)
        self.assertEqual(progress(self.writer)['level'],3)
        StoryWorkspace.objects.create(project=project,board={'nodes':[{'id':str(i)} for i in range(3)]})
        self.assertEqual(progress(self.writer)['level'],4)
        chapter=project.draft_chapters.first();chapter.markdown='word '*3000;chapter.save()
        self.assertEqual(progress(self.writer)['level'],5)
        self.assertFalse(Publication.objects.exists())
        self.assertContains(self.client.get(reverse('library')),'The illuminated Observatory')

    def test_snapshot_words_not_duplicated_and_ownership(self):
        project=Project.objects.create(owner=self.writer,title='One')
        self.revision(project,400);self.revision(project,400)
        other=Project.objects.create(owner=self.other,title='Private other')
        self.revision(other,10000)
        cards={c['code']:c for c in progress(self.writer)['cards']}
        self.assertEqual(cards['pages']['current'],400)
        self.assertFalse(cards['pages']['unlocked'])
        DraftChapter.objects.create(project=project,title='Current chapter',markdown='word '*200)
        cards={c['code']:c for c in progress(self.writer)['cards']}
        self.assertEqual(cards['pages']['current'],200)

    def test_unlocks_persist_and_are_idempotent(self):
        project=Project.objects.create(owner=self.writer,title='One')
        progress(self.writer);progress(self.writer)
        self.assertEqual(Achievement.objects.filter(user=self.writer,code='begin').count(),1)
        project.delete()
        self.assertEqual(progress(self.writer)['level'],1)

    def test_profile_opt_in_and_forged_unlock_rejected(self):
        url=reverse('achievements')
        Project.objects.create(owner=self.writer,title='Never expose this title')
        response=self.client.post(url,{'badge':'bitcoin','scene':5,'show_scene':'on'})
        self.assertEqual(response.status_code,200);self.assertFalse(ProfileUnlock.objects.exists())
        public=reverse('author',args=[self.author.pk])
        self.assertNotContains(self.client.get(public),'Seed keeper')
        self.assertEqual(self.client.post(url,{'badge':'begin','scene':1,'show_scene':'on'}).status_code,302)
        self.client.logout()
        response=self.client.get(public)
        self.assertContains(response,'Seed keeper');self.assertContains(response,'First light')
        self.assertNotContains(response,'Never expose this title')
        self.assertNotContains(response,'YOUR OBSERVATORY')
        self.assertNotContains(response,'Next:')
        self.assertEqual(self.client.get(url).status_code,302)

    def test_csrf_and_post_commit_award(self):
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.writer)
        self.assertEqual(strict.post(reverse('achievements'),{'badge':'','scene':0}).status_code,403)
        with self.captureOnCommitCallbacks(execute=True):
            Project.objects.create(owner=self.writer,title='Saved')
        self.assertTrue(Achievement.objects.filter(user=self.writer,code='begin').exists())

    def test_post_unlocks_and_hidden_post_does_not_grant(self):
        Publication.objects.create(author=self.author,title='Hidden',body='text',excerpt='text',is_visible=False)
        self.assertEqual(progress(self.writer)['level'],0)
        with self.captureOnCommitCallbacks(execute=True):
            Publication.objects.create(author=self.author,title='Released',body='text',excerpt='text')
        self.assertTrue(Achievement.objects.filter(user=self.writer,code='published').exists())
        self.assertTrue(Achievement.objects.filter(user=self.writer,code='voice').exists())
