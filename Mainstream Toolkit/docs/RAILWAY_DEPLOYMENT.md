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
