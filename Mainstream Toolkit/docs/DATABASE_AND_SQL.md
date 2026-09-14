> Current implementation update: see [Story Studio, storage and direct Bitcoin](STORY_STUDIO_AND_DIRECT_BITCOIN.md). Direct Xverse checkout no longer requires BTCPay; live payments remain disabled pending receiving-wallet setup. The platform brand is The Observatory.

# Database and SQL plan

Publishing update: migration 0002 adds AuthorProfile, PublishingMembership, ChainTip, Publication, Follow, Bookmark, PublicationReport and PaymentOrder. Profiles and memberships have unique user foreign keys; follows/bookmarks/reports enforce unique user-target pairs. Publications contain separate public prose snapshots, never automatic private analysis. PaymentOrder has a unique provider invoice ID and an applied block for idempotency. No deletion scheduler exists. Legacy AccessGrant now supplies resource limits only; private tools are free regardless of expiry.

Generate authoritative SQL using `python manage.py sqlmigrate studio 0002`. Settlement transactions lock the user and order with SELECT FOR UPDATE; PostgreSQL concurrency tests remain required. Read-only audits:

```sql
SELECT status, COUNT(*) FROM studio_paymentorder GROUP BY status;
SELECT height, observed_at FROM studio_chaintip WHERE id = 1;
SELECT user_id, expires_at_block FROM studio_publishingmembership;
```

The Django models and included migrations are the source of truth. Local execution uses SQLite. Production settings support PostgreSQL, but PostgreSQL integration and concurrency tests remain required before hosting.

## Implemented relationships

`auth_user → studio_project → studio_revision → studio_revisionnote`

`auth_user → studio_accessgrant` (at most one effective grant per user)

| Table | Purpose | Key fields / constraints |
| --- | --- | --- |
| `studio_project` | Private manuscript workspace | UUID primary key, owner FK, title, creation time |
| `studio_revision` | Saved prose and its analysis | UUID primary key, project FK, label, manuscript, SHA-256 fingerprint, profile, word count, engine version, JSON report, timestamp |
| `studio_revisionnote` | Decisions attached to a draft | Revision FK, text, timestamp |
| `studio_accessgrant` | Provider-independent pilot allowance | Unique user FK, enabled, plan code, project/word limits, optional expiry |

The revision `(project_id, created_at)` index supports revision history. Django also creates indexes for foreign keys and unique constraints. The report JSON stores scores, chapter aggregates, passage text, quotes, scoring reasons, and method provenance. On PostgreSQL, Django JSONField uses `jsonb`.

Manuscript fingerprints identify content/profile, not ownership. Identical text in different accounts remains separate. There is deliberately no unique constraint on fingerprints: two named checkpoints may contain identical text.

## SQL examples

These are PostgreSQL query examples for the implemented schema, not a replacement migration script. Bind `%(owner_id)s` and `%(project_id)s` through the database driver; never interpolate them into SQL text.

```sql
-- Author-owned project library.
SELECT id, title, created_at
FROM studio_project
WHERE owner_id = %(owner_id)s
ORDER BY created_at DESC;

-- Revision metadata, with ownership enforced through the project.
SELECT r.id, r.label, r.word_count, r.engine_version, r.created_at
FROM studio_revision AS r
JOIN studio_project AS p ON p.id = r.project_id
WHERE p.owner_id = %(owner_id)s AND p.id = %(project_id)s
ORDER BY r.created_at DESC;

-- A signal extracted from the persisted report, scoped to the owner.
SELECT r.id, r.label, (r.analysis -> 'scores' ->> 'Hope')::numeric AS hope
FROM studio_revision AS r
JOIN studio_project AS p ON p.id = r.project_id
WHERE p.owner_id = %(owner_id)s AND p.id = %(project_id)s
ORDER BY r.created_at;
```

Inspect migration SQL against the configured database:

```powershell
& .venv/Scripts/python.exe manage.py sqlmigrate studio 0001
& .venv/Scripts/python.exe manage.py migrate
```

The initial migration is generated from the actual models. Use Django migrations for schema changes, rather than running a hand-maintained duplicate DDL file. SQL above uses PostgreSQL JSON syntax; it is not a claim that these queries were exercised on SQLite.

## Transactions and ownership

Project creation locks the owner row with `select_for_update` inside a transaction before checking the project allowance. This serializes per-owner creation on PostgreSQL. SQLite does not provide equivalent row-lock behavior; concurrent quota guarantees require PostgreSQL tests.

Revision, note, comparison, and export endpoints resolve ownership server-side. A guessed UUID grants nothing. Comparisons are further restricted to the same project. Notes inherit ownership from their revision. CSRF protects form mutations; responses containing manuscripts are marked non-cacheable. There is no row-level security policy yet; application ownership filters are the current boundary.

Revisions are append-only in the UI, not enforced by a database trigger. Account deletion cascades through Django's ORM to projects/revisions/notes/grants. A public deletion/export and retention workflow remains to be implemented; do not promise immediate removal from backups.

## Next tables — design only

| Proposed table | Why it is needed |
| --- | --- |
| `chapter` / `passage_identity` | Stable references independent of content hashes |
| `revision_passage` | Passage position and text in a specific revision |
| `annotation` / `annotation_mapping` | Author-reviewed clue and note migration between drafts |
| `analysis_run` | Queued/running/completed/failed/cancelled state, revision, settings, provenance, result object key |
| `stored_asset` | Private object keys, checksums, sizes, owner/project and retention |
| `subscription` | Provider-neutral subscription state and external billing identifiers |
| `billing_event` | Unique provider/event pair for retry-safe processing |
| `usage_reservation` / `usage_event` | Atomic allowance accounting for jobs and optional semantic processing |

Use unique job idempotency keys scoped to owner and operation. Separate analysis runs from revisions before supporting multiple methods/models for the same text. Add JSON indexes only for demonstrated query patterns; do not index entire large reports by default.

## Streamlit snapshot database

`projects/observatory.sqlite3` contains a separate local-only table:

```sql
CREATE TABLE snapshots (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
```

The payload contains the selected chapters in order, profile, vocabulary, exact manuscript/settings fingerprint, clue annotations, explicit semantic results, word count, aggregate scores, and method labels. Writes use parameterized SQL and transactions; previous snapshots are retained. The path can be overridden with `OBSERVATORY_SNAPSHOT_DB` for tests or a separate local library.

`OBSERVATORY_PROJECTS_DIR` can relocate the working clue storage and default snapshot database together. Tests use a temporary directory. Reopening a snapshot restores its saved clue annotations even when the working JSON file has changed; further edits can be preserved by saving another snapshot.

This is single-user storage without account isolation. Do not mount it as a shared customer database. SQLite snapshots and the older per-fingerprint clue JSON files are not automatically imported into Django. A future importer must validate schema versions, preserve original payloads, map ownership to the signed-in author, and detect repeated imports.
