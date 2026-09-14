> Current implementation update: see [Story Studio, storage and direct Bitcoin](STORY_STUDIO_AND_DIRECT_BITCOIN.md). Direct Xverse checkout no longer requires BTCPay; live payments remain disabled pending receiving-wallet setup. The platform brand is The Observatory.

# The Observatory: production platform plan

Status: updated September 13, 2026. Free signup, Reading Room, profiles and block memberships are implemented. Optional BTCPay code is present, but live checkout remains disabled until configured. Historical pilot-access and no-payment descriptions below are superseded by [membership policy](MEMBERSHIP_POLICY.md) and [Railway deployment](RAILWAY_DEPLOYMENT.md). Free tools stay open; redemption is $27 plus $18 membership. No accounts or manuscripts are deleted.

## Product direction

Novel Tools offers a private revision workspace: inspect narrative movement, read exact supporting passages, record decisions, and return with a new draft. The Observatory is the analytical entry point. The Manuscript Workbench remains the editing/export companion during migration.

Brand: warm parchment `#F4EEDF`, ivory `#FFFCF5`, forest green `#254D3C`, pale sage `#E3E9DC`, charcoal `#252B25`. Serif headings and manuscript text; sans-serif controls; visible focus states; labeled chart values; responsive layouts. Do not use green/red changes to imply that an emotional rise or fall improves literary quality.

## Implemented now

| Area | Streamlit | Django alpha |
| --- | --- | --- |
| Brand | Beige/green theme, revised Observatory introduction | Shared visual direction, responsive templates |
| Analysis | Existing interactive timelines and passage evidence | Reuses the same Python engine, stores report with revision |
| Saving | Explicit local SQLite snapshots including optional semantic results | Account-owned projects and append-only revision creation |
| Comparison | Snapshot aggregate and word-count differences | Same-project aggregate differences, profile/version warning |
| Notes | Existing clue annotations / workbench | Revision decisions stored in SQL |
| Export | Existing JSON/CSV/PDF/EPUB tools | Private manuscript/evidence/notes JSON |
| Accounts | None; local single-user tool | Django login, administrator-created pilot users |
| Access | No hosted account boundary | Active/expired grants, project and word allowances |
| Payments | None | None; provider-neutral access module |

## Architecture

Browser → Django templates and views → owner-scoped services → PostgreSQL.

The analysis service calls the existing pure Python narrative engine. For the alpha, it returns synchronously. Production adds a durable task queue and Python worker so large manuscripts, semantic requests, and publishing exports do not occupy web requests. Private object storage will hold uploaded originals, art, large evidence reports, and generated exports; SQL holds identities, relationships, revisions, job state, and metadata.

Do not rewrite the analysis in JavaScript. First turn the existing engine into a versioned Python package used by both interfaces. The current Django adapter loads the existing source file directly and prevents code duplication during this transition.

### Technology choices

- Django 5.2 LTS family for authentication, forms, CSRF, ORM, migrations, and staff administration. Apply patch updates and lock reviewed deployment dependencies.
- PostgreSQL for production; SQLite only for local development and Streamlit's single-user snapshot store.
- Django-rendered pages with progressive enhancement. Add richer timeline/editor JavaScript after the storage and authorization contract is stable.
- Production application server behind an HTTPS proxy; static-file hosting; managed PostgreSQL; private object storage; a durable queue and separate worker. Specific providers remain undecided.

## Migration sequence and acceptance gates

### 1. Local foundation — started in this change

Run both interfaces. Verify private projects, saved analysis, evidence, comparisons, notes, and export. Existing core calculations must match between interfaces. Do not claim production readiness from local unit tests.

### 2. Reliable revision workflow

Add stable chapter/passage identities separate from content hashes. Store an explicit parent revision. Diff revisions and offer an author-reviewed mapping for moved/edited passages; preserve ambiguous clues as unmapped, never silently attach them to different prose. Add Streamlit snapshot import with schema validation and duplicate detection. Add DOCX import and round-trip checks for chapter breaks, poetry, Unicode, and scene separators. Preserve original uploads.

Acceptance: an author can revise/reorder a book without losing notes; prior drafts remain recoverable; failed imports leave existing projects untouched; all export/download paths enforce ownership.

### 3. Full manuscript jobs and analysis quality

Introduce AnalysisRun records, idempotent job submission, progress, retries, cancellation, and per-user concurrency limits. The request should return a job ID. Workers verify project ownership and the allowed operation again, operate on a fixed revision, and commit results atomically. Keep the 20,000-word synchronous ceiling until this is verified.

Persist method, engine/model version, input fingerprint, settings, supporting quotes, and failure category. Distinguish offline and semantic scores in UI and exports. Validate semantic numeric ranges and quote substrings, while stating that quote validation does not prove the interpretation is correct.

Evaluate against consented manuscripts and editor-reviewed passages. Include implicit emotion, negation, metaphor, multilingual limitations, narrative distance, and genre differences. Measure reviewer usefulness and false positives, not merely successful API responses. Current lexical scores are not calibrated literary measurements.

Acceptance: benchmark representative 80k–150k-word books, bound memory and latency, ensure duplicate retries do not create duplicate runs or usage charges, and test cancellation/failure recovery.

### 4. Private hosted pilot

Add invitation acceptance, verified email, password recovery, login throttling, CSRF tests, private storage authorization, request/job size limits, observability without manuscript text, deletion workflows, and support tooling. Run PostgreSQL tests and concurrent quota/job tests. Configure HTTPS and static files; review deployment checks and dependency locks.

Establish automated database/object backups and test restores. Define retention and deletion windows, including backups. Record explicit consent before any external semantic processing, including surrounding context sent. Hosting an offline engine still puts manuscripts on our server; never call that on-device processing.

Acceptance: two-account isolation tests cover every endpoint, signed downloads, jobs, exports, and caches; restart/redeploy retains drafts; restore succeeds; no secrets or manuscript text appear in logs; keyboard/mobile workflows are usable.

### 5. Billing adapter — planned, not implemented

Keep `studio/access.py` as the capability boundary. Views should ask whether an account can create a project or run analysis, never inspect a Stripe field. Current Access Grants are manually administered pilot capabilities.

A later billing adapter maps verified provider events to a local subscription record and an effective grant. Store provider identifiers separately; normalize active/trial/grace/expired states; make event processing idempotent with a unique provider/event ID; account for out-of-order events and reconciliation. Never grant access from a checkout redirect alone.

Add atomic usage reservations and a ledger before metered AI. Reserve allowance before dispatch, finalize actual use on completion, release appropriately on failure, and prevent duplicate billing on retries. Version the pricing/allowance policy used for each reservation.

Reading and exporting existing work should remain available after expiry. Blocking a new analysis should not trap a writer's manuscript. Project/word limits exist now; monthly usage, payment status, taxes, refunds, checkout, webhooks, and credit balances do not.

## Deployment configuration

Production requires `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, exact `DJANGO_ALLOWED_HOSTS`, HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS`, and the PostgreSQL variables documented in `web_platform/README.md`. Local HTTP is only for loopback development. Configure trusted proxy HTTPS headers only after the proxy is set to strip and replace incoming forwarding headers.

Run migrations as a release task, collect static files, then start web and worker processes with restricted credentials. Keep the engine in the deploy artifact. Run `manage.py check --deploy` against the actual production configuration. Database switches do not copy data; any SQLite migration needs explicit export/import and verification.

## Outstanding decisions

- Hosting region and provider, storage/backup retention, pilot user count.
- First supported manuscript length after worker benchmarking.
- Whether richer editing belongs in the first hosted pilot or follows analysis validation.
- Pilot pricing experiments after observing processing cost and revision reuse.

## References

- [Django authentication](https://docs.djangoproject.com/en/5.2/topics/auth/default/)
- [Django database support](https://docs.djangoproject.com/en/5.2/ref/databases/)
- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [Streamlit theming](https://docs.streamlit.io/develop/concepts/configuration/theming)
- [Stripe subscription events — future adapter only](https://docs.stripe.com/billing/subscriptions/webhooks)
