# The Observatory

Django writing studio, author community, and Bitcoin ordinal editions. Railway hosts the app at **https://observate.up.railway.app/**.

## Local development

Requires Python **3.12** and Node **22**. From this repository root:

```sh
make setup
make run
```

Open http://127.0.0.1:8000. `make setup` installs the isolated Python environment and pinned frontend packages, builds wallet bundles, collects static assets, and migrates the local SQLite database. It creates `Mainstream Toolkit/web_platform/.env` from `.env.example` only if absent. Existing process environment variables take precedence over this file. Credentials and local databases are ignored by Git.

Create an account through `/join/` or Xverse sign-in. An existing account can link its wallet at `/account/wallet/`. Create an administrator with:

```sh
.venv/bin/python 'Mainstream Toolkit/web_platform/manage.py' createsuperuser
```

`make worker` runs the Bitcoin membership clock, payment reconciliation, inscription verification, and purchase confirmation worker. `make check` checks Django and migration consistency. `make test` builds frontend assets and runs Python and JavaScript tests.

## Features and setup

- **Admin access and invites:** unlimited admin publishing and plan allowances; admin-issued three-month and lifetime passes, with optional selected-member issuing permissions.
- **Reading Room sharing:** X, Facebook, Blogger, LinkedIn, copy link, and device sharing on public readings.

See [invite operation and domain shortlist](Mainstream%20Toolkit/docs/INVITES_AND_SHARING.md).

- **Xverse authentication:** server-generated, session-bound, five-minute, single-use signature challenges. Payment-address ECDSA sign-in and Taproot BIP322 ownership proofs for collection addresses. New wallet sign-ins create passwordless accounts; linking an existing account requires signing in first.
- **Membership cards:** Stripe hosted Checkout for $18 per 4,320 confirmed blocks, or $45 for redemption plus renewal. One-time payments, no automatic renewal. Signed webhooks and worker reconciliation grant each order once. Configure test credentials and webhook delivery before enabling.
- **Public profiles and discovery:** `/authors/` searches pen names and biographies; profiles show public publications and ordinal editions, with follow/unfollow. `/ordinals/` searches verified public editions and filters sale listings.
- **Native ordinal marketplace:** Taproot inscription holders can list and resell editions; buyers review an atomic Bitcoin payment/inscription swap through Xverse. `/account/collection/` maps known Observatory editions from proven ordinal wallets. No platform custody or private keys. Bitcoin index configuration and live-wallet validation are required before enabling.

See [integration setup and limits](Mainstream%20Toolkit/docs/WALLET_PAYMENTS_MARKETPLACE.md) and [Railway deployment](Mainstream%20Toolkit/docs/RAILWAY_DEPLOYMENT.md). Card collection, Bitcoin membership collection, and ordinal trading default to **off**. Local tests do not spend money or broadcast Bitcoin transactions.
