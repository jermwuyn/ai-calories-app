# Verification report — v0.1.0

Verified on Windows with Python 3.11 using the supplied `ai` environment.

## Passed

- Existing reviewed-import suite: 3 tests passed before modifications.
- Final suite: **8 tests passed**, including the preserved 3 tests.
- Isolated Git-visible source copy under a temporary directory: missing DB restored
  solely from packaged seed, model installed from a separate release asset, setup
  run twice, all 8 tests passed. No original database or sibling model code used.
- Missing checkpoint setup exits nonzero; missing checkpoint prediction returns
  503 with setup instructions. Invalid checksum rejected before loading.
- Download streaming branch tested using the actual checkpoint bytes with a mocked
  HTTP transport; this does not establish public asset availability.
- SHA-256 matched the original 64,354,977-byte checkpoint.
- Actual EfficientNet inference through `/predict`, 310 embedded classes,
  taxonomy `unified-food-4-v2`, all 77 canonical ID/index mappings verified.
- Snapshot: 88 ingredients, 1,668 nutrient rows, 21 categories, 88 sources,
  77 foods, 77 profiles, 80 component links, 77 mappings, integrity `ok`, no FK errors.
- Every row in all seven seed tables compared equal to the current source database.
  Only the seed's declared model index type changes from `INTEGERR` to `INTEGER`.
- 76 prepared-food reference profiles and one ingredient recipe; recipe lookup,
  nutrient scaling and missing nutrient nulls; existing response fields retained.
- CORS preflight allowed Vite and rejected an unconfigured origin; invalid uploads
  and invalid API requests exercised; Vietnamese text round-tripped on Windows.
- Existing DB preserved, explicit overwrite creates a restorable backup, setup
  idempotence checked using byte-for-byte DB comparison.
- Live Uvicorn startup on loopback returned HTTP 200 and expected root JSON.
- PyPI dependency resolution (`pip install --dry-run --ignore-installed`) succeeded
  for the pinned requirements on Python 3.11 Windows. Report is local/ignored.
- `git diff --check` passed. Staged list inspected: empty. No commit/push/tag.
  Git-visible file size review found no files above 1 MiB; model/live DB remain
  ignored. Targeted credential-pattern scan found no matches. USDA source fields
  and manifests contain food reference data; no personal records were observed.

## Verification boundaries

The isolated-copy test uses installed interpreter dependencies and a local release
asset. A full install into an empty environment has not been run. PyPI resolution
is verified, but transitive dependencies are not locked. Only Windows was executed.
The TypeScript client is a handoff example, not a built frontend.

The release asset is prepared locally; the task does not publish it. The public
GitHub download path must be verified after upload before claiming an end-to-end
public fresh-clone installation. Default setup fails clearly if that URL is not
available. Real predictions used a synthetic image to verify execution and format;
this is not an accuracy evaluation.

Starlette emits a deprecation warning for its httpx test transport; tests pass
with pinned httpx 0.28.1. No inference or nutrition failure is hidden by that warning.

## Reviewable files

Created: `.env.example`, `requirements.txt`, `backend/config.py`,
`backend/inference/`, `backend/database/profile_types.json`, the versioned SQLite
seed, `scripts/setup.py`, `scripts/verify_fresh_clone.py`, `tests/test_packaging.py`,
`docs/frontend-integration.md`, `docs/api-client.ts`, captured `docs/examples/`,
`release/model.json`, `release/database.json`, `release/SHA256SUMS`, and release notes.

Modified: README, ignore rules, runtime settings in main/services, schema typo
fixes and portable paths in database utilities. The previously untracked OpenAPI
export was regenerated from the current app. Existing modified USDA manifest and
reviewed-import/reference files were preserved, including their existing tests.

The checkpoint in ignored `checkpoints/best.pth` is the upload-ready asset.
See `release/v0.1.0.md` for release steps and `README.md` for setup commands.
