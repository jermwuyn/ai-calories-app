"""Self-contained inference with a verified, trusted release checkpoint."""
import hashlib
import json
from functools import lru_cache
from backend.config import CHECKPOINT_PATH, ROOT

@lru_cache(maxsize=1)
def get_classifier():
    if not CHECKPOINT_PATH.is_file():
        raise FileNotFoundError('Model checkpoint missing. Run python scripts/setup.py (see README.md).')
    manifest = json.loads((ROOT / 'release/model.json').read_text(encoding='utf-8'))
    with CHECKPOINT_PATH.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != manifest['sha256']:
        raise RuntimeError('Model checksum mismatch. Install the trusted v0.1.0 checkpoint using scripts/setup.py.')
    from backend.inference.classifier import FoodClassifier
    classifier = FoodClassifier(CHECKPOINT_PATH, device='cpu')
    if len(classifier.classes) != manifest['class_count'] or classifier.mapping.get('version') != manifest['taxonomy']:
        raise RuntimeError('Unexpected model taxonomy')
    return classifier

def predict_food(image, top_k=3):
    return get_classifier().predict(image=image, top_k=top_k)
