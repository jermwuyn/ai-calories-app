
import sqlite3
from pathlib import Path
from contextlib import closing

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.services.recipe_service import get_recipe
from backend.services.recipe_service import calculate_recipe_custom

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
