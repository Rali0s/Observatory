from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from .models import AuthorProfile, Publication, Upvote, Tag


class VotingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.writer = get_user_model().objects.create_user('vote-writer')
        cls.reader = get_user_model().objects.create_user('vote-reader')
        cls.other = get_user_model().objects.create_user('vote-other')
        cls.author = AuthorProfile.objects.create(user=cls.writer, pen_name='Test Writer')
        cls.older = Publication.objects.create(author=cls.author, title='Older story', body='Story', excerpt='Old', channel='fiction')
        cls.newer = Publication.objects.create(author=cls.author, title='Newest story', body='Story', excerpt='New', channel='fiction')
        Publication.objects.filter(pk=cls.older.pk).update(published_at=timezone.now()-timedelta(days=1))

    def setUp(self):
        self.client.force_login(self.reader)
        self.url = reverse('vote', args=[self.older.pk])

    def test_idempotent_votes_removal_and_user_scoping(self):
        for _ in range(2): self.client.post(self.url, {'action':'upvote'})
        self.assertEqual(Upvote.objects.count(), 1)
        Upvote.objects.create(user=self.other, publication=self.older)
        for _ in range(2): self.client.post(self.url, {'action':'remove'})
        self.assertEqual(list(Upvote.objects.values_list('user_id', flat=True)), [self.other.pk])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Upvote.objects.create(user=self.other, publication=self.older)

    def test_post_login_csrf_visibility_and_no_self_vote(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.post(self.url, {'action':'invalid'}).status_code, 400)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.reader)
        self.assertEqual(strict.post(self.url, {'action':'upvote'}).status_code, 403)
        self.client.force_login(self.writer)
        self.client.post(self.url, {'action':'upvote'})
        self.assertFalse(Upvote.objects.exists())
        self.client.force_login(self.reader)
        Publication.objects.filter(pk=self.older.pk).update(is_visible=False)
        self.assertEqual(self.client.post(self.url, {'action':'upvote'}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {'action':'upvote'}).status_code, 302)
        self.assertFalse(Upvote.objects.exists())

    def test_ranking_new_posts_and_filtered_vote_counts(self):
        Upvote.objects.create(user=self.reader, publication=self.older)
        for name in ('quiet', 'forest'):
            self.older.tags.add(Tag.objects.create(name=name))
        response = self.client.get(reverse('feed'))
        self.assertEqual([p.pk for p in response.context['page']], [self.older.pk, self.newer.pk])
        self.assertEqual([p.pk for p in response.context['new_posts']], [self.newer.pk, self.older.pk])
        response = self.client.get(reverse('feed'), {'channel':'fiction','tag':'quiet'})
        self.assertEqual(response.context['page'][0].vote_count, 1)
        self.assertContains(response, 'Liked')
        response = self.client.get(reverse('feed'), {'tab':'latest'})
        self.assertEqual(response.context['page'][0].pk, self.newer.pk)
        self.client.post(self.url, {'action':'remove'})
        self.assertEqual(self.client.get(reverse('feed')).context['page'][0].pk, self.newer.pk)

    def test_safe_redirect_and_personalized_read_state(self):
        response = self.client.post(self.url, {'action':'upvote','next':'https://evil.example/'})
        self.assertRedirects(response, reverse('read', args=[self.older.pk]))
        response = self.client.get(reverse('read', args=[self.older.pk]))
        self.assertTrue(response.context['post'].has_upvoted)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(response.context['post'].vote_count, 1)
        response = self.client.post(self.url, {'action':'remove','next':'/?tab=latest'})
        self.assertRedirects(response, '/?tab=latest')
        self.client.logout()
        response = self.client.get(reverse('read', args=[self.older.pk]))
        self.assertFalse(response.context['post'].has_upvoted)
        self.assertContains(response, 'Sign in to like')
