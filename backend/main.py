
import sqlite3
from pathlib import Path
from contextlib import closing

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.services.recipe_service import get_recipe
from backend.services.recipe_service import calculate_recipe_custom
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from fastapi import File, UploadFile, Query

from backend.services.model_service import predict_food

DB_PATH = (
    Path(__file__).resolve().parent
    / "database"
    / "nutrition.db"
)

app = FastAPI(
    title="AI Calories API",
    description="Food recognition and nutrition analysis",
    version="0.1.0",
)


class IngredientResponse(BaseModel):
    id: int
    name_vi: str
    name_en: str | None
    preparation_state: str


@app.get("/")
def root():
    return {
        "app": "AI Calories",
        "status": "running",
    }


@app.get(
    "/ingredients",
    response_model=list[IngredientResponse],
)
def get_ingredients():

    if not DB_PATH.is_file():
        raise HTTPException(
            status_code=500,
            detail="Nutrition database not found",
        )

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                id,
                name_vi,
                name_en,
                preparation_state
            FROM ingredients
            ORDER BY id
            """
        ).fetchall()

    return [dict(row) for row in rows]

@app.get("/recipes/{recipe_id}")
def get_recipe_endpoint(recipe_id: int):

    if recipe_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Recipe ID must be positive",
        )

    try:
        recipe = get_recipe(recipe_id, db_path=DB_PATH)
        return recipe

    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Recipe {recipe_id} not found",
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Nutrition database not found",
        )

class IngredientPortion(BaseModel):
    ingredient_id: int = Field(gt=0, strict=True)
    grams: float = Field(gt=0, allow_inf_nan=False)


class CalculateRecipeRequest(BaseModel):
    components: list[IngredientPortion] = Field(min_length=1)


@app.post("/recipes/{recipe_id}/calculate")
def calculate_recipe_endpoint(
    recipe_id: int,
    request: CalculateRecipeRequest,
):
    if recipe_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Recipe ID must be positive",
        )

    try:
        get_recipe(recipe_id, db_path=DB_PATH)

    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Recipe {recipe_id} not found",
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Nutrition database not found",
        )

    components = [
        item.model_dump()
        for item in request.components
    ]

    try:
        return calculate_recipe_custom(
            recipe_id=recipe_id,
            components=components,
            db_path=DB_PATH,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

# Maximum upload: 10 MB
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Maximum image resolution: 20 megapixels
MAX_IMAGE_PIXELS = 20_000_000

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


@app.post("/predict")
def predict_food_endpoint(
    file: UploadFile = File(...),
    top_k: int = Query(default=3, ge=1, le=5),
):
    """
    Recognize food from an uploaded image.

    Returns Top-K predictions from EfficientNet-B0.

    Does not estimate portion weight or nutrition.
    """

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Only JPEG, PNG and WEBP images are supported",
        )

    try:
        image_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded image is empty",
            )

        if len(image_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds the 10 MB limit",
            )

        try:
            with Image.open(BytesIO(image_bytes)) as image:

                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise HTTPException(
                        status_code=415,
                        detail="Unsupported image format",
                    )

                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(
                        status_code=413,
                        detail="Image resolution exceeds 20 megapixels",
                    )

                # Decode and validate image before inference.
                image.load()

                result = predict_food(
                    image=image,
                    top_k=top_k,
                )

        except (
            UnidentifiedImageError,
            OSError,
            Image.DecompressionBombError,
        ) as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid or corrupted image",
            ) from exc

        return result

    finally:
        file.file.close()


@app.get("/foods/by-canonical/{canonical_id}")
def get_food_by_canonical_id(canonical_id: str):
    """
    Map model canonical ID to food and recipe candidates.

    Does not automatically calculate nutrition.
    """

    if not DB_PATH.is_file():
        raise HTTPException(
            status_code=500,
            detail="Nutrition database not found",
        )

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row

        food = conn.execute(
            """
            SELECT
                id,
                canonical_id,
                model_class_index,
                name_vi,
                name_en
            FROM foods
            WHERE canonical_id = ?
            """,
            (canonical_id,),
        ).fetchone()

        if food is None:
            return {
                "canonical_id": canonical_id,
                "mapped": False,
                "food": None,
                "recipes": [],
                "nutrition_status": "nutrition_unavailable",
            }

        recipes = conn.execute(
            """
            SELECT
                id,
                name,
                default_serving_g
            FROM recipes
            WHERE food_id = ?
            ORDER BY id
            """,
            (food["id"],),
        ).fetchall()

        recipe_list = [dict(row) for row in recipes]

        return {
            "canonical_id": canonical_id,
            "mapped": True,
            "food": dict(food),
            "recipes": recipe_list,
            "nutrition_status": (
                "requires_recipe_confirmation_and_portion"
                if recipe_list
                else "nutrition_unavailable"
            ),
        }
