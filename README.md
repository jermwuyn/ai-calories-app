# AI Calories v0.1.0

A self-contained FastAPI backend for food recognition, explicit food confirmation,
and portion-based nutrition calculations. A React/Vite developer can use the API
without cloning the training repository. No USDA API access is needed at runtime.

## Setup (Python 3.11)

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python scripts/setup.py
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Setup installs the pinned requirements, restores a missing database, checks SQLite
integrity and foreign keys, installs and SHA-256-verifies the checkpoint, runs CPU
inference and checks the database's canonical mappings. Internet is needed for
package installation and the initial model download. Setup can be rerun safely.

**Release preparation status:** the checkpoint must be uploaded as `best.pth` to
GitHub Release `v0.1.0` before the default download URL works. This working tree
prepares that release; it does not publish it. If you already downloaded the asset:

```sh
python scripts/setup.py --checkpoint-file /path/to/best.pth
# With dependencies already installed:
python scripts/setup.py --skip-install
```

The release URL and trusted checksum are in `release/model.json`. An unavailable
asset or checksum mismatch fails setup; `/predict` returns 503 for a missing model.
Only the trusted checkpoint is loaded (its original format uses Python pickle).
The runtime asset lives in ignored `checkpoints/best.pth`; upload that exact file
as the release asset, not as a Git commit.

Copy `.env.example` to `.env` for optional settings. Relative paths resolve from
the repository root. Settings include `AI_CALORIES_DB_PATH`,
`AI_CALORIES_CHECKPOINT`, `AI_CALORIES_MODEL_URL`, `AI_CALORIES_BACKUP_DIR` and
comma-separated `AI_CALORIES_CORS_ORIGINS`. Existing environment variables win.
Keep secrets out of Git. Optional USDA import commands read `FDC_API_KEY` from
the environment; the normal API and setup do not call USDA.

Swagger: http://127.0.0.1:8000/docs • OpenAPI: http://127.0.0.1:8000/openapi.json

## Architecture and frontend handoff

Image → packaged EfficientNet-B0 inference → user confirms canonical food →
SQLite food/profile lookup → user chooses profile and grams → nutrition calculator.
The model never estimates weight or nutrition from pixels.

- `backend/inference/`: inference-only implementation extracted from the original model project.
- `backend/services/`: model loading, recipe lookup and nutrition calculation.
- `backend/database/`: schema, preserved USDA/reviewed import pipeline and reference manifests.
- `backend/database/seeds/nutrition-v0.1.0.sqlite3`: distributable seed.
- `release/`: model/database manifests, checksums and release notes.
- `docs/frontend-integration.md`: all endpoints, flows, examples and typed client.

See [frontend integration](docs/frontend-integration.md), the exported
[OpenAPI](docs/openapi.json), and [TypeScript client](docs/api-client.ts).
No frontend UI is included.

## Model and data

EfficientNet-B0, 310 classes, zero-based ordering, taxonomy `unified-food-4-v2`.
The checkpoint's embedded class map remains authoritative and unchanged.
Inference uses the original torchvision EfficientNet evaluation transform,
EXIF orientation, RGB conversion, CPU execution and uncalibrated softmax scores.
No retraining or pretrained-weight download occurs at runtime.

The original taxonomy combines 30VNFoods, UEC-Food256, VinaFood21 and
Vietnamese_StreetFood_14Class. Nutrition5k is separate and is not used here.
The source project documents one class (`food-v2-307`) without retained positive
training examples and no native VinaFood21 validation split. Training images,
logs and datasets are excluded. Dataset/model redistribution rights are not
established by this packaging work; retain original provenance when distributing.

## Nutrition snapshot and limitations

The seed contains 88 ingredients, 1,668 nutrient values, 21 nutrient categories,
88 source references, 77 foods, 77 profiles, 80 component links and 77 mappings.
All source rows and values were copied unchanged; the distributable schema fixes
`INTEGERR` to `INTEGER` and enables the correctly spelled `foreign_keys` pragma.
The local working database is not migrated or overwritten by packaging.

There are **76 `as_served_reference` profiles**, each representing a prepared food
with per-100-g USDA nutrition. Their single component represents the entire food;
the frontend edits total portion weight. They are not verified ingredient recipes.
The existing Cơm tấm profile is the one `ingredient_recipe`; its stored title
includes “test”, and it should not be advertised as a clinically validated recipe.
Users can edit ingredient weights. Additive metadata is maintained in the reviewed
`profile_types.json` registry; unmatched future records return `unreviewed`.

Sources are retained in `data_sources`, including USDA FoodData Central SR Legacy
record URLs. Regional/reviewed manifests are preserved, not automatically imported.
Missing nutrients stay `null` with `incomplete` status and missing ingredient IDs.
Do not replace these with zero. Image scores are not calibrated certainty; require
user confirmation. Only 77 of 310 model classes have nutrition mappings. Actual
recipes and preparation can differ from reference foods.

Restore a missing database with `python scripts/setup.py`. An existing database
is verified and kept, including additional reviewed data. To explicitly reset it,
stop the server and run `python scripts/setup.py --overwrite-database`; a
`.before-restore.bak` SQLite backup is created first. The command refuses to
replace a prior backup. Fresh restoration checks exact versioned counts; existing
databases may legitimately have different counts.

## Verification and roadmap

```sh
python -m unittest discover -s tests -v
python scripts/verify_fresh_clone.py
```

Tests require the installed real checkpoint. See [verification](docs/verification.md)
for evidence and remaining publication/dependency-install limitations.

Next: frontend confirmation and portion editor, reviewed coverage expansion,
explicit metadata migrations for new profiles, calibrated model evaluation,
authentication/rate limiting for public deployment, and CI across operating systems.

Release title: **v0.1.0 — Backend & Nutrition API**.
See [release notes](release/v0.1.0.md). Nothing is committed, pushed or published automatically.
