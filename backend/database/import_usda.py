
import math
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.usda_client import get_food_details

DB_PATH = ROOT / "backend/database/nutrition.db"

FDC_ID = 168930
NAME_VI = "Cơm trắng (gạo hạt vừa, đã nấu)"
PREPARATION_STATE = "cooked"

# USDA nutrient ID -> (internal code, expected unit)
# Only IDs verified from this USDA record.
NUTRIENT_MAP = {
    1008: ("energy", "kcal"),
    1003: ("protein", "g"),
    1005: ("carbohydrates", "g"),
    1004: ("total_fat", "g"),
    1258: ("saturated_fat", "g"),
    1253: ("cholesterol", "mg"),
    1087: ("calcium", "mg"),
    1089: ("iron", "mg"),
    1090: ("magnesium", "mg"),
    1092: ("potassium", "mg"),
    1093: ("sodium", "mg"),
    1095: ("zinc", "mg"),
    1162: ("vitamin_c", "mg"),
    1177: ("folate", "µg"),
    1178: ("vitamin_b12", "µg"),
    1106: ("vitamin_a", "µg"),
    1114: ("vitamin_d", "µg"),
}


def normalize_unit(unit):
    return str(unit).strip().replace("μ", "µ").lower()


def extract_nutrients(food):
    values = {}

    for entry in food.get("foodNutrients", []):
        nutrient = entry.get("nutrient") or {}
        usda_id = nutrient.get("id")

        if usda_id not in NUTRIENT_MAP:
            continue

        code, expected_unit = NUTRIENT_MAP[usda_id]
        amount = entry.get("amount")

        if amount is None:
            continue

        actual_unit = normalize_unit(nutrient.get("unitName"))

        if actual_unit != normalize_unit(expected_unit):
            raise ValueError(
                f"Unit mismatch for {code}: {actual_unit}"
            )

        amount = float(amount)

        if not math.isfinite(amount) or amount < 0:
            raise ValueError(f"Invalid amount for {code}")

        if code in values and values[code] != amount:
            raise ValueError(f"Conflicting values for {code}")

        values[code] = amount

    for required in (
        "energy", "protein", "carbohydrates", "total_fat"
    ):
        if required not in values:
            raise ValueError(f"Missing required nutrient: {required}")

    return values


def import_food():
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)

    food = get_food_details(FDC_ID)

    if food.get("fdcId") != FDC_ID:
        raise ValueError("Unexpected FDC ID")

    if food.get("dataType") != "SR Legacy":
        raise ValueError("Unexpected USDA data type")

    values = extract_nutrients(food)

    source_name = "USDA FoodData Central - SR Legacy"
    source_url = (
        f"https://fdc.nal.usda.gov/"
        f"food-details/{FDC_ID}/nutrients"
    )

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        with conn:
            # Data source
            source = conn.execute(
                """
                SELECT id FROM data_sources
                WHERE name = ? AND reference_url = ?
                """,
                (source_name, source_url),
            ).fetchone()

            if source:
                source_id = source[0]
            else:
                source_id = conn.execute(
                    """
                    INSERT INTO data_sources
                        (name, reference_url, version)
                    VALUES (?, ?, ?)
                    """,
                    (source_name, source_url, "SR Legacy"),
                ).lastrowid

            # Ingredient
            existing = conn.execute(
                """
                SELECT id FROM ingredients
                WHERE name_vi = ? AND preparation_state = ?
                """,
                (NAME_VI, PREPARATION_STATE),
            ).fetchall()

            if len(existing) > 1:
                raise ValueError("Duplicate ingredient records")

            if existing:
                ingredient_id = existing[0][0]
            else:
                ingredient_id = conn.execute(
                    """
                    INSERT INTO ingredients
                        (name_vi, name_en, preparation_state)
                    VALUES (?, ?, ?)
                    """,
                    (
                        NAME_VI,
                        food["description"],
                        PREPARATION_STATE,
                    ),
                ).lastrowid

            # Nutrient values
            inserted = 0

            for code, amount in values.items():
                nutrient = conn.execute(
                    """
                    SELECT id, unit FROM nutrients
                    WHERE code = ?
                    """,
                    (code,),
                ).fetchone()

                if nutrient is None:
                    raise ValueError(f"Unknown nutrient: {code}")

                nutrient_id, db_unit = nutrient

                
                DB_UNIT_OVERRIDES = {
                    "vitamin_a": "µg RAE",
                }

                expected_unit = DB_UNIT_OVERRIDES.get(
                    code,
                    next(
                        unit
                        for mapped_code, unit in NUTRIENT_MAP.values()
                        if mapped_code == code
                    )
                )

                if normalize_unit(db_unit) != normalize_unit(expected_unit):
                    raise ValueError(
                        f"DB unit mismatch for {code}: "
                        f"database={db_unit!r}, expected={expected_unit!r}"
                    )                

                previous = conn.execute(
                    """
                    SELECT amount_per_100g, source_id
                    FROM ingredient_nutrients
                    WHERE ingredient_id = ? AND nutrient_id = ?
                    """,
                    (ingredient_id, nutrient_id),
                ).fetchone()

                if previous:
                    if (
                        previous[1] != source_id
                        or not math.isclose(
                            previous[0], amount, abs_tol=1e-8
                        )
                    ):
                        raise ValueError(
                            f"Existing value differs: {code}"
                        )
                    continue

                conn.execute(
                    """
                    INSERT INTO ingredient_nutrients
                        (ingredient_id, nutrient_id,
                         amount_per_100g, source_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        ingredient_id,
                        nutrient_id,
                        amount,
                        source_id,
                    ),
                )
                inserted += 1

        print("IMPORT SUCCESSFUL")
        print("Ingredient ID:", ingredient_id)
        print("FDC ID:", FDC_ID)
        print("Name:", NAME_VI)
        print("New nutrient records:", inserted)
        print("Available nutrients:", len(values))
        print("-" * 45)

        for code, amount in values.items():
            print(f"{code:<18}: {amount}")

    finally:
        conn.close()


if __name__ == "__main__":
    import_food()
