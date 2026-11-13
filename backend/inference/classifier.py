"""Single-dish inference using the taxonomy embedded in a trusted checkpoint."""
from pathlib import Path

from PIL import Image, ImageOps
import torch

from torchvision.models import EfficientNet_B0_Weights
from backend.inference.model import build_model


def validate_mapping(mapping):
    classes = mapping['classes']
    if (not classes or mapping['class_count'] != len(classes)
            or mapping['index_base'] != 0
            or [c['index'] for c in classes] != list(range(len(classes)))):
        raise ValueError('Invalid checkpoint class indices')
    ids = [c['canonical_id'] for c in classes]
    if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('Canonical IDs must be unique nonempty strings')
    return classes


class FoodClassifier:
    """Load only trusted local trainer checkpoints (these contain pickle objects)."""

    def __init__(self, checkpoint, device='auto'):
        self.checkpoint = Path(checkpoint).resolve()
        self.device = torch.device(('cuda' if torch.cuda.is_available() else 'cpu')
                                   if device == 'auto' else device)
        ck = torch.load(self.checkpoint, map_location='cpu', weights_only=False)
        self.mapping = ck['dataset']['class_map']
        self.classes = validate_mapping(self.mapping)
        self.model = build_model(ck['config']['architecture'], len(self.classes), pretrained=False)
        self.model.load_state_dict(ck['model'], strict=True)
        self.model.to(self.device).eval()
        self.transform = EfficientNet_B0_Weights.DEFAULT.transforms()

    @torch.inference_mode()
    def predict(self, image, top_k=3):
        if type(top_k) is not int or not 1 <= top_k <= len(self.classes):
            raise ValueError('top_k must be between 1 and the class count')
        if isinstance(image, Image.Image):
            rgb = ImageOps.exif_transpose(image).convert('RGB')
        else:
            with Image.open(image) as opened:
                rgb = ImageOps.exif_transpose(opened).convert('RGB')
        logits = self.model(self.transform(rgb).unsqueeze(0).to(self.device))
        if logits.shape != (1, len(self.classes)) or not torch.isfinite(logits).all():
            raise ValueError('Invalid model output')
        scores, indices = logits.softmax(dim=1)[0].topk(top_k)
        predictions = []
        for score, index in zip(scores.cpu().tolist(), indices.cpu().tolist()):
            cls = self.classes[index]
            predictions.append({'model_index': index, 'canonical_id': cls['canonical_id'],
                                'name_vi': cls.get('name_vi'), 'name_en': cls.get('name_en'),
                                'display_name': cls.get('name_vi') or cls.get('name_en') or cls['source_name'],
                                'score': score})
        return {'taxonomy_version': self.mapping.get('version'),
                'predictions': predictions, 'requires_confirmation': True,
                'score_type': 'uncalibrated_softmax',
                'nutrition_status': 'requires_confirmed_food_profile_and_portion'}
