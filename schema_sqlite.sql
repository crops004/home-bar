CREATE TABLE "BarContents" (
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        sub_category TEXT,
        PRIMARY KEY (name)
    );

CREATE TABLE Categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

CREATE TABLE GlassTypes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

CREATE TABLE IceOptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

CREATE TABLE Methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

CREATE TABLE PossibleIngredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                sub_category TEXT,
                UNIQUE(name, category, sub_category)
            );

CREATE TABLE IngredientPurchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_id INTEGER NOT NULL,
                purchase_date TEXT NOT NULL,
                location TEXT,
                size_value REAL NOT NULL,
                size_unit TEXT NOT NULL,
                price REAL NOT NULL,
                notes TEXT,
                FOREIGN KEY (ingredient_id) REFERENCES PossibleIngredients(id) ON DELETE CASCADE
            );

CREATE TABLE "RecipeIngredients" (
"drink" TEXT,
  "ingredient" TEXT,
  "quantity" TEXT,
  "unit" TEXT
);

CREATE TABLE "Recipes" (
"drink" TEXT,
  "Glass" TEXT,
  "Garnish" TEXT,
  "Method" TEXT,
  "Ice" TEXT,
  "Notes" TEXT,
  "Base_Spirit" TEXT
);

CREATE TABLE Subcategories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(category_id, name),
                FOREIGN KEY (category_id) REFERENCES Categories(id) ON DELETE CASCADE
            );

CREATE TABLE Units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

CREATE TABLE sqlite_sequence(name,seq);
