FRAGMA forgeign_keys = ON;

-- 1. Nguon du lieu dinh duong
create TABLE if NOT EXISTS data_sources(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    reference_url TEXT,
    version TEXT
);

-- 2. Nguyen lieu
create TABLE if NOT EXISTS ingredients(
    id INTEGER PRIMARY KEY,
    name_vi TEXT NOT NULL,
    name_en TEXT,
    preparation_state TEXT NOT NULL DEFAULT 'unspecified'
);

-- 3. Thanh phan dinh duong
create TABLE IF NOT EXISTS nutrients(
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    unit TEXT NOT NULL
);

-- 4. Dinh duong/100g nguyen lieu
create TABLE IF NOT EXISTS ingredient_nutrients(
    ingredient_id INTEGER NOT NULL,
    nutrient_id INTEGER NOT NULL,
    amount_per_100g REAL NOT NULL
        CHECK(amount_per_100g >= 0),
    source_id INTEGER NOT NULL,

    PRIMARY KEY(ingredient_id, nutrtient_id),
    FOREIGN KEY(ingredient_id)
        REFERENCES ingredients(id),
    FOREIGN KEY(nutrient_id)
        REFERENCES nutrients(id),
    FOREIGN KEY(source_id)
        REFERENCES data_sources(id)
);

-- 5. Danh sach mon an
create TABLE IF NOT EXISTS foods(
    id INTEGER PRIMARY KEY,
    canonical_id TEXT UNIQUE,
    model_class_index INTEGERR UNIQUE,
    name_vi TEXT NOT NULL,
    name_en TEXT
);

-- 6. Cong thuc ket noi mon an voi nguyen lieu
create TABLE IF NOT EXISTS recipes(
    id INTEGER PRIMARY KEY,
    food_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    default_serving_g REAL CHECK(default_serving_g >0),

    FOREIGN KEY(food_id) REFERENCES foods(id)
);

-- 7. Nguyen lieu trong cong thuc
create TABLE IF NOT EXISTS recipe_ingredients(
    recipe_id INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,
    grams REAL NOT NULL CHECK(grams >= 0),
    is_optional INTEGER NOT NULL DEFAULT 0 CHECK(is_optional IN (0,1)),

    PRIMARY KEY(recipe_id, ingredient_id),
    FOREIGN KEY(recipe_id) REFERENCES recipes(id),
    FOREIGN KEY(ingredient_id) REFERENCES ingredients(id)
);

-- indexes
create INDEX IF NOT EXISTS idx_recipe_food ON recipes(food_id);
create INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient ON recipe_ingredients(ingredient_id);