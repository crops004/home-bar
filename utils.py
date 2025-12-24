import os
import sqlite3
from typing import Optional, Any, Sequence, cast

from flask import g, has_request_context

# Postgres driver (Neon)
import psycopg
from psycopg.rows import dict_row


def _is_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def _sqlite_database_path() -> str:
    """Local/dev fallback (file-based)."""
    if os.environ.get("RENDER") == "true":
        # This is still ephemeral on Render, but we won't use it once DATABASE_URL is set.
        return "cocktail_app.db"
    return "cocktail_dev.db"


def _rewrite_sql_for_postgres(sql: str) -> str:
    """
    Minimal SQL rewrites so your existing SQLite-style SQL keeps working.

    - Convert SQLite parameter placeholders '?' -> '%s'
    - Convert SQLite 'INSERT OR IGNORE' -> Postgres 'INSERT ... ON CONFLICT DO NOTHING'
      (Works only when a unique constraint exists on the target table/columns.)
    """
    s = sql

    # Placeholder conversion: ? -> %s
    # (Assumes you are using ? only for params, not in string literals.)
    s = s.replace("?", "%s")

    # SQLite upsert ignore
    # Example: INSERT OR IGNORE INTO PossibleIngredients (...) VALUES (...)
    # Becomes: INSERT INTO PossibleIngredients (...) VALUES (...) ON CONFLICT DO NOTHING
    if "INSERT OR IGNORE" in s.upper():
        # preserve original casing by doing a case-insensitive approach:
        s = s.replace("INSERT OR IGNORE", "INSERT")
        s = s.replace("insert or ignore", "insert")
        # Add ON CONFLICT DO NOTHING at the end if not already present
        if "ON CONFLICT" not in s.upper():
            s = s.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return s


class DBConn:
    """
    Wrapper that normalizes SQLite and Postgres connections so the rest of your app
    can keep calling: conn.execute(sql, params), conn.commit(), conn.rollback(), conn.close()
    """

    def __init__(self, kind: str, conn: Any):
        self.kind = kind
        self._conn = conn

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        if self.kind == "postgres":
            sql = _rewrite_sql_for_postgres(sql)
            return self._conn.execute(sql, params)
        # sqlite
        return self._conn.execute(sql, params)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


def _create_connection() -> DBConn:
    """
    Create either a Postgres (Neon) or SQLite connection, wrapped in DBConn.
    """
    if _is_postgres():
        dsn = os.environ["DATABASE_URL"]
        # Neon requires SSL; sslmode=require in DATABASE_URL is normal.  :contentReference[oaicite:4]{index=4}
        conn = cast(Any, psycopg.connect(dsn))
        conn.row_factory = dict_row
        print("[DB] Using POSTGRES via DATABASE_URL (Neon)")
        return DBConn("postgres", conn)


    # SQLite fallback (local dev)
    path = os.path.abspath(_sqlite_database_path())
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    print(f"[DB] Using SQLITE at {path}")
    return DBConn("sqlite", conn)


def get_db_connection() -> DBConn:
    """
    Return a DB connection, reusing the same connection within a request.
    """
    if has_request_context():
        if "db_connection" not in g:
            g.db_connection = _create_connection()
        return g.db_connection
    return _create_connection()


def close_db_connection(exception: Optional[BaseException] = None) -> None:
    """
    Close the per-request DB connection, if one exists.
    """
    if not has_request_context():
        return

    conn = g.pop("db_connection", None)
    if conn is not None:
        conn.close()


def load_lists() -> dict:
    """
    Load reference lists from the database.
    """
    conn = get_db_connection()
    should_close = not has_request_context()

    lists = {
        "categories": [],
        "subcategories": {},
        "glass_types": [],
        "methods": [],
        "ice_options": [],
        "units": [],
    }

    try:
        categories = conn.execute("SELECT name FROM Categories ORDER BY name").fetchall()
        lists["categories"] = [row["name"] for row in categories]

        for cat in lists["categories"]:
            cursor = conn.execute("SELECT id FROM Categories WHERE name = ?", (cat,))
            cat_row = cursor.fetchone()
            if not cat_row:
                lists["subcategories"][cat] = []
                continue
            cat_id = cat_row["id"]
            subcategories = conn.execute(
                "SELECT name FROM Subcategories WHERE category_id = ? ORDER BY name",
                (cat_id,),
            ).fetchall()
            lists["subcategories"][cat] = [row["name"] for row in subcategories]

        glass_types = conn.execute("SELECT name FROM GlassTypes ORDER BY name").fetchall()
        lists["glass_types"] = [row["name"] for row in glass_types]

        methods = conn.execute("SELECT name FROM Methods ORDER BY name").fetchall()
        lists["methods"] = [row["name"] for row in methods]

        ice_options = conn.execute("SELECT name FROM IceOptions ORDER BY name").fetchall()
        lists["ice_options"] = [row["name"] for row in ice_options]

        units = conn.execute("SELECT name FROM Units ORDER BY name").fetchall()
        lists["units"] = [row["name"] for row in units]

        ingredients = conn.execute("SELECT * FROM PossibleIngredients").fetchall()
        lists["ingredients"] = {row["name"]: row for row in ingredients}
    finally:
        if should_close:
            conn.close()

    return lists
