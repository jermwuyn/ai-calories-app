
import sqlite3
from pathlib import Path

import sys
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.config import DB_PATH

FOOD_NAME = "Cơm tấm"
RECIPE_NAME = "Cơm tấm sườn trứng - test"
SERVING_G = 370.0

# Ingredient name, weight in grams, optional flag (0 / 1)
COMPONENTS = [
    ("Cơm trắng (gạo hạt vừa, đã nấu)", 180.0, 0),
    ("Sườn cốt lết heo nướng (phần ăn được)", 100.0, 0),
    ("Dưa leo tươi (còn vỏ)", 40.0, 0),
    ("Trứng gà chiên (ốp la)", 50.0, 1),
]


def get_ingredient_id(conn: sqlite3.Connection, name: str) -> int:
    rows = conn.execute(
        "SELECT id FROM ingredients WHERE name_vi = ?", (name,)
    ).fetchall()
    if len(rows) != 1:
        raise ValueError(
            f"Expected exactly one ingredient named {name!r}; found {len(rows)}"
        )
    return rows[0][0]


def seed_recipe() -> None:
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        # The transaction is rolled back if any validation fails.
        with conn:
            items = [
                (get_ingredient_id(conn, name), grams, is_optional)
                for name, grams, is_optional in COMPONENTS
            ]

            foods = conn.execute(
                "SELECT id FROM foods WHERE name_vi = ?", (FOOD_NAME,)
            ).fetchall()
            if len(foods) > 1:
                raise ValueError(f"Duplicate foods named {FOOD_NAME!r}")

            if foods:
                food_id = foods[0][0]
            else:
                food_id = conn.execute(
                    "INSERT INTO foods (name_vi, name_en) VALUES (?, ?)",
                    (FOOD_NAME, "Broken rice with pork chop and fried egg"),
                ).lastrowid

            recipes = conn.execute(
                """
                SELECT id, default_serving_g
                FROM recipes
                WHERE food_id = ? AND name = ?
                """,
                (food_id, RECIPE_NAME),
            ).fetchall()
            if len(recipes) > 1:
                raise ValueError("Duplicate recipes with the same food and name")

            if recipes:
                recipe_id, stored_serving_g = recipes[0]
                if stored_serving_g != SERVING_G:
                    raise ValueError(
                        "Existing recipe portion differs; manual review required"
                    )
            else:
                recipe_id = conn.execute(
                    """
                    INSERT INTO recipes (food_id, name, default_serving_g)
                    VALUES (?, ?, ?)
                    """,
                    (food_id, RECIPE_NAME, SERVING_G),
                ).lastrowid

            current = conn.execute(
                """
                SELECT ingredient_id, grams, is_optional
                FROM recipe_ingredients
                WHERE recipe_id = ?
                """,
                (recipe_id,),
            ).fetchall()

            if current:
                if sorted(current) != sorted(items):
                    raise ValueError(
                        "Existing recipe ingredients differ; manual review required"
                    )
            else:
                conn.executemany(
                    """
                    INSERT INTO recipe_ingredients
                        (recipe_id, ingredient_id, grams, is_optional)
                    VALUES (?, ?, ?, ?)
                    """,
                    [(recipe_id, *item) for item in items],
                )

            # Ensure the recipe has the expected ingredients and portion.
            count = conn.execute(
                "SELECT COUNT(*) FROM recipe_ingredients WHERE recipe_id = ?",
                (recipe_id,),
            ).fetchone()[0]
            assert count == len(items), "Unexpected ingredient count"
            assert sum(grams for _, grams, _ in items) == SERVING_G

    print("RECIPE CREATED/VERIFIED SUCCESSFULLY")
    print("Food ID:", food_id)
    print("Recipe ID:", recipe_id)
    print("Name:", FOOD_NAME)
    print("Total grams:", SERVING_G)
    print("Ingredient count:", len(items))


if __name__ == "__main__":
    seed_recipe()