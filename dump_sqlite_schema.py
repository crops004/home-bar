import sqlite3
from pathlib import Path

DB_FILE = "cocktail_dev.db"  # change if your file name is different
OUT_FILE = "schema_sqlite.sql"

def main():
    db_path = Path(DB_FILE)
    if not db_path.exists():
        raise SystemExit(f"Can't find {DB_FILE} in {Path.cwd()}. "
                         f"Update DB_FILE to the correct name/path.")

    conn = sqlite3.connect(str(db_path))
    try:
        # This returns CREATE TABLE statements etc.
        rows = conn.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE sql IS NOT NULL "
            "ORDER BY type='table' DESC, name ASC"
        ).fetchall()

        schema = ";\n\n".join(r[0] for r in rows if r[0].strip()) + ";\n"
        Path(OUT_FILE).write_text(schema, encoding="utf-8")
        print(f"Wrote {OUT_FILE} ({len(rows)} objects) from {DB_FILE}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
