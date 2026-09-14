from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from embit import ec, script, psbt
from embit.networks import NETWORKS
from embit.transaction import TransactionOutput
from . import marketplace as market
from .models import AuthorProfile, ChainTip, OrdinalEdition, OrdinalHolding, OrdinalListing, OrdinalTrade, Publication, WalletIdentity


@override_settings(ORDINAL_TRADING_ENABLED=True, ORDINAL_INDEX_URL='https://index.example')
class MarketplaceTests(TestCase):
    def setUp(self):
        self.seller = get_user_model().objects.create_user('seller')
        self.buyer = get_user_model().objects.create_user('buyer')
        self.seller_key = ec.PrivateKey(bytes.fromhex('33' * 32))
        self.buyer_key = ec.PrivateKey(bytes.fromhex('44' * 32))
        self.receive_key = ec.PrivateKey(bytes.fromhex('55' * 32))
        self.seller_address = script.p2tr(self.seller_key.get_public_key()).address(NETWORKS['main'])
        self.payment_address = script.p2sh(script.p2wpkh(self.buyer_key.get_public_key())).address(NETWORKS['main'])
        self.receive_address = script.p2tr(self.receive_key.get_public_key()).address(NETWORKS['main'])
        for user, address in ((self.seller, self.seller_address), (self.buyer, self.payment_address), (self.buyer, self.receive_address)):
            WalletIdentity.objects.create(user=user, address=address)
        profile = AuthorProfile.objects.create(user=self.seller, pen_name='A writer')
        self.post = Publication.objects.create(author=profile, title='Inscribed story', excerpt='Read me', body='Hello', kind='story')
        self.edition = OrdinalEdition.objects.create(publication=self.post, content='Hello', content_hash='a' * 64,
            sat_mode='regular', status='minted', inscription_id='a' * 64 + 'i0')
        self.output = {'outpoint': 'a' * 64 + ':0', 'address': self.seller_address}
        self.utxo = TransactionOutput(1000, market.address_script(self.seller_address))
        self.payment_utxo = TransactionOutput(60000, market.address_script(self.payment_address))
        self.cardinal = [('b' * 64 + ':0', TransactionOutput(600, market.address_script(self.payment_address))), ('c' * 64 + ':0', self.payment_utxo)]

    def listing(self):
        with patch('studio.marketplace.holding', return_value=(self.output, self.utxo)):
            listing = market.create_listing(self.seller, self.edition, 20000, self.seller_address)
            signed = market.decode(listing.unsigned_psbt)
            digest = signed.tx.sighash_taproot(0, [self.utxo.script_pubkey], [self.utxo.value], sighash=131)
            signature = self.seller_key.taproot_tweak().schnorr_sign(digest).serialize() + b'\x83'
            signed.inputs[0].unknown[b'\x13'] = signature
            market.activate_listing(listing, market.encode(signed))
        listing.refresh_from_db()
        return listing

    def trade(self, listing=None):
        with patch('studio.marketplace.holding', return_value=(self.output, self.utxo)), patch('studio.marketplace.cardinal_inputs', return_value=self.cardinal):
            return market.create_trade(self.buyer, listing or self.listing(), self.payment_address, self.receive_address, 3000, self.buyer_key.get_public_key().sec().hex())

    def sign_buyer(self, trade, change=None):
        signed = market.decode(trade.unsigned_psbt)
        if change:
            change(signed)
        for index in [0, 2]:
            digest = signed.tx.sighash_segwit(index, script.p2pkh(self.buyer_key.get_public_key()), signed.inputs[index].witness_utxo.value, sighash=1)
            signed.inputs[index].partial_sigs[self.buyer_key.get_public_key()] = self.buyer_key.sign(digest).serialize() + b'\x01'
        return market.encode(signed)

    def test_atomic_exchange_preserves_inscription_sats_and_exact_price(self):
        trade = self.trade()
        final = market.finalize_trade(trade, self.sign_buyer(trade))
        self.assertEqual(final.vout[0].value, 1600)
        self.assertEqual(final.vout[0].script_pubkey.address(NETWORKS['main']), self.receive_address)
        self.assertEqual(final.vout[1].value, 20000)
        self.assertEqual(final.vout[1].script_pubkey.address(NETWORKS['main']), self.seller_address)
        self.assertEqual(final.vout[2].value, 37000)
        self.assertEqual(final.vin[1].txid.hex(), 'a' * 64)
        self.assertTrue(all(inp.witness.items for inp in final.vin))
        # Every sat from the original inscription UTXO is inside receiving output zero.
        for offset in (0, 999):
            self.assertLess(600 + offset, final.vout[0].value)

    def test_reject_price_recipient_input_order_and_fee_tampering(self):
        trade = self.trade()
        for modify in (lambda p: setattr(p.outputs[1], 'value', 1),
                       lambda p: setattr(p.outputs[0], 'script_pubkey', market.address_script(self.seller_address)),
                       lambda p: setattr(p.inputs[0], 'vout', 9),
                       lambda p: setattr(p.outputs[2], 'value', 1)):
            with self.assertRaises(ValueError):
                market.finalize_trade(trade, self.sign_buyer(trade, modify))

    def test_seller_signature_cannot_be_used_at_a_different_price(self):
        listing = self.listing()
        signed = market.decode(listing.signed_psbt)
        signed.outputs[0].value += 1
        with self.assertRaises(ValueError):
            market.verify_tap_signature(signed, 0, market.tap_signature(signed, 0), 131)

    def test_buyer_signatures_must_commit_to_all_outputs(self):
        trade = self.trade()
        signed = market.decode(self.sign_buyer(trade))
        sig = signed.inputs[0].partial_sigs[self.buyer_key.get_public_key()]
        signed.inputs[0].partial_sigs[self.buyer_key.get_public_key()] = sig[:-1] + b'\x83'
        with self.assertRaises(ValueError):
            market.finalize_trade(trade, market.encode(signed))

    def test_only_verified_wallet_owner_can_list(self):
        with patch('studio.marketplace.holding', return_value=(self.output, self.utxo)):
            with self.assertRaises(ValueError):
                market.create_listing(self.buyer, self.edition, 20000, self.payment_address)
        self.assertFalse(OrdinalListing.objects.exists())

    def test_single_active_listing_and_no_duplicate_purchase(self):
        listing = self.listing()
        with patch('studio.marketplace.holding', return_value=(self.output, self.utxo)):
            with self.assertRaises(ValueError):
                market.create_listing(self.seller, self.edition, 30000, self.seller_address)
        self.trade(listing)
        with self.assertRaises(ValueError):
            self.trade(listing)
        self.assertEqual(OrdinalTrade.objects.count(), 1)

    @override_settings(ORDINAL_TRADING_ENABLED=False)
    def test_trading_flag_rejects_listing_creation(self):
        with self.assertRaises(ValueError):
            market.create_listing(self.seller, self.edition, 20000, self.seller_address)

    def test_current_owner_change_blocks_purchase(self):
        listing = self.listing()
        with patch('studio.marketplace.holding', return_value=({'outpoint': 'd' * 64 + ':0', 'address': self.receive_address}, self.utxo)):
            with self.assertRaises(ValueError):
                market.create_trade(self.buyer, listing, self.payment_address, self.receive_address, 3000, self.buyer_key.get_public_key().sec().hex())
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'stale')

    def test_asset_bearing_inputs_are_never_selected(self):
        candidate = {'outpoint': 'c' * 64 + ':0', 'value': 60000}
        for unsafe in ({'inscriptions': ['other'], 'runes': {}}, {'inscriptions': [], 'runes': {'TOKEN': 1}}):
            with patch('studio.marketplace.fetch', return_value=[candidate]), patch('studio.marketplace.output_info', return_value=({'address': self.payment_address, **unsafe}, self.payment_utxo)):
                with self.assertRaises(ValueError):
                    market.cardinal_inputs(self.payment_address, 20000)

    def test_cardinal_output_index_must_match_bitcoin_and_be_unspent(self):
        ChainTip.objects.create(height=900005, block_hash='e' * 64, observed_at=timezone.now())
        info = {'outpoint': 'c' * 64 + ':0', 'address': self.payment_address, 'value': 60000, 'spent': False, 'indexed': True}
        tx = {'txid': 'c' * 64, 'status': {'confirmed': True, 'block_height': 900000, 'block_hash': 'e' * 64},
            'vout': [{'value': 60000, 'scriptpubkey_address': self.payment_address, 'scriptpubkey': self.payment_utxo.script_pubkey.data.hex()}]}
        with patch('studio.marketplace.fetch', side_effect=[info, tx, {'spent': False}, ('e' * 64).encode()]):
            self.assertEqual(market.output_info(info['outpoint'])[1].value, 60000)
        with patch('studio.marketplace.fetch', side_effect=[info, tx, {'spent': True}]):
            with self.assertRaises(ValueError): market.output_info(info['outpoint'])
        with patch('studio.marketplace.fetch', side_effect=[dict(info, value=10), tx, {'spent': False}, ('e' * 64).encode()]):
            with self.assertRaises(ValueError): market.output_info(info['outpoint'])

    def test_pages_do_not_expose_private_transactions_or_hidden_editions(self):
        trade = self.trade()
        other = get_user_model().objects.create_user('other')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('market-trade', args=[trade.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('market-trade-action', args=[trade.pk]), {'action': 'submit'}).status_code, 404)
        self.client.logout()
        self.assertContains(self.client.get(reverse('ordinal-directory')), 'Inscribed story')
        self.post.is_visible = False
        self.post.save()
        self.assertNotContains(self.client.get(reverse('ordinal-directory')), 'Inscribed story')
        self.assertEqual(self.client.get(reverse('market-edition', args=[self.edition.pk])).status_code, 404)

    def test_profile_search_and_empty_collections_render(self):
        self.assertContains(self.client.get(reverse('authors'), {'q': 'writer'}), 'A writer')
        self.assertNotContains(self.client.get(reverse('authors'), {'q': 'missing'}), 'A writer')
        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(reverse('collection')), 'No verified Observatory editions')
        self.assertContains(self.client.get(reverse('market-trade', args=[self.trade().pk])), 'Approve purchase')

    def test_broadcast_timeout_retains_exact_transaction_and_retry_is_identical(self):
        trade = self.trade()
        signed = self.sign_buyer(trade)
        def output(point):
            if point == self.output['outpoint']:
                return {'inscriptions': [self.edition.inscription_id], 'runes': {}}, self.utxo
            return {'inscriptions': [], 'runes': {}}, self.payment_utxo
        with patch('studio.marketplace.synced_index'), patch('studio.marketplace.output_info', side_effect=output), patch('studio.marketplace.urlopen', side_effect=TimeoutError()) as broadcast:
            with self.assertRaises(ValueError): market.submit_trade(trade, signed)
            trade.refresh_from_db()
            self.assertEqual(trade.status, 'broadcasting')
            stored = trade.raw_transaction
            self.assertTrue(stored)
            with self.assertRaises(ValueError): market.submit_trade(trade, '')
            self.assertEqual(broadcast.call_args_list[0].args[0].data, broadcast.call_args_list[1].args[0].data)
            self.assertEqual(trade.raw_transaction, stored)
            self.assertEqual(OrdinalTrade.objects.count(), 1)

    def test_only_exact_canonical_confirmed_transaction_marks_trade_collected(self):
        trade = self.trade()
        final = market.finalize_trade(trade, self.sign_buyer(trade))
        trade.raw_transaction = final.serialize().hex()
        trade.txid = final.txid().hex()
        trade.status = 'broadcast'
        trade.save()
        ChainTip.objects.create(height=900005, block_hash='e' * 64, observed_at=timezone.now())
        tx = {'txid': trade.txid, 'status': {'confirmed': True, 'block_height': 900000, 'block_hash': 'e' * 64}}
        with patch('studio.marketplace.fetch', side_effect=[tx, ('f' * 64).encode()]):
            with self.assertRaises(ValueError): market.reconcile_trade(trade)
        trade.refresh_from_db()
        self.assertEqual(trade.status, 'broadcast')
        with patch('studio.marketplace.fetch', side_effect=[tx, ('e' * 64).encode(), trade.raw_transaction.encode()]):
            market.reconcile_trade(trade)
        trade.refresh_from_db()
        trade.listing.refresh_from_db()
        self.assertEqual(trade.status, 'confirmed')
        self.assertEqual(trade.listing.status, 'sold')
