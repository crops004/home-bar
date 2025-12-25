import os
import sqlite3
from dotenv import load_dotenv
import psycopg

load_dotenv()

SQLITE_PATH = "cocktail_dev.db"

def main() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is not set. Put it in .env as DATABASE_URL=...")

    if not os.path.exists(SQLITE_PATH):
        raise SystemExit(f"Can't find {SQLITE_PATH} in {os.getcwd()}")

    sq = sqlite3.connect(SQLITE_PATH)
    sq.row_factory = sqlite3.Row

    pg = psycopg.connect(dsn)
    cur = pg.cursor()

    try:
        # -------------------------
        # 1) Categories (remap IDs)
        # -------------------------
        cats = sq.execute('SELECT id, name FROM "Categories" ORDER BY id').fetchall()
        cat_id_map: dict[int, int] = {}

        print(f"Categories: inserting {len(cats)} rows...")
        for r in cats:
            old_id = int(r["id"])
            name = r["name"]
            cur.execute(
                'INSERT INTO categories (name) VALUES (%s) '
                'ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name '
                'RETURNING id',
                (name,),
            )
            new_id = cur.fetchone()[0]
            cat_id_map[old_id] = int(new_id)

        pg.commit()

        # ----------------------------
        # 2) Subcategories (use remap)
        # ----------------------------
        subs = sq.execute('SELECT id, category_id, name FROM "Subcategories" ORDER BY id').fetchall()
        print(f"Subcategories: inserting {len(subs)} rows...")
        for r in subs:
            old_cat_id = int(r["category_id"])
            new_cat_id = cat_id_map.get(old_cat_id)
            if not new_cat_id:
                # Shouldn't happen, but safe guard
                continue

            name = r["name"]
            cur.execute(
                'INSERT INTO subcategories (category_id, name) VALUES (%s, %s) '
                'ON CONFLICT (category_id, name) DO NOTHING',
                (new_cat_id, name),
            )
        pg.commit()

        # -------------------------
        # 3) Simple lookup tables
        # -------------------------
        def migrate_lookup(sqlite_table: str, pg_table: str) -> None:
            rows = sq.execute(f'SELECT name FROM "{sqlite_table}" ORDER BY name').fetchall()
            print(f"{pg_table}: inserting {len(rows)} rows...")
            for r in rows:
                cur.execute(
                    f'INSERT INTO {pg_table} (name) VALUES (%s) ON CONFLICT (name) DO NOTHING',
                    (r["name"],),
                )
            pg.commit()

        migrate_lookup("GlassTypes", "glasstypes")
        migrate_lookup("IceOptions", "iceoptions")
        migrate_lookup("Methods", "methods")
        migrate_lookup("Units", "units")

        # -------------------------
        # 4) PossibleIngredients
        # -------------------------
        pi = sq.execute('SELECT name, category, sub_category FROM "PossibleIngredients"').fetchall()
        print(f"PossibleIngredients: inserting {len(pi)} rows...")
        for r in pi:
            cur.execute(
                'INSERT INTO possibleingredients (name, category, sub_category) VALUES (%s, %s, %s) '
                'ON CONFLICT (name, category, sub_category) DO NOTHING',
                (r["name"], r["category"], r["sub_category"]),
            )
        pg.commit()

        # -------------------------
        # 5) BarContents
        # -------------------------
        bc = sq.execute('SELECT name, category, sub_category FROM "BarContents"').fetchall()
        print(f"BarContents: inserting {len(bc)} rows...")
        for r in bc:
            cur.execute(
                'INSERT INTO barcontents (name, category, sub_category) VALUES (%s, %s, %s) '
                'ON CONFLICT (name) DO NOTHING',
                (r["name"], r["category"], r["sub_category"]),
            )
        pg.commit()

        # -------------------------
        # 6) Recipes
        # -------------------------
        recs = sq.execute('SELECT drink, Glass, Garnish, Method, Ice, Notes, Base_Spirit FROM "Recipes"').fetchall()
        print(f"Recipes: inserting {len(recs)} rows...")
        for r in recs:
            cur.execute(
                'INSERT INTO recipes (drink, "Glass", "Garnish", "Method", "Ice", "Notes", "Base_Spirit") '
                'VALUES (%s, %s, %s, %s, %s, %s, %s) '
                'ON CONFLICT (drink) DO UPDATE SET '
                '"Glass" = EXCLUDED."Glass", '
                '"Garnish" = EXCLUDED."Garnish", '
                '"Method" = EXCLUDED."Method", '
                '"Ice" = EXCLUDED."Ice", '
                '"Notes" = EXCLUDED."Notes", '
                '"Base_Spirit" = EXCLUDED."Base_Spirit"',
                (
                    r["drink"],
                    r["Glass"],
                    r["Garnish"],
                    r["Method"],
                    r["Ice"],
                    r["Notes"],
                    r["Base_Spirit"],
                ),
            )
        pg.commit()

        # -------------------------
        # 7) RecipeIngredients
        # -------------------------
        ri = sq.execute('SELECT drink, ingredient, quantity, unit FROM "RecipeIngredients"').fetchall()
        print(f"RecipeIngredients: inserting {len(ri)} rows...")
        for r in ri:
            cur.execute(
                'INSERT INTO recipeingredients (drink, ingredient, quantity, unit) VALUES (%s, %s, %s, %s)',
                (r["drink"], r["ingredient"], r["quantity"], r["unit"]),
            )
        pg.commit()

        print("✅ Migration complete.")

    finally:
        cur.close()
        pg.close()
        sq.close()

if __name__ == "__main__":
    main()
