
import sqlite3
import json
from backend.config import ROOT

PROFILE_TYPES = json.loads((ROOT / "backend/database/profile_types.json").read_text(encoding="utf-8"))
from contextlib import closing
from pathlib import Path

from backend.services.nutrition_calculator import (
    calculate_nutrition,
)

from backend.config import DB_PATH


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
        "profile_type": (PROFILE_TYPES.get(str(recipe[0]), {}).get("profile_type")
                         if PROFILE_TYPES.get(str(recipe[0]), {}).get("name") == recipe[3]
                         and PROFILE_TYPES.get(str(recipe[0]), {}).get("food_id") == recipe[1] else "unreviewed"),
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

import math


def calculate_recipe_custom(
    recipe_id: int,
    components: list[dict],
    db_path=DB_PATH,
):
    """
    Calculate a customized recipe without changing SQLite.

    Example:
        [
            {"ingredient_id": 1, "grams": 200},
            {"ingredient_id": 2, "grams": 100},
        ]

    Remove an ingredient by excluding it from the list.
    Add an ingredient by supplying a valid ingredient_id.
    """

    recipe = get_recipe(recipe_id, db_path)

    if not isinstance(components, list) or not components:
        raise ValueError("Components must be a non-empty list")

    normalized = []
    seen_ids = set()

    for item in components:
        if not isinstance(item, dict):
            raise ValueError("Each component must be an object")

        ingredient_id = item.get("ingredient_id")
        grams = item.get("grams")

        if type(ingredient_id) is not int or ingredient_id <= 0:
            raise ValueError("Invalid ingredient ID")

        if ingredient_id in seen_ids:
            raise ValueError(
                f"Duplicate ingredient ID: {ingredient_id}"
            )

        if (
            isinstance(grams, bool)
            or not isinstance(grams, (int, float))
            or not math.isfinite(grams)
            or grams <= 0
        ):
            raise ValueError(
                f"Invalid weight for ingredient {ingredient_id}"
            )

        seen_ids.add(ingredient_id)

        normalized.append({
            "ingredient_id": ingredient_id,
            "grams": float(grams),
        })

    nutrition = calculate_nutrition(
        normalized,
        db_path=db_path,
    )

    return {
        "recipe_id": recipe["recipe_id"],
        "food_id": recipe["food_id"],
        "food_name": recipe["food_name"],
        "recipe_name": recipe["recipe_name"],
        "is_customized": True,
        "profile_type": recipe["profile_type"],
        "nutrition": nutrition,
    }
