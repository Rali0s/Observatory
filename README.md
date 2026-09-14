# The Observatory

![The Observatory](Mainstream%20Toolkit/web_platform/static/observatory-logo.png)

**A writing studio, reading community, and publishing platform from Premise LLC.**

The Observatory combines private manuscript revision, narrative analysis, public author profiles, and optional Bitcoin ordinal editions. Writing tools are free; publishing access is managed through memberships, invitations, or administrator access.

[Live site](https://observate.up.railway.app/) · [Installation](INSTALL.md) · [Security](SECURITY.md) · [Source archives](ARCHIVING.md)

## Features

| Area | Included |
| --- | --- |
| Writing studio | Saved revisions, chapter workbench, Visual/Markdown editing, story boards, notes, and EPUB/PDF/Markdown exports |
| Narrative analysis | Offline passage evidence, chapter/scene timelines, draft comparisons, character and clue tools |
| Creepypasta | Private 0–5 darkness estimates, with unease, dread, uncanny, psychological, and visceral horror dimensions |
| Reading community | Public profiles, channel/hashtag discovery, follows, bookmarks, votes, reporting, and social sharing |
| Accounts | Password and Xverse sign-in, verified wallet linking, and account merging with proof of both accounts |
| Invitations | Three-month/lifetime passes, campaign management, redemption history, limits, and deadlines |
| Ordinal editions | Guided metadata, frozen previews, regular Xverse minting, rare-sat discovery, and miner-fee estimates |
| Mobile | Focused reading, account access, and invite redemption; writing and management use the desktop interface |

## Quick start

Requires **Python 3.12**, **Node.js 22**, npm, and GNU Make on macOS/Linux. See [INSTALL.md](INSTALL.md) for Windows and PostgreSQL.

Current application work is published on `feature/wallet-payments-discovery`:

```sh
git clone --branch feature/wallet-payments-discovery https://github.com/Rali0s/Observatory.git
cd Observatory
make setup
.venv/bin/python 'Mainstream Toolkit/web_platform/manage.py' createsuperuser
make run
```

Open [localhost:8000](http://127.0.0.1:8000). In a second terminal, run `make worker` for block verification and reconciliation.

Setup creates a virtual environment, installs Python dependencies and the npm lockfile, builds browser assets, creates `.env` from the sanitized example if absent, and applies SQLite migrations. Keep the entire `Mainstream Toolkit` directory together: Django imports its sibling analysis and publishing engines.

## Development commands

| Command | Purpose |
| --- | --- |
| `make setup` | Install dependencies, build assets, initialize the database |
| `make run` | Start the local development server |
| `make worker` | Run Bitcoin clock and integration reconciliation |
| `make build` | Build browser bundles and collect static assets |
| `make check` | Check Django configuration and migration consistency |
| `make test` | Build assets and run backend/frontend tests |
| `make archive` | Create a committed-source ZIP and SHA-256 checksum |

The last application verification passed **145 PostgreSQL tests and 19 frontend tests**. SQLite skips five PostgreSQL-specific concurrency tests. See the [deployment log](Mainstream%20Toolkit/docs/RAILWAY_DEPLOYMENT.md) for release evidence.

## Architecture

```text
Mainstream Toolkit/
├── narrative_engine.py       # Offline narrative signals
├── analysis_engine.py        # Chapter analysis
├── semantic_engine.py        # Optional external AI interpretation
├── publisher.py              # Book exports
├── docs/                     # Feature and deployment guides
└── web_platform/
    ├── observatory/          # Django configuration
    ├── studio/               # Models, services, views, migrations, tests
    ├── templates/            # Server-rendered interface
    ├── frontend/             # Browser source and npm lockfile
    ├── static/               # Distributed assets and built bundles
    └── .env.example          # Sanitized configuration template
```

Local development uses SQLite. Production uses PostgreSQL, Gunicorn, WhiteNoise, a separate worker, and optionally Redis for shared caching/throttling. Railway configuration is included.

## Integration status

- Card payments, direct Bitcoin membership payments, and native ordinal trading default to **disabled**. Credentials alone do not activate them.
- Stripe is for publishing membership fees. The implemented one-time, block-based membership flow still needs a billing-policy decision before using the supplied recurring Writer price. See the [payment guide](Mainstream%20Toolkit/docs/WALLET_PAYMENTS_MARKETPLACE.md).
- Regular inscriptions use Xverse. Exact-sat inscriptions complete through Gamma after sat selection in Observatory. Platform fees are **0 sats for launch**; miner estimates exclude provider charges, and the wallet presents the final amount.
- Native trading code requires operator configuration and live-wallet validation before activation. Automated tests do not prove real-world settlement.
- Offline analysis sends no writing to external AI services. Optional AI interpretation requires configuration and explicit passage-sharing consent. Darkness scores are editorial estimates, not quality or age ratings.

## Documentation

- [Installation and production setup](INSTALL.md)
- [Writing editor](Mainstream%20Toolkit/docs/WRITING_EDITOR.md) and [Story Studio](Mainstream%20Toolkit/docs/STORY_STUDIO_AND_DIRECT_BITCOIN.md)
- [Creepypasta darkness](Mainstream%20Toolkit/docs/CREEPYPASTA_DARKNESS.md)
- [Invite management and sharing](Mainstream%20Toolkit/docs/INVITES_AND_SHARING.md)
- [Account merging](Mainstream%20Toolkit/docs/ACCOUNT_MERGING.md)
- [Ordinal editions and fees](Mainstream%20Toolkit/docs/ORDINAL_EDITIONS.md)
- [Mobile reading](Mainstream%20Toolkit/docs/MOBILE_READING.md)
- [Railway deployment](Mainstream%20Toolkit/docs/RAILWAY_DEPLOYMENT.md)

## Project status and ownership

This is an actively developed application. Synchronous analysis is normally limited to 20,000 words per revision. Historical milestone documents describe the state at their release date; use the current installation guide for setup.

**A Premise LLC Venture © 2026-2027.** Licensing terms have not yet been published in this repository.
