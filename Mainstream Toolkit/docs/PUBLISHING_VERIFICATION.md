# Publishing verification — September 13, 2026

- Django: 21 tests passed using isolated SQLite test data. Covers private ownership, escaped prose, public visibility, preview-before-publish, free account access, block boundaries, redemption pricing, owner-only withdrawal and mocked invoice settlement/idempotency.
- Django system check: no issues. Migration drift check: no changes detected. Migration 0002 applied locally.
- Static collection completed with manifest/compression.
- Bitcoin mainnet tip successfully fetched through Esplora. Local block worker refreshes the clock; it never deletes accounts.
- No real payment was attempted. Live BTCPay credentials are not configured. Wallet compatibility, PostgreSQL concurrency, Docker execution and Railway deployment remain unverified.
- No browser visual QA was performed for this publishing increment. Responsive styles are implemented; review actual device layouts before public launch.

Run `python manage.py collectstatic --noinput`, `python manage.py test studio`, `python manage.py check` and `python manage.py makemigrations --check --dry-run` from web_platform to repeat local verification.
