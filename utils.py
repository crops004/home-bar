import os
from typing import Optional, Any, Sequence, cast

from flask import g, has_request_context

# Postgres driver (Neon)
import psycopg
from psycopg.rows import dict_row


class DBConn:
    """
    Wrapper around a Postgres connection so the rest of your app
    can keep calling: conn.execute(sql, params), conn.commit(), conn.rollback(), conn.close()
    """

    def __init__(self, conn: Any):
        self._conn = conn

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        return self._conn.execute(sql, params)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


def _create_connection() -> DBConn:
    """
    Create a Postgres (Neon) connection wrapped in DBConn.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is required for this Postgres-only app configuration.")
    conn = cast(Any, psycopg.connect(dsn))
    conn.row_factory = dict_row
    print("[DB] Using POSTGRES via DATABASE_URL (Neon)")
    return DBConn(conn)


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
            cursor = conn.execute("SELECT id FROM Categories WHERE name = %s", (cat,))
            cat_row = cursor.fetchone()
            if not cat_row:
                lists["subcategories"][cat] = []
                continue
            cat_id = cat_row["id"]
            subcategories = conn.execute(
                "SELECT name FROM Subcategories WHERE category_id = %s ORDER BY name",
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
