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
