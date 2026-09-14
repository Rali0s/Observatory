# Source archives

Run from a clean, committed checkout:

```sh
make archive
```

Without Make, run `python3.12 scripts/archive.py`; on Windows use `py -3.12 scripts/archive.py`. Output:

```text
dist/observatory-<commit>.zip
dist/observatory-<commit>.zip.sha256
```

The ZIP contains committed HEAD source, installation guides, migrations, tests, assets, frontend sources/lockfile, and the sanitized `.env.example`. It excludes Git history, untracked/ignored files, databases, credentials, raw supplied assets, and installed dependencies. `.gitattributes` adds export exclusions.

The script rejects tracked edits or tracked files matched by ignore rules, verifies ZIP integrity, and checks required installation files. Commit new files first: untracked source is deliberately not packaged. Follow [SECURITY.md](SECURITY.md) before sharing; the script does not run a secret scanner itself.

From `dist`, verify the checksum:

```sh
shasum -a 256 -c observatory-<commit>.zip.sha256
```

On Windows, compare `Get-FileHash -Algorithm SHA256` with the checksum file. Extract and follow INSTALL.md, skipping the clone command. Install dependencies afresh. Generated ZIPs/checksums stay local in ignored `dist/` and are not committed. A source archive is not a backup of application data.
