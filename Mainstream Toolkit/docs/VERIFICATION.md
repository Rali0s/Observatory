# Verification — September 13, 2026

## Automated checks completed

- Mainstream Toolkit: `python -m unittest discover -s tests -v` — **29 tests passed**.
- Django: `manage.py test studio` — **10 tests passed** against an isolated SQLite test database.
- Django: `manage.py check` — no issues.
- Django: `manage.py makemigrations --check --dry-run` — no model/migration drift.
- Initial migrations applied successfully to the new local development database.

The expanded tests cover local snapshot persistence across a fresh Streamlit session, Unicode snapshot round-trips and demo headings, comparison dimensions, retained Django revisions, imports, notes, exports, CSRF, account isolation, expiry and access allowances, invalid/foreign comparison identifiers, and parity with the existing Python engine. Tests make no paid API calls.

## Browser checks completed

Used local loopback previews and an agent-created temporary pilot account with invented sample prose. Verified sign-in, manuscript project creation, save-and-analyze, visible signal estimates, expandable passage evidence, saved revision decisions, and sign-out. Inspected the rendered login and report pages and the updated Streamlit Observatory/Revision studio. The temporary account and its sample project were removed after verification.

## Not yet verified

- PostgreSQL execution, row locks, and concurrent quota enforcement.
- Full-length novel throughput, worker queues, retry/cancellation behavior.
- Production HTTPS, static serving, login throttling, account recovery, deployment, backups/restoration.
- Mobile device testing, complete keyboard/screen-reader audit.
- Accuracy calibration against editor-reviewed manuscripts.
- Billing and Stripe: deliberately not implemented.

The successful checks establish a local development baseline; they do not establish production readiness.
