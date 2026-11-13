import sqlite3
from pathlib import Path
import sys
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.config import DB_PATH

FOOD_NAME = "Cơm trắng"
RECIPE_NAME = ""