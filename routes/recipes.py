from collections import defaultdict
import time

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app

from utils import get_db_connection, load_lists, close_db_connection
from helpers import get_drinks_can_make

recipes_bp = Blueprint("recipes", __name__)

SPIRIT_CATEGORIES = [
    "Absinthe",
    "Aperitif",
    "Bitters",
    "Brandy",
    "Cognac",
    "Digestif",
    "Fortified Wine",
    "Gin",
    "Liqueur",
    "Mezcal",
    "Rum",
    "Tequila",
    "Vermouth",
    "Vodka",
    "Whiskey",
]


def _get_lists():
    """Fetch shared option lists from the application config, refreshing if needed."""
    cached = current_app.config.get("LISTS")
    if not cached:
        cached = load_lists()
        current_app.config["LISTS"] = cached
    return cached


def _build_category_lookup(lists_data: dict) -> dict:
    """Map subcategory -> parent category, also keep category names."""
    category_lookup = {}
    subcategories = lists_data.get("subcategories", {})
    for category, subs in subcategories.items():
        category_lookup[category.lower()] = category
        for sub in subs:
            category_lookup[sub.lower()] = category
    for category in lists_data.get("categories", []):
        category_lookup.setdefault(category.lower(), category)
    return category_lookup


def _get_spirit_name_set(conn) -> set[str]:
    """
    Build a set of ingredient names that count as "spirits" for summary purposes.

    This avoids doing expensive LOWER(name) joins for every recipe page load.
    Cached in app.config["LISTS"]["_spirit_name_set"].
    """
    lists_data = _get_lists()
    cached = lists_data.get("_spirit_name_set")
    if cached is not None:
        return cached

    spirit_cats = {s.lower() for s in SPIRIT_CATEGORIES}

    # Pull all possible ingredients once and filter in Python (fast enough and cached)
    rows = conn.execute(
        "SELECT name, category, sub_category FROM possibleingredients"
    ).fetchall()

    spirit_names: set[str] = set()
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        cat = (r.get("category") or "").strip().lower()
        sub = (r.get("sub_category") or "").strip().lower()
        if cat in spirit_cats or sub in spirit_cats:
            spirit_names.add(name.lower())

    lists_data["_spirit_name_set"] = spirit_names
    current_app.config["LISTS"] = lists_data
    return spirit_names


@recipes_bp.route("/recipe", methods=["GET", "POST"])
def recipes():
    lists_data = _get_lists()
    conn = get_db_connection()

    t_total = time.perf_counter()
    try:
        if request.method == "POST":
            drink = request.form["drink"].strip().title()
            glass = request.form["glass"]
            garnish = request.form["garnish"]
            method = request.form["method"]
            ice = request.form["ice"]
            notes = request.form["notes"]
            base_spirit = request.form["base_spirit"]

            conn.execute(
                "INSERT INTO Recipes (drink, glass, garnish, method, ice, notes, base_spirit) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (drink, glass, garnish, method, ice, notes, base_spirit),
            )

            i = 0
            while f"ingredient_{i}" in request.form:
                ingredient = request.form[f"ingredient_{i}"]
                quantity = request.form[f"quantity_{i}"]
                unit = request.form[f"unit_{i}"]
                conn.execute(
                    "INSERT INTO RecipeIngredients (drink, ingredient, quantity, unit) VALUES (?, ?, ?, ?)",
                    (drink, ingredient, quantity, unit),
                )
                i += 1

            conn.commit()
            return redirect(url_for("recipes.recipes"))

        # ---- GET (fast path) ----
        category_lookup = _build_category_lookup(lists_data)

        # Cache spirit-name lookup set (lowercased names)
        t0 = time.perf_counter()
        spirit_name_set = _get_spirit_name_set(conn)
        print(f"[PERF] build spirit_name_set (cached): {(time.perf_counter() - t0) * 1000:.0f} ms")

        # 1) Fetch recipe list (small query)
        t0 = time.perf_counter()
        raw_recipes = conn.execute(
            """
            SELECT
              r.drink,
              COALESCE(r.base_spirit, '') AS base_spirit
            FROM recipes r
            ORDER BY
              CASE WHEN r.base_spirit IS NULL OR r.base_spirit = '' THEN 1 ELSE 0 END,
              lower(r.base_spirit),
              lower(r.drink)
            """
        ).fetchall()
        print(f"[PERF] recipes list: {(time.perf_counter() - t0) * 1000:.0f} ms, rows={len(raw_recipes)}")

        # 2) Aggregate ingredients per drink (single query; no join to possibleingredients)
        t0 = time.perf_counter()
        ing_rows = conn.execute(
            """
            SELECT
              drink,
              COALESCE(
                string_agg(DISTINCT NULLIF(trim(ingredient), ''), ' • ' ORDER BY NULLIF(trim(ingredient), '')),
                ''
              ) AS ingredient_summary
            FROM recipeingredients
            GROUP BY drink
            """
        ).fetchall()
        print(f"[PERF] ingredients aggregate: {(time.perf_counter() - t0) * 1000:.0f} ms, rows={len(ing_rows)}")

        ingredient_summary_by_drink = {r["drink"]: (r["ingredient_summary"] or "") for r in ing_rows}

        # 3) Spirit summary per drink (computed in Python from recipeingredients, using cached spirit names)
        #    Pull only (drink, ingredient) once
        t0 = time.perf_counter()
        ri_rows = conn.execute(
            "SELECT drink, ingredient FROM recipeingredients ORDER BY id"
        ).fetchall()
        print(f"[PERF] recipeingredients scan: {(time.perf_counter() - t0) * 1000:.0f} ms, rows={len(ri_rows)}")

        spirits_by_drink = defaultdict(list)
        seen_spirits = defaultdict(set)

        for r in ri_rows:
            drink = r["drink"]
            ing = (r["ingredient"] or "").strip()
            if not ing:
                continue
            key = ing.lower()
            if key in spirit_name_set:
                if ing not in seen_spirits[drink]:
                    spirits_by_drink[drink].append(ing)
                    seen_spirits[drink].add(ing)

        # 4) Availability (this may be slow depending on implementation)
        t0 = time.perf_counter()
        # can_make_entries = get_drinks_can_make()
        # can_make_set = {entry["drink"] for entry in can_make_entries}
        can_make_set = set()
        # print(f"[PERF] get_drinks_can_make: {(time.perf_counter() - t0) * 1000:.0f} ms, rows={len(can_make_entries)}")

        # 5) Build view model
        all_recipes = []
        for row in raw_recipes:
            drink = row["drink"]
            base_spirit = (row["base_spirit"] or "").strip()

            resolved_category = category_lookup.get(base_spirit.lower(), base_spirit or "Unknown")
            resolved_category = (resolved_category or "Unknown").strip() or "Unknown"

            all_recipes.append(
                {
                    "drink": drink,
                    "base_spirit": base_spirit,
                    "base_spirit_category": resolved_category,
                    "spirit_summary": " • ".join(spirits_by_drink.get(drink, [])),
                    "ingredient_summary": (ingredient_summary_by_drink.get(drink, "") or "").strip(),
                    "available": drink in can_make_set,
                }
            )

        all_recipes.sort(
            key=lambda item: (
                1 if item["base_spirit_category"].lower() == "unknown" else 0,
                item["base_spirit_category"].lower(),
                item["drink"].lower(),
            )
        )

        print(f"[PERF] total /recipe/recipe: {(time.perf_counter() - t_total) * 1000:.0f} ms")

        return render_template(
            "recipes.html",
            all_recipes=all_recipes,
            lists=lists_data,
            spirit_categories=SPIRIT_CATEGORIES,
        )

    finally:
        close_db_connection()


@recipes_bp.route("/<string:drink>", methods=["GET"])
def get_recipe(drink):
    conn = get_db_connection()
    try:
        recipe = conn.execute("SELECT * FROM Recipes WHERE drink = ?", (drink,)).fetchone()
        ingredients = conn.execute(
            """
            SELECT
                ri.ingredient,
                ri.quantity,
                ri.unit,
                COALESCE(pi.category, '') AS category,
                COALESCE(pi.sub_category, '') AS sub_category
            FROM RecipeIngredients AS ri
            LEFT JOIN PossibleIngredients AS pi
                ON LOWER(pi.name) = LOWER(ri.ingredient)
            WHERE ri.drink = ?
            ORDER BY ri.id
            """,
            (drink,),
        ).fetchall()
    finally:
        close_db_connection()

    if recipe:
        recipe_data = {
            "name": recipe["drink"],
            "glass": recipe["glass"],
            "garnish": recipe["garnish"],
            "method": recipe["method"],
            "ice": recipe["ice"],
            "notes": recipe["notes"],
            "base_spirit": recipe["base_spirit"],
            "ingredients": [
                {
                    "ingredient": ing["ingredient"],
                    "quantity": ing["quantity"],
                    "unit": ing["unit"],
                    "category": ing["category"],
                    "sub_category": ing["sub_category"],
                }
                for ing in ingredients
            ],
        }
        return jsonify(recipe_data)

    return jsonify({"error": "Recipe not found"}), 404


@recipes_bp.route("/delete_recipe/<string:drink>", methods=["DELETE"])
def delete_recipe(drink):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM Recipes WHERE drink = ?", (drink,))
        conn.execute("DELETE FROM RecipeIngredients WHERE drink = ?", (drink,))
        conn.commit()
    finally:
        close_db_connection()
    return jsonify({"message": "Recipe deleted successfully"}), 200


@recipes_bp.route("/edit_recipe/<drink>", methods=["POST"])
def edit_recipe(drink):
    data = request.get_json()
    original_drink = data.get("original_drink")
    new_drink = data.get("drink")
    glass = data.get("glass")
    garnish = data.get("garnish")
    method = data.get("method")
    ice = data.get("ice")
    notes = data.get("notes")
    base_spirit = data.get("base_spirit")
    ingredients = data.get("ingredients", [])

    if not original_drink or not new_drink:
        return jsonify({"success": False, "message": "Drink name is required."}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE Recipes
            SET drink = ?, glass = ?, garnish = ?, method = ?, ice = ?, notes = ?, base_spirit = ?
            WHERE drink = ?
            """,
            (
                new_drink,
                glass or None,
                garnish or None,
                method or None,
                ice or None,
                notes or None,
                base_spirit,
                original_drink,
            ),
        )

        conn.execute("DELETE FROM RecipeIngredients WHERE drink = ?", (original_drink,))

        target_drink = new_drink if new_drink != original_drink else original_drink
        for ingredient in ingredients:
            conn.execute(
                "INSERT INTO RecipeIngredients (drink, ingredient, quantity, unit) VALUES (?, ?, ?, ?)",
                (target_drink, ingredient["ingredient"], ingredient["quantity"], ingredient["unit"]),
            )

        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        close_db_connection()
