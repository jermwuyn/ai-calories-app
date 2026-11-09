
import os
import sys
from pathlib import Path
from functools import lru_cache


# Both repositories are located in D:\Code
CODE_DIR = Path(__file__).resolve().parents[3]

MODEL_REPO = Path(
    os.environ.get(
        "AI_CALORIES_MODEL_REPO",
        str(CODE_DIR / "ai-calories-model"),
    )
).resolve()

CHECKPOINT_PATH = (
    MODEL_REPO
    / "runs"
    / "exp-001-unified4-v2"
    / "best.pth"
)


@lru_cache(maxsize=1)
def get_classifier():
    """
    Load the trained classifier and cache the instance.

    Only use our own trusted checkpoint.
    """

    if not CHECKPOINT_PATH.is_file():
        raise FileNotFoundError(
            f"Model checkpoint not found: {CHECKPOINT_PATH}"
        )

    if not (MODEL_REPO / "classification").is_dir():
        raise FileNotFoundError(
            f"Model source code not found: {MODEL_REPO}"
        )

    # Import the existing model implementation.
    model_repo_str = str(MODEL_REPO)

    if model_repo_str not in sys.path:
        sys.path.insert(0, model_repo_str)

    from classification.inference import FoodClassifier

    classifier = FoodClassifier(
        checkpoint=CHECKPOINT_PATH,
        device="cpu",
    )

    return classifier


def predict_food(image, top_k=3):
    """Predict food classes from an image."""

    classifier = get_classifier()

    return classifier.predict(
        image=image,
        top_k=top_k,
    )
