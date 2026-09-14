> Current implementation update: see [Story Studio, storage and direct Bitcoin](STORY_STUDIO_AND_DIRECT_BITCOIN.md). Direct Xverse checkout no longer requires BTCPay; live payments remain disabled pending receiving-wallet setup. The platform brand is The Observatory.

# Railway deployment handoff

Railway suits this Django/PostgreSQL architecture. Build configuration is prepared; no service is deployed or billed. Use a private sanitized deployment repository. Never upload manuscripts, local databases, .env files or Streamlit secrets.

## Services

1. Web: root `Mainstream Toolkit`, config `/Mainstream Toolkit/railway.toml`, Dockerfile `web_platform/Dockerfile`. Build context must include sibling `narrative_engine.py`. Review the Docker ignore allowlist. Gunicorn serves Django and WhiteNoise serves static files; pre-deploy runs migrations.
2. PostgreSQL: persistent private database shared by web and worker.
3. Redis: shared request-limit cache configured through REDIS_URL.
4. Worker: same image and database; command `python manage.py sync_memberships --loop`. Use a separate Railway config without the web HTTP healthcheck or migration command.

## Environment

Set DJANGO_DEBUG=0, generated DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS including your domain and healthcheck.railway.app, DJANGO_CSRF_TRUSTED_ORIGINS with the HTTPS origin, and TRUST_PROXY_HTTPS=1 only behind the trusted Railway proxy.

Map PostgreSQL variables into POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST and POSTGRES_PORT. POSTGRES_SSLMODE defaults to require; verify actual endpoint TLS support. Set REDIS_URL from private Redis. Production settings reject SQLite. /health/ checks database connectivity.

Direct Bitcoin membership payments use Xverse and server-side Esplora verification. Keep DIRECT_BITCOIN_ENABLED=0 until unused receiving addresses are imported and payment verification is tested. BTCPay is optional legacy support, not required. No Stripe integration is enabled.

Ordinal minting has a separate default-off admin switch and requires ORDINAL_INDEX_URL pointing to a trusted HTTPS mainnet ord JSON API with sat indexing. See ORDINAL_EDITIONS.md for the regular Xverse and external Gamma special-sat workflows and current limits. Do not enable paid or minting flows merely to make deployment succeed.

Create a new production admin through the deployed Django management command. Local SQLite accounts and manuscripts are not bundled or migrated by a source-code deployment. Configure database backups separately.

## Before public launch

Run migrations, collectstatic, checks and tests on staging PostgreSQL. Verify concurrent settlement, duplicate reconciliation, block boundaries, source outages, actual configured invoice lifecycle, backup restoration, HTTPS/static assets and proxy behavior. Add account recovery/email, login abuse protection and operational moderation. Signup has basic cached IP limiting; proxy-aware abuse controls remain work. Resolve uncertain invoices against provider metadata. Keep live payments disabled until verification is complete.

Analysis is synchronous with a 20,000-word cap; add a task queue before increasing it. Railway and BTCPay hosting costs are separate from author prices. Select resource plans in the operator account. This remains an alpha.

Sources: [Railway Django](https://docs.railway.com/guides/django), [configuration](https://docs.railway.com/config-as-code/reference), [healthchecks](https://docs.railway.com/deployments/healthchecks), [BTCPay](https://docs.btcpayserver.org/Development/ecommerce-integration-guide/), [Esplora API](https://github.com/Blockstream/esplora/blob/master/API.md).

## Deployment created 2026-09-14

Private source: https://github.com/Rali0s/Observatory (main).
Railway project: https://railway.com/project/8a863a75-2f59-4781-93e7-bfd21706319b
Web domain: https://observate.up.railway.app

Services: web, worker, Postgres and Redis in the production environment. Runtime secrets are generated and stored in Railway variables; database/cache variables use service references. Local databases and accounts are excluded.

This deployment uses CLI uploads from a clean `git archive`, not automatic GitHub deployments. Web archive root is Mainstream Toolkit. Worker uses the same source with railway.worker.toml copied to railway.toml in a separate deployment archive. RAILWAY_DOCKERFILE_PATH=web_platform/Dockerfile is configured on both services. Service settings explicitly set the web migration/healthcheck and worker start command.

The current Railway API no longer accepts DOCKERFILE as its Builder enum. Set the Dockerfile path explicitly; do not depend on the old builder value. Config-as-code is being deprecated by Railway; migrate these deployment settings to its current infrastructure-as-code format before the announced December 2026 cutoff.

Payments, external AI and ordinal minting remain off. Production admin access must be established separately from the local 3xc account. Configure backups and complete the operational checks above before inviting paying members.

## Domain rename repair — 2026-09-14

The rename to `observate.up.railway.app` left the old hostname in Django's allowed hosts and CSRF origins. Requests reached Gunicorn but returned HTTP 400. Updated the web service's `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`, retaining the previous host and Railway healthcheck host. Verified HTTP 200 at the new origin.

The updated application settings also admit the exact `RAILWAY_PUBLIC_DOMAIN` and its HTTPS CSRF origin, so another Railway-generated domain rename does not require hard-coded host updates. No wildcard host or CSRF origin is used. For custom domains, set allowed hosts and origins explicitly. `PUBLIC_BASE_URL` defaults to the Railway-generated domain unless explicitly configured.

New integration configuration and limits are in [wallet, payments, and marketplace](WALLET_PAYMENTS_MARKETPLACE.md). Preserve disabled payment/trading flags until those prerequisites are met. Both services need the new application version for reconciliation.

## Application update deployed — 2026-09-14

Deployed code commit `e278e14` from the local `feature/wallet-payments-discovery` branch using clean Git archives. The branch has not been pushed to GitHub or merged into `main`.

- Web deployment: `fb430fae-0902-4142-bb6c-0f60db869609` — SUCCESS. Migrations 0009 and 0010 applied successfully.
- Worker deployment: `5816eba1-99e2-4704-80d3-e6dce1279518` — SUCCESS. Verified its Bitcoin block synchronization log.
- HTTPS smoke checks passed for `/health/`, `/accounts/login/`, `/authors/`, `/ordinals/`, and the hashed Xverse authentication bundle.
- Validation: 89 Django tests passed against PostgreSQL, including two concurrency tests; 13 frontend tests passed; Django checks, migration consistency, and frontend dependency audit passed. SQLite validation passed with the PostgreSQL-only concurrency tests skipped.
- Stripe credentials and the ordinal index are absent. Card collection and native ordinal trading remain disabled. No real wallet login, charge, or Bitcoin trade was performed during deployment.

Local development server and membership worker were started separately with the ignored local SQLite database. Restart with `make run` and `make worker` from the repository root.

## Admin invites and sharing deployed — 2026-09-14

Code commit `eafd6a2` is deployed to both services:

- Web `42985b82-eee5-4e31-bea7-89c3efad836c` — SUCCESS.
- Worker `dbb58bfb-a5de-4bbe-8867-5de11c034a86` — SUCCESS.
- Migration 0011 adds invite settings, hashed invitation codes, redemptions, and complimentary publishing access.
- Validation: 100 Django tests passed on PostgreSQL, including concurrent last-use invitation redemption; 13 frontend tests passed. Django checks and migration consistency passed. Browser preview verified public sharing icons, copy-link feedback, unlimited admin membership, and invite management controls.
- Production health, homepage, sharing JavaScript, and both product PNGs returned 200. PNG hashes match the supplied images. Unauthenticated invite access redirects to sign-in.
- Supplied Stripe keys, webhook secret, and catalog IDs are configured in web and worker environments. `STRIPE_ENABLED=0` is retained pending the one-time versus recurring Writer billing choice. A signed no-order webhook check returned 200; an invalid signature returned 400. No payment order or charge was created.
- Stripe Writer and Unlock product images now point to the verified production static PNG URLs.

See [invite operation, sharing, and five domain choices](INVITES_AND_SHARING.md). No custom domain has been purchased or attached. Production admin authentication was not exercised; the local browser preview used an isolated disposable database.

## Visual writing editor deployed — 2026-09-14

Code commit `954e581` is live on web (`17ad62d2-7081-40f7-a9fd-b0e85bcfbc38`) and worker (`4da3c53b-d267-4514-bc31-813f5d6c4607`); both deployments succeeded. No database migration was needed.

- Visual/Markdown switching, H1–H3, bold, italic, lists, quotes, undo/redo, and Markdown help are available in chapter, revision, publication, and front-matter fields.
- Browser verification confirmed live heading conversion, bold serialization, help display, revision saving, and visual reopening in the chapter workbench.
- 103 Django tests completed: 100 passed and the 3 PostgreSQL concurrency tests were skipped on SQLite. All 17 frontend tests passed. Django/migration checks and npm audit passed.
- Production health and editor JavaScript/CSS returned HTTP 200; deployed asset hashes match the local build.

See [writing editor behavior and implementation](WRITING_EDITOR.md). `observatory.cafe` was not resolving from the verification environment at the time of this release, so HTTPS asset checks used the existing Railway-generated domain.

## Mobile reading deployed — 2026-09-14

Code commit `f49f2d6` is live on web (`43735fd0-b7f2-4cd4-86b4-89c9a324cb72`) and worker (`17d97350-08f7-495e-911d-0675ef9ca07f`); both deployments succeeded. No database migration was needed.

- Phone navigation focuses on reading, author discovery, invitations, and account access. Desktop tools display a notice directing readers to a computer.
- Admin-created invites include shareable links. Signup and password/wallet sign-in preserve the pending code and return to a separate redemption confirmation.
- Validation: 111 Django tests completed, with 108 passed and 3 PostgreSQL-only tests skipped on SQLite. All 17 frontend tests, Django checks, migration consistency, and diff whitespace checks passed.
- A 390-pixel browser preview verified the reading layout. The workstation locked during further interactive checks; narrow-screen authentication and real mobile wallet behavior were not verified in a browser. Automated tests cover invite continuation and redemption.
- Production `/`, `/health/`, `/invite/`, `/accounts/login/`, `/join/`, and `/authors/` returned HTTP 200. Mobile CSS/JavaScript hashes match the local build. Invite responses have no-store and no-referrer headers.
- Local development was restarted with the new code. Deployment used clean Git archives; no local accounts, databases, or credentials were uploaded. Existing payment flags and domain settings were preserved.

See [mobile reading and invite links](MOBILE_READING.md).

## Verified account merging deployed — 2026-09-14

Code commit `4a960f2` is deployed to web (`8c5f7e79-4523-4822-95f3-8878ff3f3878`) and worker (`ad3f5275-ec3a-4e6e-93b4-b3082c7b53ca`), both SUCCESS. Migration 0012 adds merge attempts, retained account aliases, wallet proof scope, and original billing identity preservation.

- Account and wallet-conflict links open the verified merge flow. Both accounts require fresh password or linked-wallet proof, then an explicit review and confirmation. Admin accounts take priority over paid accounts, then wallet accounts.
- The full PostgreSQL suite passed 123 tests. Subsequent final merge/concurrency checks passed 17 tests, and the final quota regression run passed all 13 merge tests. All 19 frontend tests, Django checks, and migration consistency passed.
- Browser verification used disposable local accounts: password verification of both accounts, paid-account priority, the mobile review screen, and successful consolidation were verified. No production account was merged and no real wallet signature or payment was requested during verification.
- Live health and login returned 200; anonymous access to the merge page correctly returns to sign-in. The production Xverse bundle matches the tested build, including the actionable wallet-conflict link.
- Local development was migrated and restarted. Existing payment switches and domain settings were preserved.

See [account merging behavior and operations](ACCOUNT_MERGING.md).

## Guided ordinal minting deployed — 2026-09-14

Code commit `5e861f8` is live on web (`57c7e8ca-a604-4ef4-8297-890075e12690`) and worker (`88d83477-7223-40de-954f-5689f364e20f`), both SUCCESS. No database migration was needed.

- Replaced JSON entry with guided edition fields and add/remove metadata traits. Regular mode hides rare-sat controls. Linked-wallet discovery lists classical Ordinal rarity from confirmed indexed outputs; signed choices are checked again when freezing.
- Miner estimates use live sats/vB recommendations, UTF-8 content size, commit/reveal size estimates, and a separate postage allowance. Regular minting requires a current signed fee quote. Launch platform fee is explicitly **0 sats** in both services and local development.
- Registered all three supplied public wallet references and explicitly configured Gamma's public mainnet sat/rune index. Existing payment and trading switches were preserved. Shared membership/redemption references are not reused as individual invoice addresses.
- Validation: all 134 Django tests passed against PostgreSQL; SQLite completed 134 with 5 PostgreSQL-only tests skipped. All 19 frontend tests, Django checks, migration consistency, and whitespace checks passed.
- Local browser verification covered adding traits, a live fee estimate, regular/special visibility, fixture-wallet rare-sat selection, and successful freezing of the selected sat into the Gamma flow. Real Xverse signatures, Bitcoin broadcasts, and payments were not performed. Gamma's live index and mempool fee endpoints responded successfully.
- Production health, login, and ordinal directory returned HTTP 200. Anonymous wallet-sat access redirects to login. The deployed ordinal-builder JavaScript/CSS and Xverse inscription JavaScript match the tested local asset hashes.
- The worker had one startup chain lookup failure, then recovered on its next scheduled check and verified Bitcoin mainnet block 966,979. Local development was restarted; disposable preview services were stopped.

Special-sat execution remains a manual Gamma step because Xverse's standard inscription API cannot select a specific sat. Fee estimates exclude provider charges; the wallet/provider presents the final transaction. See [ordinal edition operation and fee policy](ORDINAL_EDITIONS.md).

## Creepypasta darkness deployed — 2026-09-14

Code commit `185b846` is live on web (`cccd6b6f-91cf-4611-9d00-f07e2b6c34f3`) and worker (`dd07ce6b-9c15-4aea-a5c7-40328f936bdf`), both SUCCESS. Production migration 0013 added the Creepypasta profile choice successfully.

- New revisions and chapter snapshots can opt into a private 0–5 darkness estimate, five horror dimensions, chapter ratings, strongest passages, supporting evidence, and revision prompts. Existing reports retain their original analysis.
- Full validation passed 140 PostgreSQL tests and 19 frontend tests. SQLite completed 140 tests with 5 PostgreSQL-only tests skipped. A final six-test darkness regression run passed after correcting dimension descriptions. Django checks, migration consistency, and whitespace checks passed.
- Browser verification used a disposable local report: confirmed the overall rating, expanded dimension descriptions, separate zero-gore result, and the Darkness timeline. Exports, chapter snapshots, comparisons with legacy profiles, and account isolation are covered by automated tests.
- Production health and login returned 200; anonymous studio access redirected to login. Local migration and restart succeeded. No production manuscript was created or rescored for verification, and no manuscript was sent to an external AI service.

See [darkness scale, method, and limitations](CREEPYPASTA_DARKNESS.md).

## Copyright footer deployed — 2026-09-14

Code commit `011a4eb` is live on web (`797ba7a4-4d6e-4708-a1e8-f8b261afed7b`, SUCCESS). The shared footer now reads “Made for close reading. Your judgment leads the revision. | A Premise LLC Venture © 2026-2027”. Verified the exact text in local and production HTTP responses. This template-only change requires no migration or worker deployment.

## Invite campaign management deployed — 2026-09-14

Code commit `3669169` is live on web (`ecfdf8dc-e953-4792-abcf-772cd2212d6d`) and worker (`628f2dd4-9a6d-4c3b-b39b-bcdc134902e6`), both SUCCESS. No migration was required.

- Account now links to invite management for authorized issuers. Dashboard totals, search, status/type filters, pagination, per-campaign progress, settings, and recipient history are available. Limits and deadline edits preserve prior grants and serialize with redemption. Non-admin issuers remain scoped to their own campaigns and see public recipient names rather than sign-in names.
- All 145 PostgreSQL tests and 19 frontend tests passed. SQLite completed 145 tests with 5 PostgreSQL-only tests skipped. Django, migration consistency, and whitespace checks passed.
- Browser verification used disposable local campaigns and a redemption: confirmed the dashboard, progress, grant history, and saving a changed capacity from 10 to 12. No production invitation, redemption, or permission was changed for verification.
- Production health/login returned 200; dashboard and new detail routes redirect anonymous visitors to sign-in. Worker verified Bitcoin block 966,981. Local development restarted and the disposable preview was stopped.

See [invite management and tracking behavior](INVITES_AND_SHARING.md). Tracking covers completed redemptions, not delivery, link opens, or incomplete signups.
