
import sqlite3
from contextlib import closing
from pathlib import Path

from backend.services.nutrition_calculator import (
    calculate_nutrition,
)

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "nutrition.db"
)


def get_recipe(recipe_id: int, db_path=DB_PATH):
    """Retrieve a recipe and its ingredients from SQLite."""

    if not Path(db_path).is_file():
        raise FileNotFoundError(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        recipe = conn.execute(
            """
            SELECT
                r.id,
                r.food_id,
                f.name_vi,
                r.name,
                r.default_serving_g
            FROM recipes r
            JOIN foods f ON f.id = r.food_id
            WHERE r.id = ?
            """,
            (recipe_id,),
        ).fetchone()

        if recipe is None:
            raise ValueError(f"Recipe {recipe_id} not found")

        rows = conn.execute(
            """
            SELECT
                ri.ingredient_id,
                i.name_vi,
                ri.grams,
                ri.is_optional
            FROM recipe_ingredients ri
            JOIN ingredients i
                ON i.id = ri.ingredient_id
            WHERE ri.recipe_id = ?
            ORDER BY ri.ingredient_id
            """,
            (recipe_id,),
        ).fetchall()

    components = [
        {
            "ingredient_id": ingredient_id,
            "name": name,
            "grams": grams,
            "is_optional": bool(is_optional),
        }
        for ingredient_id, name, grams, is_optional in rows
    ]

    return {
        "recipe_id": recipe[0],
        "food_id": recipe[1],
        "food_name": recipe[2],
        "recipe_name": recipe[3],
        "default_serving_g": recipe[4],
        "components": components,
    }


def calculate_recipe(recipe_id: int, db_path=DB_PATH):
    """Calculate nutrition using the stored recipe."""

    recipe = get_recipe(recipe_id, db_path)

    components = [
        {
            "ingredient_id": item["ingredient_id"],
            "grams": item["grams"],
        }
        for item in recipe["components"]
    ]

    result = calculate_nutrition(
        components,
        db_path=db_path,
    )

    return {
        **recipe,
        "nutrition": result,
    }
