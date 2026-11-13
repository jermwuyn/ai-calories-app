import sqlite3
from pathlib import Path

import sys
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.config import DB_PATH

NUTRIENTS = [
    # 1. Energy and macronutrients
    ("energy", "Năng lượng", "kcal"),
    ("protein", "Protein", "g"),
    ("carbohydrates", "Carbohydrate", "g"),
    ("total_fat", "Chất béo tổng", "g"),

    # 2. Additional nutritional information
    ("saturated_fat", "Chất béo bão hòa", "g"),
    ("fiber", "Chất xơ", "g"),
    ("total_sugars", "Đường tổng", "g"),
    ("sodium", "Natri", "mg"),
    ("calcium", "Canxi", "mg"),
    ("iron", "Sắt", "mg"),
    ("potassium", "Kali", "mg"),
    ("vitamin_c", "Vitamin C", "mg"),

    # 3. Extended nutrients
    ("trans_fat", "Chất béo trans", "g"),
    ("cholesterol", "Cholesterol", "mg"),
    ("added_sugars", "Đường bổ sung", "g"),
    ("vitamin_a", "Vitamin A", "µg RAE"),
    ("vitamin_d", "Vitamin D", "µg"),
    ("vitamin_b12", "Vitamin B12", "µg"),
    ("folate", "Folate tổng", "µg"),
    ("magnesium", "Magie", "mg"),
    ("zinc", "Kẽm", "mg"),
]
def seed_nutrients():
    if not DB_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    codes = [item[0] for item in NUTRIENTS]

    assert len(codes) == len(set(codes)), (
        "Duplicate nutrient codes"
    )

    assert len(NUTRIENTS) == 21, (
        "Expected exactly 21 nutrients"
    )

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        with conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO nutrients
                    (code, name, unit)
                VALUES (?, ?, ?)
                """,
                NUTRIENTS,
            )

            # Verify existing records are consistent
            for code, name, unit in NUTRIENTS:
                stored = conn.execute(
                    """
                    SELECT name, unit
                    FROM nutrients
                    WHERE code = ?
                    """,
                    (code,),
                ).fetchone()

                if stored != (name, unit):
                    raise ValueError(
                        f"Nutrient mismatch: {code}. "
                        f"Expected {(name, unit)}, "
                        f"found {stored}"
                    )

        rows = conn.execute(
            """
            SELECT id, code, name, unit
            FROM nutrients
            ORDER BY id
            """
        ).fetchall()

        print(f"Configured nutrients: {len(NUTRIENTS)}")
        print(f"Total database nutrients: {len(rows)}")
        print("-" * 65)

        for nutrient_id, code, name, unit in rows:
            print(
                f"{nutrient_id:>3} | "
                f"{code:<18} | "
                f"{name} ({unit})"
            )

        print("-" * 65)
        print("NUTRIENTS INITIALIZED SUCCESSFULLY")

    finally:
        conn.close()


if __name__ == "__main__":
    seed_nutrients()
