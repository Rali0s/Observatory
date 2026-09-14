import hashlib
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from .models import AuthorProfile, Publication, OrdinalSettings, OrdinalEdition
from .ordinals import verify
from .ordinal_forms import ListingForm

@override_settings(ORDINAL_INDEX_URL='https://index.example')
class OrdinalTests(TestCase):
    def setUp(self):
        self.writer=get_user_model().objects.create_user('ordinal-writer')
        self.reader=get_user_model().objects.create_user('ordinal-reader')
        self.author=AuthorProfile.objects.create(user=self.writer,pen_name='Public Author')
        self.post=Publication.objects.create(author=self.author,title='Frozen story',body='Public <script>bad()</script>',excerpt='A story')
        self.url=reverse('ordinal',args=[self.post.pk])
        self.wallet=reverse('ordinal-wallet',args=[self.post.pk])
        self.data={'action':'prepare','edition_name':'First edition','description':'A quiet story','attributes':'{"language":"English"}','sat_mode':'regular','consent':'on'}
        self.flags,_=OrdinalSettings.objects.update_or_create(pk=1,defaults={'enabled':True,'special_sats_enabled':True})
        self.client.force_login(self.writer)

    def prepare(self):
        self.assertEqual(self.client.post(self.url,self.data).status_code,302)
        return OrdinalEdition.objects.get(publication=self.post)

    def test_switch_owner_csrf_and_immutable_snapshot(self):
        self.flags.enabled=False;self.flags.save()
        self.assertEqual(self.client.post(self.url,self.data).status_code,403)
        self.flags.enabled=True;self.flags.save()
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(self.url,self.data).status_code,403)
        self.client.force_login(self.writer)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.writer)
        self.assertEqual(strict.post(self.url,self.data).status_code,403)
        edition=self.prepare()
        self.assertIn('&lt;script&gt;',edition.content)
        self.assertEqual(edition.content_hash,hashlib.sha256(edition.content.encode()).hexdigest())
        self.data['description']='Replacement'
        self.client.post(self.url,self.data)
        edition.refresh_from_db();self.assertEqual(edition.metadata['description'],'A quiet story')
        self.assertContains(self.client.get(self.url),'Frozen ordinal edition preview')

    def test_wallet_duplicate_attempt_and_switch(self):
        edition=self.prepare()
        self.assertEqual(self.client.get(self.wallet).status_code,405)
        response=self.client.post(self.wallet,{'action':'begin'})
        self.assertEqual(response.json()['content'],edition.content)
        self.assertEqual(self.client.post(self.wallet,{'action':'begin'}).status_code,409)
        self.client.post(self.wallet,{'action':'broadcast','txid':'b'*64})
        edition.refresh_from_db();self.assertEqual(edition.status,'awaiting');self.assertIsNone(edition.inscription_id)
        self.assertEqual(self.client.post(self.wallet,{'action':'cancel'}).status_code,409)
        self.flags.enabled=False;self.flags.save()
        self.assertEqual(self.client.post(self.wallet,{'action':'begin'}).status_code,403)

    def test_special_requires_exact_sat_and_no_wallet_path(self):
        self.data['sat_mode']='special'
        self.assertEqual(self.client.post(self.url,self.data).status_code,200)
        self.assertFalse(OrdinalEdition.objects.exists())
        self.data['requested_sat']='123'
        edition=self.prepare()
        self.assertEqual(edition.requested_sat,123)
        self.assertEqual(self.client.post(self.wallet,{'action':'begin'}).status_code,409)

    def test_private_pending_download_and_public_profile(self):
        edition=self.prepare()
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse('ordinal-download',args=[self.post.pk])).status_code,404)
        self.assertNotContains(self.client.get(self.url),'A quiet story')
        edition.status='minted';edition.inscription_id='a'*64+'i0';edition.save()
        self.client.logout()
        self.assertContains(self.client.get(self.url),'Bitcoin ordinal')
        self.assertContains(self.client.get(reverse('author',args=[self.author.pk]),{'tab':'ordinals'}),self.post.title)
        self.post.is_visible=False;self.post.save()
        self.assertEqual(self.client.get(self.url).status_code,404)

    @patch('studio.ordinals.chain_height',return_value=100)
    @patch('studio.ordinals.fetch')
    def test_verified_content_confirmations_sat_and_no_republishing(self,fetch,height):
        self.data.update(sat_mode='special',requested_sat='123')
        edition=self.prepare();iid='a'*64+'i0'
        edition.inscription_id=iid;edition.status='submitted';edition.save()
        responses={'/status':{'chain':'mainnet','height':100},'/inscription/'+iid:{'id':iid,'sat':123},
            '/content/'+iid:edition.content.encode(),'/tx/'+'a'*64:{'txid':'a'*64,'status':{'confirmed':True,'block_height':95,'block_hash':'b'*64}},
            '/block-height/95':('b'*64).encode(),'/sat/123':{'number':123,'rarity':'uncommon'}}
        fetch.side_effect=lambda path,**kwargs:responses[path]
        responses['/content/'+iid]=b'wrong'
        with self.assertRaises(ValueError):verify(edition)
        edition.refresh_from_db();self.assertEqual(edition.status,'submitted')
        responses['/content/'+iid]=edition.content.encode()
        responses['/inscription/'+iid]['sat']=124
        responses['/sat/124']={'number':124,'rarity':'common'}
        with self.assertRaises(ValueError):verify(edition)
        responses['/inscription/'+iid]['sat']=123
        self.post.is_visible=False;self.post.save()
        self.assertTrue(verify(edition))
        edition.refresh_from_db();first=edition.minted_at
        self.assertTrue(verify(edition));edition.refresh_from_db();self.assertEqual(edition.minted_at,first)
        self.post.refresh_from_db();self.assertFalse(self.post.is_visible)
        self.assertEqual(edition.sat_rarity,'uncommon')

    def test_listing_urls_are_gamma_only(self):
        for url in ['https://evil.example/x','javascript:alert(1)','https://gamma.io.evil.example/x','https://gamma.io:bad/x']:
            self.assertFalse(ListingForm({'marketplace_url':url}).is_valid())
        self.assertTrue(ListingForm({'marketplace_url':'https://gamma.io/ordinals/example'}).is_valid())

    def test_ordinal_publish_hub_only_lists_own_visible_posts(self):
        other_author=AuthorProfile.objects.create(user=self.reader,pen_name='Other Writer')
        Publication.objects.create(author=other_author,title='Other private selection',body='text',excerpt='text')
        Publication.objects.create(author=self.author,title='Withdrawn selection',body='text',excerpt='text',is_visible=False)
        response=self.client.get(reverse('ordinal-publish'))
        self.assertContains(response,self.post.title)
        self.assertNotContains(response,'Other private selection')
        self.assertNotContains(response,'Withdrawn selection')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('ordinal-publish')).status_code,302)
