"""Atomic USDA ingredient and as-served recipe import. Run as a backend.database module."""
import argparse
from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3
from uuid import uuid4

from backend.database.batch_import_usda import DB_PATH, MANIFEST, REPORT_DIR, inspect_existing, validate_manifest
from backend.database.import_usda import NUTRIENT_MAP, extract_nutrients, normalize_unit
from backend.usda_client import get_food_details

RECIPES = MANIFEST.with_name("reviewed_recipes.json")
SOURCE = "USDA FoodData Central - SR Legacy"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_url(fdc):
    return f"https://fdc.nal.usda.gov/food-details/{fdc}/nutrients"


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def import_item(db, item, food):
    fdc = item["fdc_id"]
    kind = item.get("data_type", "SR Legacy")
    require(kind in ("SR Legacy", "Survey (FNDDS)"), "Unsupported USDA dataset")
    provider = f"USDA FoodData Central - {kind}"
    require((food.get("fdcId"), food.get("description"), food.get("dataType")) ==
            (fdc, item["expected_description"], kind), f"USDA identity mismatch {fdc}")
    values = extract_nutrients(food)
    require(all(values[k] <= 100 for k in ("protein", "carbohydrates", "total_fat"))
            and values["energy"] <= 1000, f"Implausible per-100g value {fdc}")
    status = inspect_existing(db, item)
    url = source_url(fdc)
    sources = db.execute("SELECT id,name,version FROM data_sources WHERE reference_url=?", (url,)).fetchall()
    require(len(sources) <= 1 and all(s[1:] == (provider, kind) for s in sources), f"Source conflict {fdc}")
    sid = sources[0][0] if sources else db.execute(
        "INSERT INTO data_sources(name,reference_url,version) VALUES(?,?,?)", (provider,url,kind)).lastrowid
    if status == "NEW":
        iid = db.execute("INSERT INTO ingredients(name_vi,name_en,preparation_state) VALUES(?,?,?)",
                         (item["name_vi"],food["description"],item["state"])).lastrowid
    else:
        iid, desc = db.execute("SELECT id,name_en FROM ingredients WHERE name_vi=? AND preparation_state=?",
                               (item["name_vi"],item["state"])).fetchone()
        require(desc == food["description"], f"Stored description differs {fdc}")
    expected = {}
    for code, unit in NUTRIENT_MAP.values():
        if code not in values:
            continue
        row = db.execute("SELECT id,unit FROM nutrients WHERE code=?", (code,)).fetchone()
        unit = "µg RAE" if code == "vitamin_a" else unit
        require(row and normalize_unit(row[1]) == normalize_unit(unit), f"Catalog unit mismatch {code}")
        expected[row[0]] = (values[code], sid)
    if status == "NEW":
        db.executemany("INSERT INTO ingredient_nutrients VALUES(?,?,?,?)",
                       [(iid,nid,*pair) for nid,pair in expected.items()])
    stored = {n:(v,s) for n,v,s in db.execute(
        "SELECT nutrient_id,amount_per_100g,source_id FROM ingredient_nutrients WHERE ingredient_id=?", (iid,))}
    require(stored == expected, f"Stored USDA nutrients differ {fdc}")
    return iid, status, values


def seed(db, recipe, ingredients):
    require(recipe.get("reviewed") is True and all(isinstance(recipe.get(k), str) and recipe[k].strip()
            for k in ("source","canonical_id","name")), "Missing recipe review, source or identity")
    portion = recipe["default_serving_g"]
    require(positive(portion), "Invalid serving")
    mapping = recipe.get("model_mapping")
    if mapping is not None:
        index = mapping["index"]
        require(type(index) is int and index >= 0, "Invalid model index")
        identity = (recipe["canonical_id"], index)
        matches = db.execute("SELECT canonical_id,model_class_index FROM foods WHERE canonical_id=? OR model_class_index=?", identity).fetchall()
        if matches:
            require(matches == [identity], "Food mapping conflict")
        else:
            db.execute("INSERT INTO foods(canonical_id,model_class_index,name_vi,name_en) VALUES(?,?,?,?)",
                       (*identity, mapping["name_vi"], mapping["name_en"]))
    food = db.execute("SELECT id FROM foods WHERE canonical_id=?", (recipe["canonical_id"],)).fetchone()
    require(food, "Unknown food")
    parts = {}
    totals = dict.fromkeys(("energy","protein","carbohydrates","total_fat"), 0.0)
    for part in recipe["ingredients"]:
        fdc, grams, optional = part["fdc_id"], part["grams"], part["is_optional"]
        require(type(fdc) is int and fdc in ingredients and positive(grams) and type(optional) is bool,
                "Invalid component, grams or optional flag")
        iid, _, values = ingredients[fdc]
        require(iid not in parts, "Repeated component")
        parts[iid] = (grams, int(optional))
        for code in totals:
            totals[code] += grams * values[code] / 100
    require(parts and math.isclose(sum(g for g,_ in parts.values()), portion, abs_tol=0.001),
            "As-served ingredient grams must sum to serving")
    rows = db.execute("SELECT id,default_serving_g FROM recipes WHERE food_id=? AND name=?",
                      (food[0],recipe["name"])).fetchall()
    if rows:
        rid, old = rows[0]
        stored = {i:(g,o) for i,g,o in db.execute(
            "SELECT ingredient_id,grams,is_optional FROM recipe_ingredients WHERE recipe_id=?", (rid,))}
        require(len(rows)==1 and old==portion and stored==parts, "Existing recipe differs")
    else:
        rid = db.execute("INSERT INTO recipes(food_id,name,default_serving_g) VALUES(?,?,?)",
                         (food[0],recipe["name"],portion)).lastrowid
        db.executemany("INSERT INTO recipe_ingredients VALUES(?,?,?,?)", [(rid,i,*v) for i,v in parts.items()])
    return {"name":recipe["name"], "source":recipe["source"], "status":"SKIP" if rows else "NEW",
            "per_serving_including_optional":totals}


def run(path, items, recipes, foods, apply=False, backup_dir=REPORT_DIR.parent):
    validate_manifest(items)
    require(isinstance(recipes,list), "Expected recipe array")
    keys = [(r["canonical_id"],r["name"]) for r in recipes]
    require(len(keys)==len(set(keys)), "Duplicate recipe")
    uri = path.resolve().as_uri()
    with closing(sqlite3.connect(uri+"?mode="+("rw" if apply else "ro"),uri=True)) as live, closing(sqlite3.connect(":memory:")) as preview:
        if not apply:
            live.backup(preview)
        db = live if apply else preview
        db.execute("PRAGMA foreign_keys=ON")
        with db:
            db.execute("BEGIN IMMEDIATE")
            before = db.total_changes
            ingredients = {i["fdc_id"]:import_item(db,i,foods[i["fdc_id"]]) for i in items}
            results = [seed(db,r,ingredients) for r in recipes]
            require(db.execute("PRAGMA integrity_check").fetchall()==[("ok",)] and
                    not db.execute("PRAGMA foreign_key_check").fetchall(), "Database integrity failure")
            changes = db.total_changes-before
            backup = None
            if apply and changes:
                backup_dir.mkdir(parents=True,exist_ok=True)
                backup = backup_dir / f"before-reviewed-{uuid4().hex}.db"
                # Independent reader sees the committed state while this connection holds the writer lock.
                with closing(sqlite3.connect(uri+"?mode=ro",uri=True)) as reader, closing(sqlite3.connect(backup)) as target:
                    reader.backup(target)
                    require(target.execute("PRAGMA integrity_check").fetchall()==[("ok",)], "Backup integrity failure")
        return {"apply":apply,"changed_rows":changes,"backup":str(backup) if backup else None,
                "ingredients":{k:{"status":s,"nutrients_per_100g":v} for k,(_,s,v) in ingredients.items()},"recipes":results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--recipes",type=Path,default=RECIPES)
    args = parser.parse_args()
    items = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    recipes = json.loads(args.recipes.read_text(encoding="utf-8-sig"))
    validate_manifest(items)
    foods = {i["fdc_id"]:get_food_details(i["fdc_id"]) for i in items}
    report = run(DB_PATH,items,recipes,foods)
    if args.apply:
        report = run(DB_PATH,items,recipes,foods,True)
        require(run(DB_PATH,items,recipes,foods)["changed_rows"]==0, "Replay changed rows")
    REPORT_DIR.mkdir(parents=True,exist_ok=True)
    dest = REPORT_DIR / f"reviewed-{uuid4().hex}.json"
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Changed rows:",report["changed_rows"],"Backup:",report["backup"],"Report:",dest)


if __name__ == "__main__":
    main()
