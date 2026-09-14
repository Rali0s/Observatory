from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.test import TestCase,override_settings
from django.urls import reverse
from django.utils import timezone
from . import models as m
from .ordinal_forms import EditionForm
from .mint_fees import estimate,wallet_fee_payload
from .rare_sats import boundaries,inventory,selection


@override_settings(ORDINAL_INDEX_URL='https://index.example',ORDINAL_PLATFORM_FEE_SATS=0)
class MintBuilderTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user('mint-author')
        self.other=get_user_model().objects.create_user('other')
        profile=m.AuthorProfile.objects.create(user=self.user,pen_name='A writer')
        self.post=m.Publication.objects.create(author=profile,title='A story',body='Story text',excerpt='An excerpt')
        m.OrdinalSettings.objects.update_or_create(pk=1,defaults={'enabled':True,'special_sats_enabled':True})
        self.client.force_login(self.user)
        self.url=reverse('ordinal',args=[self.post.pk]);self.fees=reverse('ordinal-fees',args=[self.post.pk])
        self.data={'action':'prepare','edition_name':'First edition','language':'English','sat_mode':'regular','consent':'on',
            'trait_name':['Cover','Series'],'trait_value':['Green','Quiet Hours']}

    def frozen(self):
        self.client.post(self.url,self.data)
        return m.OrdinalEdition.objects.get(publication=self.post)

    def test_guided_traits_regular_ignores_special_sat_and_no_json_field(self):
        response=self.client.get(self.url)
        self.assertContains(response,'Add a trait')
        self.assertNotContains(response,'name="attributes"')
        self.assertNotContains(response,'Exact sat number')
        self.assertContains(response,'id="special-sat-fields" hidden')
        self.data['requested_sat']='123'
        item=self.frozen()
        self.assertEqual(item.metadata['attributes'],{'language':'English','Cover':'Green','Series':'Quiet Hours'})
        self.assertIsNone(item.requested_sat)

    def test_traits_validate_duplicates_unmatched_values_and_limits(self):
        for change in [{'trait_name':['Language'],'trait_value':['French']}, {'trait_name':['A'],'trait_value':[]},
                       {'trait_name':['X']*18,'trait_value':['Y']*18}, {'trait_name':['A'],'trait_value':['x'*241]}]:
            self.client.post(self.url,{**self.data,**change})
            self.assertFalse(m.OrdinalEdition.objects.exists())

    @patch('studio.mint_fees.recommendations',return_value={'standard':'3','economy':'2','fast':'4'})
    def test_fee_breakdown_counts_utf8_and_requires_signed_current_quote(self,rates):
        item=self.frozen()
        quote=self.client.post(self.fees,{'speed':'standard'}).json()
        self.assertEqual(quote['content_bytes'],len(item.content.encode()))
        self.assertEqual(quote['subtotal_min'],quote['miner_min']+546)
        self.assertEqual(quote['platform_fee'],0)
        self.assertGreater(estimate('é'*100,3)['miner_min'],estimate('a'*100,3)['miner_min'])
        wallet=reverse('ordinal-wallet',args=[self.post.pk])
        self.assertEqual(self.client.post(wallet,{'action':'begin'}).status_code,400)
        self.assertEqual(self.client.post(wallet,{'action':'begin','quote':quote['quote']+'x'}).status_code,400)
        item.refresh_from_db();self.assertEqual(item.status,'prepared')
        payload=self.client.post(wallet,{'action':'begin','quote':quote['quote']}).json()
        self.assertEqual(payload['suggestedMinerFeeRate'],3)
        self.assertNotIn('appFee',payload)
        self.assertNotIn('appFeeAddress',payload)
        self.assertEqual(self.client.post(wallet,{'action':'begin','quote':quote['quote']}).status_code,409)

    def test_fee_changes_expiry_and_content_changes_require_review(self):
        item=self.frozen();quote=estimate(item.content,2,item)['quote']
        with override_settings(ORDINAL_PLATFORM_FEE_SATS=1000):
            with self.assertRaises(ValueError):wallet_fee_payload(item,quote)
            new=estimate(item.content,2,item)
            payload=wallet_fee_payload(item,new['quote'])
            self.assertEqual(payload['appFee'],1000)
            self.assertEqual(payload['appFeeAddress'],'bc1qzs2nsqjhx8hnrg4vvlzzpmp3smjkh0xl75h90g')
            external=estimate(item.content,2,item,external=True)
            self.assertEqual(external['platform_fee'],0)
            self.assertNotIn('quote',external)
        with patch('django.core.signing.time.time',return_value=timezone.now().timestamp()+301):
            with self.assertRaises(ValueError):wallet_fee_payload(item,quote)
        item.content_hash='changed'
        with self.assertRaises(ValueError):wallet_fee_payload(item,quote)

    @patch('studio.mint_fees.recommendations',side_effect=ValueError('offline'))
    def test_fee_outage_custom_rate_and_owner_boundaries(self,rates):
        self.assertEqual(self.client.post(self.fees,{**self.data,'speed':'standard'}).status_code,503)
        self.assertEqual(self.client.post(self.fees,{**self.data,'speed':'custom','fee_rate':'2.5'}).status_code,200)
        for value in ['NaN','Infinity','0','-1','1001','oops']:
            self.assertEqual(self.client.post(self.fees,{**self.data,'speed':'custom','fee_rate':value}).status_code,400)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.fees,{'speed':'custom','fee_rate':2}).status_code,404)
        self.assertFalse(m.OrdinalEdition.objects.exists())

    def test_sat_boundary_classification_and_exclusive_ranges(self):
        self.assertEqual(list(boundaries(0,1,1)),[(0,'mythic',0)])
        self.assertEqual(list(boundaries(1,5000000000,2)),[])
        self.assertEqual(list(boundaries(5000000000,5000000001,2)),[(5000000000,'uncommon',1)])
        self.assertEqual(list(boundaries(2016*5000000000,2016*5000000000+1,2016))[0][1],'rare')
        self.assertEqual(list(boundaries(210000*5000000000,210000*5000000000+1,210000))[0][1],'epic')
        self.assertEqual(list(boundaries(5000000000,5000000001,0)),[])

    @patch('studio.rare_sats.chain_height',return_value=900000)
    @patch('studio.rare_sats.fetch')
    def test_wallet_sats_are_signed_owned_rechecked_and_exclude_other_assets(self,fetch,height):
        address='bc1qwallet';txid='a'*64;point=txid+':0';sat=5000000000
        m.WalletIdentity.objects.create(user=self.user,address=address)
        output={'outpoint':point,'address':address,'value':1000,'indexed':True,'spent':False,'inscriptions':[],'runes':{},'sat_ranges':[[sat,sat+1000]]}
        responses={'/status':{'chain':'mainnet','height':900000,'sat_index':True,'rune_index':True},
            '/address/'+address+'/utxo':[{'txid':txid,'vout':0,'value':1000,'status':{'confirmed':True,'block_height':899990}}],
            '/output/'+point:output,'/tx/'+txid:{'txid':txid,'status':{'confirmed':True,'block_height':899990,'block_hash':'b'*64},'vout':[{'value':1000,'scriptpubkey_address':address}]},
            '/tx/'+txid+'/outspend/0':{'spent':False},'/block-height/899990':('b'*64).encode()}
        fetch.side_effect=lambda path,**kwargs:responses[path]
        result=inventory(self.user,address)
        self.assertEqual(result['items'][0]['sat'],sat)
        token=result['items'][0]['token']
        self.assertEqual(selection(self.user,token)['sat'],sat)
        with self.assertRaises(ValueError):selection(self.other,token)
        with self.assertRaises(ValueError):selection(self.user,token+'x')
        self.data.update(sat_mode='special',sat_choice=token)
        self.assertEqual(self.frozen().requested_sat,sat)
        output['inscriptions']=['c'*64+'i0']
        self.assertEqual(inventory(self.user,address)['items'],[])
        with self.assertRaises(ValueError):selection(self.user,token)
        output['inscriptions']=[];responses['/tx/'+txid+'/outspend/0']['spent']=True
        with self.assertRaises(ValueError):selection(self.user,token)
        with self.assertRaises(ValueError):inventory(self.other,address)

    @patch('studio.rare_sats.selection',side_effect=ValueError('Moved'))
    def test_special_sat_freeze_fails_closed(self,selection):
        for payload in [{**self.data,'sat_mode':'special','requested_sat':'123'},
                        {**self.data,'sat_mode':'special','sat_choice':'stale'}]:
            self.client.post(self.url,payload)
            self.assertFalse(m.OrdinalEdition.objects.exists())
