from contextlib import closing

import math
import sqlite3
from pathlib import Path

from backend.config import DB_PATH


def calculate_nutrition(components, db_path=DB_PATH):
    """
    Calculate meal nutrition from ingredient quantities.

    Input:
        [
            {"ingredient_id": 1, "grams": 150},
            {"ingredient_id": 2, "grams": 90},
        ]

    Missing nutrient values are NOT treated as zero.
    """

    if not components:
        raise ValueError("Ingredient list cannot be empty")

    portions = []

    for component in components:
        ingredient_id = component["ingredient_id"]
        grams = float(component["grams"])

        if not isinstance(ingredient_id, int) or isinstance(ingredient_id, bool) or ingredient_id <= 0:
            raise ValueError("Invalid ingredient ID")

        if not math.isfinite(grams) or grams < 0:
            raise ValueError("Invalid ingredient weight")

        if grams > 0:
            portions.append((ingredient_id, grams))

    if not portions:
        raise ValueError("Total ingredient weight must be positive")

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        nutrients = conn.execute(
            "SELECT id, code, name, unit FROM nutrients"
        ).fetchall()

        ingredients = []

        for ingredient_id, grams in portions:
            ingredient = conn.execute(
                "SELECT name_vi FROM ingredients WHERE id = ?",
                (ingredient_id,),
            ).fetchone()

            if ingredient is None:
                raise ValueError(
                    f"Ingredient {ingredient_id} not found"
                )

            rows = conn.execute(
                """
                SELECT n.code, x.amount_per_100g
                FROM ingredient_nutrients x
                JOIN nutrients n ON n.id = x.nutrient_id
                WHERE x.ingredient_id = ?
                """,
                (ingredient_id,),
            ).fetchall()

            values = {
                code: amount * grams / 100
                for code, amount in rows
            }

            ingredients.append({
                "id": ingredient_id,
                "name": ingredient[0],
                "grams": grams,
                "nutrients": values,
            })

    report = {}

    for _, code, name, unit in nutrients:
        missing = [
            item["id"]
            for item in ingredients
            if code not in item["nutrients"]
        ]

        if missing:
            amount = None
            status = "incomplete"
        else:
            amount = round(
                sum(
                    item["nutrients"][code]
                    for item in ingredients
                ),
                2,
            )
            status = "complete"

        report[code] = {
            "name": name,
            "amount": amount,
            "unit": unit,
            "status": status,
            "missing_ingredient_ids": missing,
        }

    return {
        "total_grams": round(
            sum(item["grams"] for item in ingredients), 2
        ),
        "ingredients": [
            {
                "id": item["id"],
                "name": item["name"],
                "grams": item["grams"],
            }
            for item in ingredients
        ],
        "nutrients": report,
    }
