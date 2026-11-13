
import sqlite3
from pathlib import Path

import sys
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.config import DB_PATH

# Verified against taxonomy unified-food-4-v2.
MAPPINGS = [
    {
        "food_id": 1,
        "canonical_id": "food-v2-023",
        "model_class_index": 23,
        "name_vi": "Cơm tấm",
        "name_en": "Broken Rice",
    },
]


def seed_model_mappings():
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        with conn:
            for item in MAPPINGS:
                row = conn.execute(
                    """
                    SELECT
                        name_vi,
                        canonical_id,
                        model_class_index
                    FROM foods
                    WHERE id = ?
                    """,
                    (item["food_id"],),
                ).fetchone()

                if row is None:
                    raise ValueError(
                        f"Food ID {item['food_id']} not found"
                    )

                if row[0] not in (
                    "Cơm tấm",
                    "Cơm tấm sườn trứng",
                ):
                    raise ValueError(
                        f"Unexpected food name: {row[0]!r}"
                    )

                if row[1] not in (
                    None,
                    item["canonical_id"],
                ):
                    raise ValueError(
                        "Conflicting canonical ID"
                    )

                if row[2] not in (
                    None,
                    item["model_class_index"],
                ):
                    raise ValueError(
                        "Conflicting model class index"
                    )

                conflict = conn.execute(
                    """
                    SELECT id FROM foods
                    WHERE id != ?
                      AND (
                          canonical_id = ?
                          OR model_class_index = ?
                      )
                    """,
                    (
                        item["food_id"],
                        item["canonical_id"],
                        item["model_class_index"],
                    ),
                ).fetchone()

                if conflict:
                    raise ValueError(
                        f"Mapping conflict with Food ID {conflict[0]}"
                    )

                conn.execute(
                    """
                    UPDATE foods
                    SET
                        canonical_id = ?,
                        model_class_index = ?,
                        name_vi = ?,
                        name_en = ?
                    WHERE id = ?
                    """,
                    (
                        item["canonical_id"],
                        item["model_class_index"],
                        item["name_vi"],
                        item["name_en"],
                        item["food_id"],
                    ),
                )

        for item in MAPPINGS:
            print(
                "MAPPED:",
                item["canonical_id"],
                "-> Food ID",
                item["food_id"],
            )

    print("MODEL MAPPINGS VERIFIED")


if __name__ == "__main__":
    seed_model_mappings()
