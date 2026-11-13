# Frontend integration

Start with Python 3.11: `python scripts/setup.py`, then
`python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`.
Set Vite's `VITE_API_BASE_URL=http://127.0.0.1:8000` in your frontend environment.
Use [api-client.ts](api-client.ts) with Vite's `vite/client` types enabled.

CORS defaults to `http://localhost:5173` and `http://127.0.0.1:5173`.
Configure exact frontend origins in backend `AI_CALORIES_CORS_ORIGINS` (comma
separated), then restart. GET/POST and Content-Type are allowed; credentials are
not used. Do not set multipart Content-Type yourself: the browser adds its boundary.

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | App name and running status (not model readiness) |
| GET | `/ingredients` | Ingredient IDs, Vietnamese/English names, preparation states |
| POST | `/predict?top_k=3` | Multipart `file`; integer top_k 1–5 |
| GET | `/foods/by-canonical/{canonical_id}` | Confirmed food and available profiles |
| GET | `/recipes/{recipe_id}` | Profile metadata and default components |
| POST | `/recipes/{recipe_id}/calculate` | Calculate supplied components without saving |
| GET | `/docs`, `/redoc`, `/openapi.json` | Interactive and machine-readable API docs |

## Recognition and confirmation

```ts
const result = await api.predict(file, 3);
// Render candidates; wait for the user's choice, then:
const food = await api.food(chosenCanonicalId);
// Wait for a profile selection, then load:
const recipe = await api.recipe(chosenRecipeId);
```

Upload JPEG, PNG or WebP, at most 10 MiB and 20 megapixels:

```sh
curl -F "file=@meal.jpg" "http://127.0.0.1:8000/predict?top_k=3"
```

[Real prediction response](examples/prediction.json) was captured from the actual
checkpoint using a synthetic 224×224 RGB image (120,80,40). It demonstrates the
wire format and real scores, not food-recognition accuracy. Each prediction has
`model_index`, `canonical_id`, nullable names, `display_name`, and `score`.
The response includes taxonomy, `requires_confirmation: true`,
`score_type: "uncalibrated_softmax"`, and a nutrition status requiring confirmation.
Never infer portion size or nutrition from these scores.

Use the canonical ID, not translated display text, for food lookup. A valid but
unmapped class returns HTTP 200, `mapped: false`, `food: null`, `recipes: []` and
`nutrition_status: "nutrition_unavailable"`. Do not invent a recipe. Mapped food
lookup returns candidates, not automatic confirmation. See [food response](examples/food.json)
and [Cơm tấm recipe](examples/recipe.json).

## Profile behavior and calculation

Both food candidate records and recipe details now include `profile_type`:

- `as_served_reference`: one component represents the whole prepared food.
  Keep its ingredient ID and send the user's total portion grams as its weight.
  Do not display it as a list of actual ingredients or invent a composition.
- `ingredient_recipe`: show editable individual component grams. Omit an ingredient
  to remove it; added ingredients must use IDs from `/ingredients`.
- `unreviewed`: a future record without matching reviewed metadata. Do not assume
  a profile type; require review before presenting it as a verified profile.

The generic calculation endpoint preserves its existing ability to accept any
valid component list, including substitutions. Frontend behavior must preserve the
prepared-food distinction. Returned profile metadata describes the selected
stored profile; it does not certify arbitrary substitutions.

For example, the prepared-food profile at `/recipes/2` can use its sole component
at 200 grams. For Cơm tấm, send [this captured request](examples/calculate-request.json):

```json
{"components":[{"ingredient_id":1,"grams":180},{"ingredient_id":2,"grams":100},{"ingredient_id":3,"grams":40},{"ingredient_id":4,"grams":50}]}
```

Use the actual IDs and quantities from the selected recipe. The authoritative
[captured response](examples/calculate-response.json) includes profile identity,
`is_customized`, and `nutrition` with `total_grams`, ingredient portions and a map
of 21 nutrient categories. Each nutrient has `name`, nullable `amount`, `unit`,
`status` (`complete` or `incomplete`) and `missing_ingredient_ids`.
Calculations scale stored amounts per 100 g, sum supplied portions and round
reported amounts to two decimals. Optional ingredients are included only if sent.
There is no save endpoint; calculations do not mutate the database.

Display `null` as “Unavailable” or “Incomplete”; retain the unit and explain which
ingredients lack data. Never show zero or a partial sum as a complete total.

## Errors

The client throws `ApiError` with HTTP status and the original `detail` (which may
be a string or validation-error array). Handle network/CORS failures separately;
those reject fetch without an HTTP response.

- 400: corrupt/empty image, duplicate/unknown ingredients or invalid calculation.
- 404: recipe does not exist. Unmapped canonical IDs instead return 200 as above.
- 413: upload over size or pixel limits.
- 415: unsupported declared media type or decoded image format.
- 422: invalid path/query/body, nonpositive grams, empty components or missing file.
- 500: missing database; run setup and check backend configuration.
- 503: missing or checksum-invalid checkpoint; follow setup instructions in detail.

The original fields/routes remain intact; profile metadata is additive. OpenAPI
is exported in [openapi.json](openapi.json). Existing dynamically returned response
schemas are not fully typed by FastAPI; use the typed client and captured JSON
examples alongside OpenAPI for response shapes.
