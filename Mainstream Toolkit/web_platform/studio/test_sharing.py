from urllib.parse import parse_qs, urlsplit
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import AuthorProfile, Publication
from .templatetags.sharing import social_share

@override_settings(PUBLIC_BASE_URL='https://observate.up.railway.app')
class SharingTests(TestCase):
    def setUp(self):
        author = AuthorProfile.objects.create(user=get_user_model().objects.create_user('writer'), pen_name='Writer')
        self.post = Publication.objects.create(author=author, title='A & B "<test>"', excerpt='A short introduction.', body='The entire story stays on the reading page.', kind='story')

    def test_social_links_are_canonical_encoded_and_public_only(self):
        data = social_share({}, self.post)
        url = 'https://observate.up.railway.app'+reverse('read',args=[self.post.pk])
        self.assertEqual(data['share_url'],url)
        for platform,label,destination in data['share_links']:
            query = parse_qs(urlsplit(destination).query)
            self.assertEqual(query.get('url',query.get('u')), [url])
            self.assertNotIn(self.post.body,destination)
        self.post.is_visible=False
        self.assertEqual(social_share({},self.post),{})
        self.post.save()
        self.assertEqual(self.client.get(reverse('read',args=[self.post.pk])).status_code,404)

    def test_feed_and_read_have_accessible_icons_and_escaped_metadata(self):
        for path in [reverse('feed'),reverse('read',args=[self.post.pk])]:
            response=self.client.get(path)
            for name in ['X','Facebook','Blogger','LinkedIn']:
                self.assertContains(response,f'aria-label="Share on {name}"')
            self.assertNotContains(response,'"<test>"')
        response=self.client.get(reverse('read',args=[self.post.pk]))
        self.assertContains(response,'property="og:title"')
