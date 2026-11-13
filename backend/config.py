"""Project-relative settings; environment variables override .env."""
import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
def path_setting(name, default):
    value = Path(os.getenv(name, default)).expanduser()
    return (ROOT / value).resolve() if not value.is_absolute() else value.resolve()
DB_PATH = path_setting('AI_CALORIES_DB_PATH', 'backend/database/nutrition.db')
CHECKPOINT_PATH = path_setting('AI_CALORIES_CHECKPOINT', 'checkpoints/best.pth')
BACKUP_DIR = path_setting('AI_CALORIES_BACKUP_DIR', 'local/backups')
CORS_ORIGINS = [x.strip() for x in os.getenv('AI_CALORIES_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()]
