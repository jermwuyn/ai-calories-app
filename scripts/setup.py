"""Install dependencies and verified runtime assets. Never replace an existing DB silently."""
from contextlib import closing
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def verify_database(path, exact=False):
    manifest = json.loads((ROOT / 'release/database.json').read_text(encoding='utf-8'))
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('pragma integrity_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity check failed')
        if db.execute('pragma foreign_key_check').fetchall():
            raise ValueError('SQLite foreign key check failed')
        counts = {t: db.execute('select count(*) from ' + t).fetchone()[0] for t in manifest['counts']}
        if counts['nutrients'] != 21:
            raise ValueError('Expected 21 nutrient categories')
        if exact and (counts != manifest['counts'] or db.execute('select count(*) from foods where canonical_id is not null and model_class_index is not null').fetchone()[0] != manifest['model_mappings']):
            raise ValueError('Seed record counts do not match manifest')
    return counts

def restore_database(target, overwrite=False):
    target = Path(target)
    manifest = json.loads((ROOT / 'release/database.json').read_text(encoding='utf-8'))
    seed = ROOT / manifest['path']
    if digest(seed) != manifest['sha256']:
        raise ValueError('Seed checksum mismatch')
    verify_database(seed, exact=True)
    if target.exists() and not overwrite:
        return verify_database(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_name(target.name + '.before-restore.bak')
        if backup.exists():
            raise ValueError('Restore backup already exists; move it before replacing the database')
        with closing(sqlite3.connect(target)) as source, closing(sqlite3.connect(backup)) as dest:
            source.backup(dest)
    with closing(sqlite3.connect(seed)) as source, closing(sqlite3.connect(target)) as dest:
        source.backup(dest)
    return verify_database(target, exact=True)

def install_model(target, source=None):
    manifest = json.loads((ROOT / 'release/model.json').read_text(encoding='utf-8'))
    target = Path(target)
    if target.exists():
        if digest(target) != manifest['sha256']:
            raise ValueError('Existing checkpoint checksum mismatch; move it aside and rerun setup')
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent, suffix='.download')
    os.close(fd)
    try:
        if source:
            shutil.copyfile(source, temporary)
        else:
            url = os.getenv('AI_CALORIES_MODEL_URL', manifest['url'])
            if not url.startswith('https://'):
                raise ValueError('Model download URL must use HTTPS')
            with urllib.request.urlopen(url, timeout=60) as response, open(temporary, 'wb') as out:
                shutil.copyfileobj(response, out)
        if digest(temporary) != manifest['sha256']:
            raise ValueError('Downloaded checkpoint checksum mismatch')
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-install', action='store_true', help='Use already installed dependencies')
    parser.add_argument('--checkpoint-file', type=Path, help='Install a locally downloaded release asset')
    parser.add_argument('--overwrite-database', action='store_true', help='Explicitly confirm restoring the seed over an existing database; creates a backup')
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 11):
        raise ValueError('Use Python 3.11 for this release')
    for file in ['requirements.txt','release/model.json','release/database.json','backend/database/seeds/nutrition-v0.1.0.sqlite3','backend/database/profile_types.json']:
        if not (ROOT / file).is_file():
            raise FileNotFoundError('Required package file missing: ' + file)
    if not args.skip_install:
        subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT / 'requirements.txt')],check=True)
    for line in (ROOT / 'requirements.txt').read_text().splitlines():
        name, version = line.split('==')
        if importlib.metadata.version(name).split('+')[0] != version:
            raise ValueError('Dependency mismatch: run python -m pip install -r requirements.txt')
    from backend.config import DB_PATH, CHECKPOINT_PATH
    counts = restore_database(DB_PATH, args.overwrite_database)
    print('Database verified: ' + json.dumps(counts))
    install_model(CHECKPOINT_PATH, args.checkpoint_file)
    from backend.services.model_service import get_classifier
    classifier = get_classifier()
    from PIL import Image
    classifier.predict(Image.new('RGB', (224,224)), top_k=1)
    with closing(sqlite3.connect(DB_PATH)) as db:
        for canonical, index in db.execute('select canonical_id,model_class_index from foods where model_class_index is not null'):
            if not 0 <= index < len(classifier.classes) or classifier.classes[index]['canonical_id'] != canonical:
                raise ValueError('Database/model canonical mapping mismatch')
    print('Backend ready. Run: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Setup failed: ' + str(exc) + '\nSee README.md. Download the v0.1.0 release asset or use --checkpoint-file PATH.', file=sys.stderr)
        sys.exit(1)
