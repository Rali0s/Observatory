from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from .models import AuthorProfile, Publication, Tag, Follow, Bookmark
from .forms import PublishForm
from .taxonomy import parse_tags, apply_tags


class TaxonomyTests(TestCase):
    def setUp(self):
        self.writer=get_user_model().objects.create_user('writer')
        self.reader=get_user_model().objects.create_user('reader')
        self.author=AuthorProfile.objects.create(user=self.writer,pen_name='Writer')
        self.poem=Publication.objects.create(author=self.author,title='Garden Lines',excerpt='Leaves fall.',body='A leaf.',kind='poetry',channel='poetry')
        self.mystery=Publication.objects.create(author=self.author,title='Hidden Key',excerpt='A door.',body='A key.',channel='mystery')
        self.hidden=Publication.objects.create(author=self.author,title='Withdrawn',excerpt='Hidden.',body='Hidden.',channel='romance',is_visible=False)
        apply_tags(self.poem,'#Nature #quiet');apply_tags(self.mystery,'#quiet #whodunit');apply_tags(self.hidden,'#secret-only')

    def test_tag_validation_and_normalization(self):
        self.assertEqual(parse_tags('#SlowBurn, slowburn #found-family'),['slowburn','found-family'])
        self.assertEqual(parse_tags('#poésie'),['poésie'])
        for invalid in ['<script>','a'*33,' '.join('t'+str(i) for i in range(9))]:
            with self.assertRaises(ValidationError):parse_tags(invalid)

    def test_channel_tag_intersection_and_visible_facets(self):
        response=self.client.get(reverse('feed'),{'channel':'poetry','tag':'quiet'})
        self.assertContains(response,'Garden Lines');self.assertNotContains(response,'Hidden Key')
        self.assertNotContains(response,'secret-only');self.assertNotContains(self.client.get(reverse('feed')),'Withdrawn')
        self.assertContains(self.client.get(reverse('feed'),{'channel':'erotica'}),'No matching readings yet.')
        self.assertEqual(self.client.get(reverse('feed'),{'channel':'unknown'}).status_code,404)

    def test_following_saved_and_pagination_keep_filters(self):
        self.client.force_login(self.reader)
        Follow.objects.create(user=self.reader,author=self.author)
        Bookmark.objects.create(user=self.reader,publication=self.poem)
        for tab in ['following','saved']:
            self.assertContains(self.client.get(reverse('feed'),{'tab':tab,'channel':'poetry','tag':'quiet'}),'Garden Lines')
        for i in range(13):
            p=Publication.objects.create(author=self.author,title=f'Poem {i}',excerpt='Leaf',body='Leaf',channel='poetry')
            apply_tags(p,'quiet')
        response=self.client.get(reverse('feed'),{'channel':'poetry','tag':'quiet'})
        self.assertContains(response,'channel=poetry&amp;tag=quiet&amp;page=2')

    def test_owner_can_relabel_without_membership_and_without_republishing(self):
        url=reverse('categorize',args=[self.poem.pk])
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(url,{'channel':'fiction','hashtags':'oops'}).status_code,404)
        self.client.force_login(self.writer)
        stamp=self.poem.published_at
        self.assertEqual(self.client.post(url,{'channel':'memoir','hashtags':'#memory'}).status_code,302)
        self.poem.refresh_from_db()
        self.assertEqual(self.poem.channel,'memoir');self.assertEqual(self.poem.body,'A leaf.')
        self.assertEqual(self.poem.published_at,stamp)
        self.assertEqual(list(self.poem.tags.values_list('name',flat=True)),['memory'])
        self.assertEqual(self.client.post(url,{'channel':'memoir','hashtags':''}).status_code,302)
        self.assertFalse(self.poem.tags.exists())

    def test_publish_form_has_explicit_classification(self):
        data={'title':'Title','kind':'story','channel':'non-fiction','hashtags':'#History #history','excerpt':'A fact.','body':'A fact.','rights_confirmed':True}
        form=PublishForm(data,user=self.writer)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data['hashtags'],'#history')
        form=PublishForm({**data,'channel':'not-a-channel'},user=self.writer)
        self.assertFalse(form.is_valid())
