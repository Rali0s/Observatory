# Wallet authentication, membership cards, and native ordinal trading

## Local setup

Use Python 3.12 (matching the Railway Docker image) and Node 22. Run `make setup`, `make check`, `make test`, then `make run` at the repo root. The `.env` file lives in `Mainstream Toolkit/web_platform`; it never overrides externally supplied environment variables. SQLite is used locally unless PostgreSQL variables are explicitly configured. The root `.venv`, local database, and `.env` are excluded from Git and deployment.

## Xverse accounts

`/accounts/login/` offers Continue with Xverse. The server issues a random, domain-bound challenge linked to the current Django session and a five-minute expiry. A valid signature is required to create or sign into an account. Challenges are consumed under a database lock, including invalid attempts. A signature cannot change accounts, domains, addresses, or sessions, and it cannot be replayed concurrently.

The payment-address flow requests explicit ECDSA signatures, recovers the secp256k1 public key, and checks the exact mainnet P2SH-P2WPKH or P2WPKH address. The ordinal-address flow uses BIP322 simple Taproot key-path verification (default or ALL sighash only), including verification against an official Bitcoin BIP322 test vector. Script-path and multisig proofs are unsupported.

Existing password accounts should sign in first, then link the payment address at `/account/wallet/` and the ordinal address at `/account/collection/`. Addresses are unique across accounts; ownership cannot be reassigned by an unauthenticated connection response. Wallet-only accounts have unusable passwords. There is no automatic account merge, seed phrase custody, or wallet recovery. Verified addresses stay private to account/collection pages and administrative records; profiles do not reveal them automatically.

## Stripe membership setup

Configure these on **both web and worker**:

- `STRIPE_SECRET_KEY`: begin with the Stripe test secret.
- `STRIPE_WEBHOOK_SECRET`: the signing secret for this endpoint/environment.
- `STRIPE_ENABLED=1`: only after completing test Checkout and webhook delivery.
- `PUBLIC_BASE_URL=https://observate.up.railway.app` in production, or `http://127.0.0.1:8000` locally.

Register `https://observate.up.railway.app/webhooks/stripe/` in Stripe. Subscribe to `checkout.session.completed`, `checkout.session.async_payment_succeeded`, and `checkout.session.expired`. For local Stripe CLI testing, forward events to `http://127.0.0.1:8000/webhooks/stripe/` and use the CLI's signing secret in the local `.env` file. Do not paste keys into Git or chat.

Pricing stays in the server membership policy: $18 for 4,320 blocks; $45 after the redemption threshold. Card checkout is a one-time USD payment. No recurring subscription, price supplied by a browser, seller payout, or ordinal purchase runs through Stripe. The browser return cannot grant membership: the server retrieves provider state and validates the order ID, user, session, mode, currency, amount, and paid state. Signed webhooks and manual/worker reconciliation use the same locked fulfillment path. Early renewal retains remaining blocks.

A paid order received while the block clock is stale becomes `paid_pending_blocks`; the worker credits it once a fresh height is available. Unknown checkout creation outcomes are retained as `uncertain` and block another checkout. Reconciliation can recover the original session from Stripe and never creates another charge. If the provider has no matching session, an operator must reconcile the order before reopening checkout. The app does not automatically process refunds, disputes, or entitlement reversals; handle these in Stripe and the membership administration process before a paid launch.

## Native marketplace

Set `ORDINAL_INDEX_URL` to a trusted HTTPS mainnet `ord server` with inscription, sat, and **rune indexing**. The service uses `/status`, `/inscription/{id}`, `/output/{outpoint}`, and `/outputs/{address}?type=cardinal|inscribed`, plus the existing Esplora transaction, outspend, canonical-block, and broadcast endpoints. No provider is silently chosen for ordinal ownership data. Set `ORDINAL_TRADING_ENABLED=1` only after validating the real Xverse flow and provider behavior on a staging deployment.

An edition must already be content-verified, minted, publicly visible, and currently held by a proven Taproot wallet address. Its output must contain exactly that inscription and no runes. Both the ordinal address and the payout/payment address must be linked through signed proofs. A collector can resell; author identity alone never grants authority to sell an inscription held elsewhere.

The seller signs a one-input/one-output offer using `SIGHASH_SINGLE|ANYONECANPAY` (131), committing to the exact payout. The buyer transaction prepends a confirmed cardinal input and a receiving output. That output receives every sat in the leading input and in the entire inscription UTXO, preserving the inscription's position regardless of its offset. The seller input and payout both move to index one. Buyer funding inputs sign ALL, protecting all outputs, price, recipient, and change. The backend verifies seller and buyer signatures against its own canonical transaction and verified UTXO values before broadcasting.

Payment inputs must be P2SH-P2WPKH or P2WPKH, confirmed, unspent, and indexed with no inscriptions or runes. The initial flow needs at least two cardinal outputs and supports at most ten funding inputs. It requires a dust-safe change output. Users enter a total network fee; the current UI does not fetch a live fee estimate. Prices are limited to 546–100,000,000 sats and fees to 500–100,000 sats. No platform fee or royalty is added.

A signed purchase is saved before broadcasting. Ambiguous broadcasts retain exactly the same transaction bytes and txid; retries rebroadcast those bytes. Purchases are marked collected only after six canonical confirmations of the exact approved transaction. The worker checks submitted purchases. Unsigned attempts can be abandoned; broadcast attempts remain recorded. Automated fee bumping, conflict recovery, and reorg audits of previously confirmed history are not implemented.

Delisting stops new preparation in Observatory. Bitcoin signatures cannot be revoked by changing a database field: a transaction previously shared with a buyer may still execute. The seller must move the inscription to a fresh output to invalidate an outstanding offer at the protocol level. This limitation appears in the seller UI. There are no auctions, batches, bids, escrow, or fiat ordinal purchases in this first implementation.

## Collections and public discovery

Author search uses pen names and bios, with optional ordinal filtering and stable pagination. Public profiles, followed-author feeds, and bookmarks use the existing community model. Ordinal search excludes hidden publications and unverified editions.

Collection refresh discovers known Observatory inscriptions at proven ordinal addresses and rechecks previous holdings. It handles up to 100 known editions per refresh; larger or unsupported outputs require operator follow-up. Holdings are observations with timestamps, not permanent ownership claims. Failure retains previous observations with an explicit stale-data notice. Bitcoin trade history and current holdings are separate: an inscription may move after a completed purchase.

## Verification and remaining launch work

Tests cover genuine ECDSA and Schnorr signatures; an official BIP322 vector; expiry, session isolation, replay, account-link collisions, inactive accounts, and CSRF; Stripe identity, amount, signature, delayed block state, duplicate delivery, redemption, and uncertain responses; transaction output tampering, ordinal sat placement, asset-bearing funding rejection, stale ownership, private attempt access, and broadcast recovery. PostgreSQL tests exercise concurrent login replay and membership crediting. The frontend suite checks wallet rejection and challenge-before-signing behavior.

No real Stripe charge, live Xverse signing, or mainnet inscription trade was performed. The native trade assembly has not been validated against Bitcoin Core regtest or a live wallet, so trading stays disabled. Credentials, index service, wallet verification, and an operational refund/dispute policy are still required before collecting money.

References: [Xverse signMessage](https://docs.xverse.app/sats-connect/bitcoin-methods/signmessage), [Xverse signPsbt](https://docs.xverse.app/sats-connect/bitcoin-methods/signpsbt), [Bitcoin BIP322](https://github.com/bitcoin/bips/blob/master/bip-0322.mediawiki), [Stripe Checkout](https://docs.stripe.com/api/checkout/sessions/create), [Stripe fulfillment](https://docs.stripe.com/checkout/fulfillment), [ord API](https://docs.ordinals.com/guides/api.html).
