"""Simulate an uncommitted fresh clone using only Git-visible files and a release asset."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    files = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    with tempfile.TemporaryDirectory(prefix='ai-calories-clean-') as directory:
        base = Path(directory)
        clone = base / 'clone'
        clone.mkdir()
        for name in files:
            if not name or not (ROOT/name).is_file():
                continue
            target = clone/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,target)
        assert not (clone/'backend/database/nutrition.db').exists()
        assert not (clone/'checkpoints/best.pth').exists()
        asset = base/'best.pth'
        shutil.copy2(ROOT/'checkpoints/best.pth',asset)
        env = {k:v for k,v in os.environ.items() if not k.startswith('AI_CALORIES_') and k not in ['PYTHONPATH','FDC_API_KEY']}
        env['PYTHONIOENCODING']='utf-8'
        def run(*args):
            subprocess.run([sys.executable,*args],cwd=clone,env=env,check=True)
        missing = subprocess.run([sys.executable, 'scripts/setup.py', '--skip-install', '--checkpoint-file', str(base/'missing.pth')], cwd=clone, env=env, capture_output=True, text=True)
        assert missing.returncode != 0 and 'Setup failed' in missing.stderr
        assert not (clone/'checkpoints/best.pth').exists()
        run('scripts/setup.py','--skip-install','--checkpoint-file',str(asset))
        db=clone/'backend/database/nutrition.db'
        before=hashlib.sha256(db.read_bytes()).hexdigest()
        run('scripts/setup.py','--skip-install')
        assert hashlib.sha256(db.read_bytes()).hexdigest()==before
        run('-m','unittest','discover','-s','tests','-v')
        print('Fresh-copy setup, idempotence and tests passed without original database/model repository.')
        print('Uses the current interpreter dependencies and a local release asset; does not prove a fresh pip install or public asset availability.')

if __name__ == '__main__': main()
