
import argparse
import io
import re
import sqlite3
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

from backend.database import import_usda


DB_PATH = import_usda.DB_PATH

from backend.config import BACKUP_DIR

SOURCE_NAME = "USDA FoodData Central - SR Legacy"

URL_PATTERN = re.compile(
    r"https://fdc\.nal\.usda\.gov/"
    r"food-details/([0-9]+)/nutrients"
)


def get_plan():
    """Read ingredient identities from existing SQLite data."""

    plan = []
    used_fdc_ids = set()

    with sqlite3.connect(DB_PATH) as conn:
        ingredients = conn.execute(
            """
            SELECT id, name_vi, preparation_state
            FROM ingredients
            ORDER BY id
            """
        ).fetchall()

        for ingredient_id, name, state in ingredients:
            sources = conn.execute(
                """
                SELECT DISTINCT
                    s.name,
                    s.reference_url
                FROM ingredient_nutrients v
                JOIN data_sources s
                    ON s.id = v.source_id
                WHERE v.ingredient_id = ?
                """,
                (ingredient_id,),
            ).fetchall()

            if len(sources) != 1:
                raise ValueError(
                    f"Ingredient {ingredient_id}: "
                    "missing or conflicting sources"
                )

            source_name, url = sources[0]

            if source_name != SOURCE_NAME:
                raise ValueError(
                    f"Ingredient {ingredient_id}: "
                    "unexpected data source"
                )

            match = URL_PATTERN.fullmatch(url or "")

            if match is None:
                raise ValueError(
                    f"Ingredient {ingredient_id}: "
                    "invalid USDA source URL"
                )

            fdc_id = int(match.group(1))

            if fdc_id in used_fdc_ids:
                raise ValueError(
                    f"Duplicate FDC ID: {fdc_id}"
                )

            used_fdc_ids.add(fdc_id)

            plan.append({
                "ingredient_id": ingredient_id,
                "fdc_id": fdc_id,
                "name": name,
                "state": state,
            })

    return plan


def get_nutrient_values(ingredient_id):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT
                nutrient_id,
                amount_per_100g,
                source_id
            FROM ingredient_nutrients
            WHERE ingredient_id = ?
            """,
            (ingredient_id,),
        ).fetchall()

    return {
        nutrient_id: (amount, source_id)
        for nutrient_id, amount, source_id in rows
    }


def backup_database():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    destination = BACKUP_DIR / (
        "nutrition-before-full-backfill-"
        + datetime.now().strftime(
            "%Y%m%d-%H%M%S-%f"
        )
        + ".db"
    )

    with sqlite3.connect(DB_PATH) as source:
        with sqlite3.connect(destination) as backup:
            source.backup(backup)

    print("Backup:", destination)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write missing nutrients to SQLite",
    )

    args = parser.parse_args()

    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)

    plan = get_plan()

    print("=== USDA NUTRIENT BACKFILL ===")
    print("Mode:", "APPLY" if args.apply else "DRY RUN")
    print("Ingredients:", len(plan))
    print("-" * 55)

    for item in plan:
        print(
            f"Ingredient {item['ingredient_id']:02d} "
            f"-> FDC {item['fdc_id']}"
        )

    if not args.apply:
        print("\nBACKFILL DRY RUN PASSED")
        return

    backup_database()

    total_added = 0

    for item in plan:
        ingredient_id = item["ingredient_id"]

        before = get_nutrient_values(ingredient_id)

        # Reuse the existing, tested importer.
        import_usda.FDC_ID = item["fdc_id"]
        import_usda.NAME_VI = item["name"]
        import_usda.PREPARATION_STATE = item["state"]

        # Capture verbose importer output.
        # This also avoids Windows console Unicode errors.
        with redirect_stdout(io.StringIO()):
            import_usda.import_food()

        after = get_nutrient_values(ingredient_id)

        # Existing nutrient values and sources must be preserved.
        for nutrient_id, old_value in before.items():
            if after.get(nutrient_id) != old_value:
                raise ValueError(
                    f"Existing nutrient changed: "
                    f"ingredient {ingredient_id}, "
                    f"nutrient {nutrient_id}"
                )

        added = len(after) - len(before)

        if added < 0:
            raise ValueError(
                "Unexpected loss of nutrient records"
            )

        total_added += added

        print(
            f"Ingredient {ingredient_id:02d}: "
            f"{len(before)} -> {len(after)} "
            f"(+{added})"
        )

    with sqlite3.connect(DB_PATH) as conn:
        errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if errors:
            raise ValueError(
                f"Foreign key errors: {errors}"
            )

    print("-" * 55)
    print("Total new nutrient records:", total_added)
    print("BACKFILL COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
