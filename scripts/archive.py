#!/usr/bin/env python3
"""Package committed source only. No databases, credentials, or Git history."""
import hashlib
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def main():
    if git('status', '--porcelain', '--untracked-files=no'):
        raise SystemExit('Commit tracked changes before creating an archive.')
    if git('ls-files', '-ci', '--exclude-standard'):
        raise SystemExit('Tracked files match ignore rules. Review before archiving.')
    commit = git('rev-parse', '--short=12', 'HEAD')
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    name = f'observatory-{commit}'
    target = output / f'{name}.zip'
    subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=zip',
                    f'--prefix={name}/', f'--output={target}', 'HEAD'], check=True)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():
            raise SystemExit('Archive integrity check failed.')
        names = {n.removeprefix(name + '/') for n in archive.namelist()}
        required = {'README.md', 'INSTALL.md', '.gitignore', 'Makefile',
                    'Mainstream Toolkit/narrative_engine.py',
                    'Mainstream Toolkit/web_platform/manage.py',
                    'Mainstream Toolkit/web_platform/.env.example',
                    'Mainstream Toolkit/web_platform/frontend/package-lock.json'}
        if not required <= names:
            raise SystemExit('Archive is missing required installation files.')
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    checksum_file = target.with_suffix('.zip.sha256')
    checksum_file.write_text(f'{checksum}  {target.name}\n', encoding='utf-8')
    print(target)
    print(checksum_file)


if __name__ == '__main__':
    main()
