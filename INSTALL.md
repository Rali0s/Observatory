# Installation and operation

## Requirements

Python **3.12**, Node.js **22**, npm, and Git. GNU Make provides shortcuts on macOS/Linux; Windows commands are below. SQLite is the local default. Production requires PostgreSQL; the integration suite has been exercised with PostgreSQL 16. Initial dependency installation needs internet access.

No payment or AI keys are required for local writing, offline analysis, or tests.

## macOS and Linux

```sh
git clone --branch feature/wallet-payments-discovery https://github.com/Rali0s/Observatory.git
cd Observatory
make setup
.venv/bin/python 'Mainstream Toolkit/web_platform/manage.py' createsuperuser
make run
```

Visit `http://127.0.0.1:8000/`. Admin is at `/admin/`; normal registration is at `/join/`. If Python 3.12 has another executable name, use `make setup PYTHON=/path/to/python3.12`.

Run `make worker` in a second terminal from the repository root. This maintains the Bitcoin clock and reconciles configured integrations. Network failures retry on the next loop. Offline manuscript analysis does not depend on the clock.

## Windows PowerShell

These commands run from the repository root without activating PowerShell scripts:

```powershell
git clone --branch feature/wallet-payments-discovery https://github.com/Rali0s/Observatory.git
Set-Location Observatory
py -3.12 -m venv .venv
& .venv/Scripts/python.exe -m pip install -r 'Mainstream Toolkit/web_platform/requirements.txt'
Push-Location 'Mainstream Toolkit/web_platform/frontend'
npm ci
npm run build
Pop-Location
if (-not (Test-Path 'Mainstream Toolkit/web_platform/.env')) {
    Copy-Item 'Mainstream Toolkit/web_platform/.env.example' 'Mainstream Toolkit/web_platform/.env'
}
& .venv/Scripts/python.exe 'Mainstream Toolkit/web_platform/manage.py' collectstatic --noinput
& .venv/Scripts/python.exe 'Mainstream Toolkit/web_platform/manage.py' migrate
& .venv/Scripts/python.exe 'Mainstream Toolkit/web_platform/manage.py' createsuperuser
& .venv/Scripts/python.exe 'Mainstream Toolkit/web_platform/manage.py' runserver 127.0.0.1:8000
```

In a second terminal from the repository root:

```powershell
& .venv/Scripts/python.exe 'Mainstream Toolkit/web_platform/manage.py' sync_memberships --loop
```

This release was verified on macOS and Railway Linux, not an interactive Windows machine.

## Configuration

Edit `Mainstream Toolkit/web_platform/.env`, created from `.env.example` during setup. Process environment variables take precedence. The optional `Mainstream Toolkit/.env.stripe` supplies Stripe credentials/catalog IDs as a fallback; it is not needed for writing tools. Neither actual file is distributable. Keep wallet seeds and private keys out of application configuration.

Local SQLite lives at `Mainstream Toolkit/web_platform/db.sqlite3`. Source archives exclude databases and credentials. Create local accounts rather than copying production account data.

### PostgreSQL

Create an empty database and a dedicated user. Set these variables in `.env` using your own values, including a password:

```dotenv
POSTGRES_DB=observatory
POSTGRES_USER=observatory
POSTGRES_PASSWORD=
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_SSLMODE=disable
```

`disable` is for a local database without TLS; use the mode required by the production provider there. Apply migrations:

```sh
.venv/bin/python 'Mainstream Toolkit/web_platform/manage.py' migrate
```

Changing configuration does not transfer SQLite data. Back up before migrating existing data. Django tests create a separate `test_...` database; use a dedicated local database/user with permission to create it, never production credentials.

## Validation

```sh
make check
make test
```

On Windows, use `.venv/Scripts/python.exe` to run `manage.py check`, `manage.py makemigrations --check --dry-run`, and `manage.py test studio --noinput`; run `npm test` in the frontend directory. Build assets before checking the interface.

Tests mock wallet/payment operations and do not charge cards or broadcast Bitcoin transactions. PostgreSQL concurrency tests are skipped on SQLite.

## Production and Railway

Deploy the enclosing **Mainstream Toolkit** directory, not `web_platform` alone. It includes the sibling Python engines, Docker context, and service configuration.

Configure both services with:

- `DJANGO_DEBUG=0` and a unique `DJANGO_SECRET_KEY` from the hosting secret store.
- PostgreSQL credentials and the provider's required TLS mode.
- Exact `DJANGO_ALLOWED_HOSTS`, HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS`, and `PUBLIC_BASE_URL`.
- `TRUST_PROXY_HTTPS=1` only behind the trusted Railway HTTPS proxy.
- `REDIS_URL` for shared caching and throttling.

Use `railway.toml` for web and `railway.worker.toml` settings for the separate worker. Web deployment runs migrations before serving. The worker runs `sync_memberships --loop`. Gunicorn and WhiteNoise serve the app and assets; do not expose Django's development server publicly.

Payment/trading switches stay off until configured and validated. Consult the [Railway guide](Mainstream%20Toolkit/docs/RAILWAY_DEPLOYMENT.md), [payments guide](Mainstream%20Toolkit/docs/WALLET_PAYMENTS_MARKETPLACE.md), and [ordinal guide](Mainstream%20Toolkit/docs/ORDINAL_EDITIONS.md).

Back up PostgreSQL and maintain credentials separately in the hosting secret store. A source ZIP is not a database backup or disaster-recovery package.

## Updating a checkout

Save or commit local changes first, then run on the working branch:

```sh
git pull --ff-only
make setup
make check
make test
```

Setup preserves an existing `.env` and applies outstanding migrations. Review `.env.example` changes manually. Restart the local server/worker; deploy both services when application behavior changes.
