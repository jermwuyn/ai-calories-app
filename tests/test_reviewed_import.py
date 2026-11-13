import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

from backend.database import reviewed_import as workflow


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "test.db"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript(workflow.DB_PATH.with_name("schema.sql").read_text())
            db.execute("INSERT INTO foods(canonical_id,name_vi) VALUES('fixture','fixture')")
            db.executemany("INSERT INTO nutrients(code,name,unit) VALUES(?,?,?)",
                           [(c,c,u) for c,u in workflow.NUTRIENT_MAP.values()])
        self.item = dict(fdc_id=168290,name_vi="test",state="cooked_simmered",reviewed=True,
                         expected_description="Pork, fresh, variety meats and by-products, feet, cooked, simmered")
        self.food = dict(fdcId=168290,description=self.item["expected_description"],dataType="SR Legacy",
                         foodNutrients=[dict(nutrient=dict(id=n,unitName=u),amount=v)
                                        for n,u,v in [(1008,"kcal",238),(1003,"g",21.94),(1005,"g",0),(1004,"g",16.05)]])
        self.recipe = dict(canonical_id="fixture",name="test",source="unit test only",reviewed=True,
                           default_serving_g=100,ingredients=[dict(fdc_id=168290,grams=100,is_optional=False)])

    def execute(self, apply=False):
        return workflow.run(self.path,[self.item],[self.recipe],{168290:self.food},apply,self.path.parent)

    def test_preview_backup_and_replay(self):
        original = self.path.read_bytes()
        self.assertGreater(self.execute()["changed_rows"],0)
        self.assertEqual(original,self.path.read_bytes())
        report = self.execute(True)
        with closing(sqlite3.connect(report["backup"])) as backup:
            self.assertEqual(backup.execute("SELECT count(*) FROM ingredients").fetchone()[0],0)
        self.assertEqual(report["recipes"][0]["per_serving_including_optional"]["energy"],238)
        self.assertEqual(self.execute(True)["changed_rows"],0)

    def test_recipe_failure_rolls_back_ingredients(self):
        self.recipe["ingredients"][0]["grams"] = -1
        with self.assertRaises(ValueError):
            self.execute(True)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute("SELECT count(*) FROM ingredients").fetchone()[0],0)

    def test_source_and_units(self):
        self.food["fdcId"] = 0
        with self.assertRaises(ValueError):
            self.execute()
        self.food["fdcId"] = 168290
        self.food["foodNutrients"][0]["nutrient"]["unitName"] = "kJ"
        with self.assertRaises(ValueError):
            self.execute()