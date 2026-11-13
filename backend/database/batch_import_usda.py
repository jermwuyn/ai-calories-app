
import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import os

from backend.usda_client import get_food_details

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "backend/database/nutrition.db"
MANIFEST = ROOT / "backend/database/usda_batch.json"
IMPORTER = ROOT / "backend/database/import_usda.py"

REPORT_DIR = Path(r"D:\Code\ai-calories-db-backups\import-reports")


def validate_manifest(items):
    if not isinstance(items, list) or not items:
        raise ValueError("Manifest must be a non-empty list")

    seen_ids = set()
    seen_names = set()

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid manifest entry")

        fdc_id = item.get("fdc_id")
        name = item.get("name_vi")
        state = item.get("state")
        description = item.get("expected_description")

        if type(fdc_id) is not int or fdc_id <= 0:
            raise ValueError("Invalid FDC ID")

        if not all(
            isinstance(x, str) and x.strip()
            for x in (name, state, description)
        ):
            raise ValueError(f"Invalid metadata: {fdc_id}")

        if item.get("reviewed") is not True:
            raise ValueError(f"Not reviewed: {fdc_id}")

        name_key = (name, state)

        if fdc_id in seen_ids or name_key in seen_names:
            raise ValueError(f"Duplicate manifest entry: {fdc_id}")

        seen_ids.add(fdc_id)
        seen_names.add(name_key)


def inspect_existing(conn, item):
    """Check FDC identity AND ingredient name/state."""

    fdc_id = item["fdc_id"]
    source_url = (
        "https://fdc.nal.usda.gov/"
        f"food-details/{fdc_id}/nutrients"
    )

    matches = conn.execute(
        """
        SELECT DISTINCT
            i.id, i.name_vi, i.preparation_state
        FROM ingredients i
        JOIN ingredient_nutrients v
            ON v.ingredient_id = i.id
        JOIN data_sources s
            ON s.id = v.source_id
        WHERE s.reference_url = ?
        """,
        (source_url,),
    ).fetchall()

    names = conn.execute(
        """
        SELECT id FROM ingredients
        WHERE name_vi = ?
          AND preparation_state = ?
        """,
        (item["name_vi"], item["state"]),
    ).fetchall()

    if len(matches) > 1 or len(names) > 1:
        raise ValueError(f"Duplicate database entries: {fdc_id}")

    if matches:
        existing_id, name, state = matches[0]

        if (
            name != item["name_vi"]
            or state != item["state"]
            or not names
            or names[0][0] != existing_id
        ):
            raise ValueError(
                f"FDC identity conflict: {fdc_id}"
            )

        return "SKIP_ALREADY_IMPORTED"

    if names:
        raise ValueError(
            f"Name/state already used by another source: {fdc_id}"
        )

    return "NEW"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Import new records; default is dry-run",
    )
    args = parser.parse_args()

    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)

    items = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validate_manifest(items)

    # Preflight all local records before performing writes.
    plan = []

    with sqlite3.connect(DB_PATH) as conn:
        for item in items:
            status = inspect_existing(conn, item)
            plan.append((item, status))

    print("=== USDA BATCH IMPORT ===")
    print("Mode:", "APPLY" if args.apply else "DRY RUN")
    print("Entries:", len(plan))

    report = []

    for item, status in plan:
        fdc_id = item["fdc_id"]

        if status == "SKIP_ALREADY_IMPORTED":
            print(f"{fdc_id}: SKIP_ALREADY_IMPORTED")
            report.append({
                "fdc_id": fdc_id,
                "status": status,
            })
            continue

        if not args.apply:
            print(f"{fdc_id}: READY_FOR_REVIEWED_IMPORT")
            report.append({
                "fdc_id": fdc_id,
                "status": "READY",
            })
            continue

        try:
            # Verify actual USDA identity before writing.
            food = get_food_details(fdc_id)

            if (
                food.get("fdcId") != fdc_id
                or food.get("dataType") != "SR Legacy"
                or food.get("description")
                    != item["expected_description"]
            ):
                raise ValueError(
                    f"USDA metadata mismatch: {fdc_id}"
                )

            command = [
                sys.executable,
                str(IMPORTER),
                "--fdc-id", str(fdc_id),
                "--name-vi", item["name_vi"],
                "--state", item["state"],
            ]

            completed = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={
                    **os.environ,
                    "PYTHONIOENCODING": "utf-8",
                },
            )

            if completed.returncode != 0:
                raise RuntimeError(
                    completed.stderr or completed.stdout
                )

            print(f"{fdc_id}: IMPORT_SUCCESSFUL")
            report.append({
                "fdc_id": fdc_id,
                "status": "IMPORTED",
            })

        except Exception as exc:
            print(f"{fdc_id}: IMPORT_FAILED")
            print(str(exc))

            report.append({
                "fdc_id": fdc_id,
                "status": "FAILED",
                "error": str(exc),
            })
            # Stop on the first failure.
            break

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    path = REPORT_DIR / (
        "batch-"
        + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        + ".json"
    )

    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n=== SUMMARY ===")
    for status in sorted(set(x["status"] for x in report)):
        count = sum(x["status"] == status for x in report)
        print(status, count)

    print("Report:", path)

    if any(x["status"] == "FAILED" for x in report):
        sys.exit(1)

    print("BATCH IMPORT CHECK COMPLETED")


if __name__ == "__main__":
    main()
