import os
import sqlite3
from typing import List

import psycopg
from dotenv import load_dotenv

load_dotenv()  # loads .env into os.environ

SQLITE_PATH = "cocktail_dev.db"  # adjust if needed

# Migrate in FK-safe order
TABLES: List[str] = [
    "Categories",
    "Subcategories",
    "GlassTypes",
    "IceOptions",
    "Methods",
    "Units",
    "PossibleIngredients",
    "BarContents",
    "Recipes",
    "RecipeIngredients",
]

def percents(n: int) -> str:
    return ", ".join(["%s"] * n)

def main() -> None:
    pg_dsn = os.environ.get("DATABASE_URL")
    if not pg_dsn:
        raise SystemExit(
            "DATABASE_URL is not set.\n"
            "Fix: add it to .env (DATABASE_URL=...) or set $env:DATABASE_URL in PowerShell."
        )

    if not os.path.exists(SQLITE_PATH):
        raise SystemExit(f"Can't find {SQLITE_PATH} in {os.getcwd()}")

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = psycopg.connect(pg_dsn)
    pg_cur = pg_conn.cursor()

    try:
        for table in TABLES:
            # Check SQLite table exists
            t = sqlite_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not t:
                print(f"Skipping {table} (not found in SQLite)")
                continue

            rows = sqlite_conn.execute(f'SELECT * FROM "{table}"').fetchall()
            if not rows:
                print(f"{table}: 0 rows")
                continue

            cols = list(rows[0].keys())
            col_list = ", ".join([f'"{c}"' for c in cols])

            insert_sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({percents(len(cols))}) ON CONFLICT DO NOTHING'

            print(f"{table}: inserting {len(rows)} rows...")

            for r in rows:
                values = [r[c] for c in cols]
                pg_cur.execute(insert_sql, values)  # type: ignore[arg-type]

            pg_conn.commit()

        print("Migration complete.")
    finally:
        pg_cur.close()
        pg_conn.close()
        sqlite_conn.close()

if __name__ == "__main__":
    main()
