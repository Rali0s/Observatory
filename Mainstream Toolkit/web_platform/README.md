> New: [Story Studio, restored writing tools, storage quota and direct Xverse payments](../docs/STORY_STUDIO_AND_DIRECT_BITCOIN.md). This update supersedes earlier feature boundaries below.

# The Observatory — Django foundation

A runnable local alpha with a public Reading Room, chronological feed, free signup, author profiles, follows, bookmarks, reporting, private manuscript analysis, and block-based publishing memberships. Publishing costs $18 per 4,320 blocks; redemption costs $27 plus $18 membership. Optional BTCPay invoice integration is implemented but disabled until configured. No Stripe SDK or direct wallet signing is included.

The existing Streamlit Observatory continues to run separately. This application reuses `../narrative_engine.py`; keep the enclosing Mainstream Toolkit folder when moving it.

## Run on Windows

Open PowerShell in this `web_platform` directory:

```powershell
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -r requirements.txt
& .venv/Scripts/python.exe manage.py migrate
& .venv/Scripts/python.exe manage.py createsuperuser
& .venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000. Sign in, create a manuscript project, then paste or import UTF-8 `.md`, `.markdown`, or `.txt` text. Save a revision to run the offline analysis. Select a signal, expand passage evidence, save a revision decision, or compare another revision in the same project.

Authors can register free at `/join/`. Private projects, analysis, notes and exports remain free regardless of publishing membership. Legacy Access Grant rows only supply resource limits. Public posting requires a verified active publishing term. Accounts and manuscripts are never deleted by membership expiry.

The development database is `db.sqlite3`. It is ignored by Git. Back it up while the application is stopped. Do not commit manuscripts or credentials.

## Verify

```powershell
& .venv/Scripts/python.exe manage.py check
& .venv/Scripts/python.exe manage.py collectstatic --noinput
& .venv/Scripts/python.exe manage.py test studio
& .venv/Scripts/python.exe manage.py makemigrations --check --dry-run
```

The tests cover account isolation on reads and writes, foreign-project comparison rejection, CSRF, expiry, quota boundaries, UTF-8 import, escaped manuscript HTML, retained revisions, notes, export, and reuse of the existing analysis engine. Tests run without remote AI calls.

## PostgreSQL configuration

Set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and optionally `POSTGRES_PORT` (default 5432) and `POSTGRES_SSLMODE` (default `require`). Then run migrations against an empty, dedicated database. Changing these variables does not migrate existing SQLite data automatically.

For production, also set `DJANGO_DEBUG=0`, a strong unique `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS`. Settings refuse production mode without a secret or PostgreSQL. Environment variables are read directly; no `.env` loader is installed in this application.

These settings are only a foundation. Follow [the production plan](../docs/PRODUCTION_PLAN.md) before exposing this service publicly. In particular: use a production application server, HTTPS, a configured static-file service, login throttling, account recovery, backup/restore tests, and PostgreSQL integration tests. Do not expose Django's development server.

## Current boundaries

- Analysis runs synchronously and is capped at 20,000 input words per revision, or a smaller account allowance. This is not yet a full-length novel service.
- Revisions are append-only through the web UI. SQL administrators can still change them; database immutability triggers are not implemented.
- Stored reports include all passage evidence; large-manuscript pagination and background jobs remain planned.
- The Django workspace currently supports the two profiles, chapter signal bars, saved manuscript reports, and notes. Streamlit still has the richer interactive timelines, character/clue tools, semantic pass, and publishing workbench.
- Streamlit snapshots and Django projects use separate databases. Automatic import, stable passage IDs, and clue migration across revisions are not implemented.
- Access Grants are provider-neutral permissions, not subscription records. Only the administrator can change them. There is no billing provider and no payment collection.
- No DOCX import, email delivery, deletion UI, team sharing, or self-service signup yet.

See [the schema and SQL plan](../docs/DATABASE_AND_SQL.md) for the implemented tables and planned changes.

## Publishing and deployment

Run `python manage.py sync_memberships --loop` in a separate worker to keep the confirmed block clock fresh. Checkout remains disabled without BTCPay configuration. See [membership policy](../docs/MEMBERSHIP_POLICY.md), [Railway deployment](../docs/RAILWAY_DEPLOYMENT.md), and [brand guide](../docs/BRAND_GUIDE.md). Deployment, real wallet compatibility, live settlement and PostgreSQL concurrency have not yet been verified.
