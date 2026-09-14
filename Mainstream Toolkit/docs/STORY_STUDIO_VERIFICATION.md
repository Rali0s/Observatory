# Story Studio verification

- 35 Django tests passed against isolated SQLite test data: existing account isolation, publishing gates and payments; new story-board validation/stale writes, owner-scoped routes, storage rollback, chapter editing/import, Markdown safety, clue annotations, explicit cleanup, PDF/EPUB/Markdown output, chapter image validation/privacy, AI consent and mocked direct-payment boundaries.
- 3 Node wallet-flow tests passed: mainnet/exact sats, cancelled connection and expired quote. These mock the wallet request function; they do not prove actual extension or mobile-wallet compatibility.
- Wallet bundle built with pinned @sats-connect/core 0.17.6 and axios override 1.20.0. npm audit reports zero known vulnerabilities.
- JavaScript syntax checks passed for board, chart and wallet bundle. Static collection completed; Django reported no migration drift.
- Migration 0003 applied to the local development database. Django and the membership worker restarted with the new code.
- Local HTTP smoke checks passed for public landing page, protected-route login redirects, new JavaScript assets and database health endpoint. No authenticated production browser visual QA was performed.

No live Bitcoin transaction, external AI request, Railway deployment, PostgreSQL concurrency test or backup restore was executed. Receiving-wallet configuration is still required. See the deployment and direct-Bitcoin guide for remaining operational gates.

Repeat from web_platform: `python manage.py collectstatic --noinput`, `python manage.py test studio`, `node --test frontend/wallet.test.cjs`, `python manage.py makemigrations --check --dry-run`.
