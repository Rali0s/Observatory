# Credentials and private data

This repository is public. Keep deployment credentials in Railway's environment settings or another secret store. Use ignored local `.env` files for development.

## Excluded files

`.gitignore` excludes environment files, API key/credential files, private-key formats, service-account JSON, token files, credential directories, database dumps, SQLite databases, logs, backups, raw `Res/` originals, dependencies, and generated archives. Only the sanitized `.env.example` is included. API integration source remains part of the application.

Use recognizable credential filenames such as `.env.stripe`, `api_keys.json`, `credentials.json`, or `service-account-local.json`. Arbitrarily named files can still contain secrets; naming rules do not inspect contents. Never store wallet seeds/private keys here.

Ignore rules do not remove files already tracked by Git. Before publishing:

```sh
git status --short
git ls-files -ci --exclude-standard
git diff --cached --stat
```

The second command should return no tracked files matched by ignore rules. Review staged changes locally without posting credential values in issues or chat.

## Secret scanning

With Gitleaks installed:

```sh
gitleaks git . --log-opts='--all' --redact
gitleaks git . --staged --redact
```

`.gitleaks.toml` extends standard rules. Its narrow exception permits two exact disposable test passwords in two named test files; it does not exclude whole test directories. Keep reports under ignored `tmp/` and use redaction. A clean scan reduces risk but cannot prove every possible secret is absent.

## If a credential is committed

Revoke or rotate it with the provider first. Deleting the file or adding an ignore rule does not erase history or invalidate a credential. Coordinate history cleanup with collaborators; do not force-push an unreviewed rewrite. Report exposures privately to the repository owner without posting live credentials in public issues.

Wallet addresses and product IDs are public identifiers, not signing secrets. Their inclusion in a template does not activate payments.
