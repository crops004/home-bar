import os
import sqlite3
from typing import Optional
from flask import g, has_request_context


def _database_path() -> str:
    """Return the correct database filename for the current environment."""
    if os.environ.get("RENDER") == "true":
        return "cocktail_app.db"
    return "cocktail_dev.db"


def _create_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_database_path())
    conn.row_factory = sqlite3.Row
    return conn


def get_db_connection() -> sqlite3.Connection:
    """
    Return a SQLite connection, reusing the same connection within a request.

    When called outside a request context (e.g., command-line scripts), a fresh
    connection is returned for the caller to manage.
    """
    if has_request_context():
        if "db_connection" not in g:
            g.db_connection = _create_connection()
        return g.db_connection
    return _create_connection()


def close_db_connection(exception: Optional[BaseException] = None) -> None:
    """
    Close the per-request SQLite connection, if one exists.

    Flask automatically calls this via teardown handlers; views can also invoke
    it explicitly when they finish with the database.
    """
    if not has_request_context():
        return

    conn = g.pop("db_connection", None)
    if conn is not None:
        conn.close()


def load_lists() -> dict:
    """
    Load reference lists from the database.

    When called inside a request the shared connection is reused; when called
    outside a request (e.g., at startup) a temporary connection is created and
    closed before returning.
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
        categories = conn.execute(
            "SELECT name FROM Categories ORDER BY name"
        ).fetchall()
        lists["categories"] = [row["name"] for row in categories]

        for cat in lists["categories"]:
            cursor = conn.execute(
                "SELECT id FROM Categories WHERE name = ?", (cat,)
            )
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

        glass_types = conn.execute(
            "SELECT name FROM GlassTypes ORDER BY name"
        ).fetchall()
        lists["glass_types"] = [row["name"] for row in glass_types]

        methods = conn.execute("SELECT name FROM Methods ORDER BY name").fetchall()
        lists["methods"] = [row["name"] for row in methods]

        ice_options = conn.execute(
            "SELECT name FROM IceOptions ORDER BY name"
        ).fetchall()
        lists["ice_options"] = [row["name"] for row in ice_options]

        units = conn.execute("SELECT name FROM Units ORDER BY name").fetchall()
        lists["units"] = [row["name"] for row in units]

        ingredients = conn.execute("SELECT * FROM PossibleIngredients").fetchall()
        lists["ingredients"] = {row["name"]: row for row in ingredients}
    finally:
        if should_close:
            conn.close()

    return lists
