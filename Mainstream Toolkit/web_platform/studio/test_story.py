import io
import json
import zipfile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Project, Revision, StoryWorkspace, StoryEntry, DraftChapter, ChainTip, PaymentOrder, ReceivingAddress, PublishingMembership
from .engine import analyze, fingerprint
from .storage import usage,save_content
from .story_board import validate_board
from .direct_payments import create_order,verify_transaction


class StoryTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('writer')
        self.other=get_user_model().objects.create_user('other')
        self.project=Project.objects.create(owner=self.user,title='Garden')
        self.foreign=Project.objects.create(owner=self.other,title='Private')
        self.client.force_login(self.user);cache.clear()
        report=analyze('Ada felt hope beside the silver key.\n\nAda chose to give the silver key to Ben.','general')
        self.revision=Revision.objects.create(project=self.project,label='First',manuscript='Ada felt hope.',profile='general',fingerprint='a'*64,analysis=report,word_count=report['word_count'],engine_version=report['engine_version'])

    def test_story_routes_and_owner_isolation(self):
        for name in ['story','chapters','edition','export-project','story-board']:
            self.assertEqual(self.client.get(reverse(name,args=[self.project.pk])).status_code,200)
            self.assertEqual(self.client.get(reverse(name,args=[self.foreign.pk])).status_code,404)
        for name in ['story-aids','timeline-csv']:
            self.assertEqual(self.client.get(reverse(name,args=[self.revision.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('storage')).status_code,200)

    def test_board_branches_loop_and_conflict(self):
        data={'version':1,'name':'Plot','nodes':[{'id':'a','pos':[10,20],'title':'Start'},{'id':'b','pos':[350,20],'title':'End'}],
            'edges':[{'id':'e','source':'a','target':'b','kind':'Payoff','condition':'Key found','effect':'Door opens'},{'id':'loop','source':'a','target':'a','kind':'Branch'}]}
        url=reverse('story-board',args=[self.project.pk])
        self.assertEqual(self.client.post(url,json.dumps({'board':data,'revision':0}),content_type='application/json').status_code,200)
        self.assertEqual(self.client.post(url,json.dumps({'board':data,'revision':0}),content_type='application/json').status_code,400)
        self.assertEqual(StoryWorkspace.objects.get(project=self.project).board['edges'][0]['effect'],'Door opens')
        data['edges'][0]['target']='missing'
        with self.assertRaises(ValueError):validate_board(data)

    def test_quota_rollback_and_owner_scoping(self):
        before=usage(self.user)
        with override_settings(STORAGE_QUOTA_BYTES=before+10):
            with self.assertRaises(ValueError): save_content(self.user,lambda:StoryEntry.objects.create(project=self.project,title='X'*100,kind='task'))
        self.assertFalse(StoryEntry.objects.exists())
        DraftChapter.objects.create(project=self.foreign,title='secret',markdown='x'*10000)
        self.assertEqual(usage(self.user),before)
        with override_settings(STORAGE_QUOTA_BYTES=1):
            response=self.client.post(reverse('project',args=[self.project.pk]),{'label':'Too large','profile':'general','manuscript':'Ada feels hope.'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.project.revisions.count(),1)

    def test_chapter_save_preview_snapshot_and_conflict(self):
        url=reverse('chapters',args=[self.project.pk]);data={'title':'Opening','position':1,'markdown':'# Hello\n\nAda chose hope. <script>alert(1)</script>','version':0}
        self.assertEqual(self.client.post(url,data).status_code,302)
        chapter=DraftChapter.objects.get(project=self.project)
        edit=reverse('chapter-edit',args=[self.project.pk,chapter.pk])
        response=self.client.get(edit)
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertContains(response,'<h1>Hello</h1>')
        data['title']='Stale'
        self.assertContains(self.client.post(edit,data),'changed in another tab')
        chapter.refresh_from_db();self.assertEqual(chapter.title,'Opening')
        self.assertEqual(self.client.post(reverse('chapter-snapshot',args=[self.project.pk]),{'profile':'general'}).status_code,302)
        self.assertEqual(self.project.revisions.count(),2)

    def test_clue_annotation_and_vocabulary(self):
        url=reverse('story-aids',args=[self.revision.pk])
        self.client.post(url,{'action':'vocabulary','roster':'{"Ada":["Ada"],"Ben":["Ben"]}','clues':'{"Key":["silver key"]}'})
        uid=self.revision.analysis['units'][0]['id']
        self.client.post(url,{'action':'clue','clue':'Key','passage':uid,'status':'Planted','note':'First promise'})
        self.assertEqual(self.revision.clue_annotations.count(),1)
        self.assertContains(self.client.get(url),'First promise')
        self.assertContains(self.client.get(url),'Ada & Ben')
        self.client.post(url,{'action':'clue','clue':'Key','passage':'foreign','status':'Paid off'})
        self.assertEqual(self.revision.clue_annotations.count(),1)

    def test_export_formats_and_explicit_cleanup(self):
        DraftChapter.objects.create(project=self.project,title='Opening',markdown='Ada chose hope.\n\nA quiet ending.')
        data={'title':'Garden','author':'Writer','title_page':'# {title}','copyright_page':'Copyright {copyright_year}','trim_size':'6 x 9 in','font_family':'Times','font_size':11,'line_spacing':1.35}
        for kind,signature in [('pdf',b'%PDF'),('epub',b'PK'),('md',b'# Opening')]:
            response=self.client.post(reverse('edition',args=[self.project.pk]),{**data,'format':kind})
            self.assertEqual(response.status_code,200);self.assertTrue(response.content.startswith(signature),response.content[:100])
            if kind=='epub':
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:self.assertIn('mimetype',z.namelist())
        url=reverse('remove-content',args=['revision',self.revision.pk])
        self.client.post(url);self.assertTrue(Revision.objects.filter(pk=self.revision.pk).exists())
        self.client.post(url,{'confirm':'yes'});self.assertFalse(Revision.objects.filter(pk=self.revision.pk).exists())

    def test_ai_disabled_does_not_send(self):
        with patch('studio.publishing.module') as module:
            self.client.post(reverse('story-aids',args=[self.revision.pk]),{'action':'semantic','consent':'yes','passage':self.revision.analysis['units'][0]['id']})
            module.assert_not_called()

    def test_import_saved_revision_and_chapter_notes(self):
        url=reverse('revision-to-chapters',args=[self.revision.pk])
        self.client.post(url);self.client.post(url)
        self.assertEqual(self.project.draft_chapters.count(),1)
        chapter=self.project.draft_chapters.get()
        self.client.post(reverse('chapter-note',args=[chapter.pk]),{'text':'Give Ada a concrete goal.','mode':'manual'})
        self.assertEqual(self.project.story_entries.get().reference,str(chapter.pk))
        response=self.client.get(reverse('chapter-edit',args=[self.project.pk,chapter.pk]))
        self.assertContains(response,'Give Ada a concrete goal.')
        self.assertContains(response,'Summary candidates')

    @override_settings(SEMANTIC_ENABLED=True,SEMANTIC_MODEL='configured-test-model')
    @patch('studio.publishing.module')
    def test_semantic_consent_and_retention(self,module):
        url=reverse('story-aids',args=[self.revision.pk]);uid=self.revision.analysis['units'][0]['id']
        self.client.post(url,{'action':'semantic','passage':uid})
        module.assert_not_called()
        module.return_value.semantic_pass.return_value={'scores':{'Hope':0.5},'evidence':{}}
        original=self.revision.analysis
        self.client.post(url,{'action':'semantic','passage':uid,'consent':'yes'})
        self.assertEqual(self.revision.semantic_readings.count(),1)
        self.revision.refresh_from_db();self.assertEqual(self.revision.analysis,original)

    def test_art_validation_owner_and_export(self):
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        stream=io.BytesIO();Image.new('RGB',(2,2),'green').save(stream,format='PNG')
        self.client.post(reverse('chapters',args=[self.project.pk]),{'title':'Illustrated','position':1,'markdown':'Ada chose hope.','version':0,
            'image':SimpleUploadedFile('cover.png',stream.getvalue(),content_type='image/png'),'art_alt':'A green square'})
        chapter=self.project.draft_chapters.get()
        self.assertEqual(bytes(chapter.art),stream.getvalue())
        self.assertEqual(self.client.get(reverse('chapter-art',args=[chapter.pk])).status_code,200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('chapter-art',args=[chapter.pk])).status_code,404)
        self.client.force_login(self.user)
        response=self.client.post(reverse('chapters',args=[self.project.pk]),{'title':'Invalid','position':2,'markdown':'Ada chose hope.','version':0,
            'image':SimpleUploadedFile('bad.png',b'<script>bad</script>',content_type='image/png')})
        self.assertContains(response,'Choose a valid PNG')
        self.assertEqual(self.project.draft_chapters.count(),1)


class DirectPaymentTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('buyer');self.client.force_login(self.user)
        ChainTip.objects.create(pk=1,height=10005,block_hash='a'*64,observed_at=timezone.now())
        self.address=ReceivingAddress.objects.create(address='bc1q-test-address')
        cache.clear()

    @override_settings(DIRECT_BITCOIN_ENABLED=True)
    @patch('studio.direct_payments.spot_price',return_value=Decimal('60000'))
    def test_quote_address_reservation_and_redemption(self,rate):
        PublishingMembership.objects.create(user=self.user,expires_at_block=1000)
        order=create_order(self.user)
        self.assertEqual(order.amount_sats,75000);self.assertEqual(order.amount_usd,Decimal('45'))
        self.assertEqual(create_order(self.user).pk,order.pk)
        self.assertEqual(PaymentOrder.objects.count(),1)
        self.assertEqual(self.client.get(reverse('bitcoin-order',args=[order.pk])).status_code,200)

    def order(self):
        return PaymentOrder.objects.create(user=self.user,provider='direct',amount_usd=18,amount_sats=30000,address=self.address.address,quote_expires=timezone.now()+timedelta(minutes=15))

    def tx(self,order,value=30000,confirmed=True):
        return {'txid':'b'*64,'vout':[{'scriptpubkey_address':order.address,'value':value}],
            'status':{'confirmed':confirmed,'block_height':9999,'block_hash':'c'*64,'block_time':int(timezone.now().timestamp())}}

    @patch('studio.direct_payments.urlopen')
    def test_confirmations_amount_recipient_and_idempotency(self,network):
        network.return_value.__enter__.return_value.read.return_value=b'c'*64
        order=self.order();tx=self.tx(order)
        self.assertEqual(verify_transaction(order,self.tx(order,100)),'Underpaid')
        self.assertEqual(verify_transaction(order,self.tx(order,confirmed=False)),'Confirming')
        self.assertFalse(PublishingMembership.objects.exists())
        bad=self.tx(order);bad['vout'][0]['scriptpubkey_address']='elsewhere'
        self.assertEqual(verify_transaction(order,bad),'Awaiting payment')
        tx['status']['block_height']=10001
        self.assertEqual(verify_transaction(order,tx),'Confirming')
        tx['status']['block_height']=9999
        self.assertEqual(verify_transaction(order,tx),'Settled')
        self.assertEqual(verify_transaction(order,tx),'Settled')
        self.assertEqual(PublishingMembership.objects.get(user=self.user).expires_at_block,14320)

    @patch('studio.direct_payments.urlopen')
    def test_late_payment_and_reorg_cannot_activate(self,network):
        order=self.order();PaymentOrder.objects.filter(pk=order.pk).update(quote_expires=timezone.now()-timedelta(hours=1));order.refresh_from_db()
        self.assertEqual(verify_transaction(order,self.tx(order)),'Late payment review')
        self.assertFalse(PublishingMembership.objects.exists())
        order=self.order();network.return_value.__enter__.return_value.read.return_value=b'd'*64
        with self.assertRaises(ValueError):verify_transaction(order,self.tx(order))
        self.assertFalse(PublishingMembership.objects.exists())

    def test_wallet_connection_page_works_without_payment_setup(self):
        response=self.client.get(reverse('wallet'))
        self.assertContains(response,'Connect Xverse')
        self.assertContains(response,'receiving wallet to be configured')
        self.assertEqual(PaymentOrder.objects.count(),0)

    def test_disabled_and_foreign_order(self):
        with self.assertRaises(ValueError):create_order(self.user)
        order=self.order();other=get_user_model().objects.create_user('outsider');self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('bitcoin-order',args=[order.pk])).status_code,404)
