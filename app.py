from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
    session,
    current_app,
    g,
    abort,
)
from routes import drink_maker, bar, recipes
from utils import get_db_connection, load_lists, close_db_connection
from helpers import fetch_drinks_missing_ingredients, fetch_drinks_with_base
from config import Config
import time
import logging
from datetime import date
from werkzeug.exceptions import BadRequest, BadRequestKeyError

UNIT_TO_ML = {
    "ml": 1.0,
    "milliliter": 1.0,
    "millilitre": 1.0,
    "l": 1000.0,
    "liter": 1000.0,
    "litre": 1000.0,
    "oz": 29.5735,
    "fl oz": 29.5735,
    "floz": 29.5735,
    "fluid ounce": 29.5735,
    "gal": 3785.41,
    "gallon": 3785.41,
    "qt": 946.353,
    "quart": 946.353,
    "pt": 473.176,
    "pint": 473.176,
    "cup": 236.588,
    "tbsp": 14.7868,
    "tablespoon": 14.7868,
    "tsp": 4.92892,
    "teaspoon": 4.92892,
}

PURCHASE_UNITS = [
    {"value": "ml", "label": "ml"},
    {"value": "l", "label": "L"},
    {"value": "oz", "label": "oz"},
    {"value": "gallon", "label": "gallon"},
]


def _normalize_unit(unit: str) -> str:
    u = (unit or "").strip().lower()
    u = u.replace(".", "")
    u = u.replace("fluid ounces", "fluid ounce")
    u = u.replace("fluid ounce", "fl oz")
    u = u.replace("fl oz", "fl oz")
    u = u.replace("floz", "fl oz")
    u = " ".join(u.split())
    if u.endswith("s") and u[:-1] in UNIT_TO_ML:
        u = u[:-1]
    return u


def _convert_to_ml(value: float, unit: str) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    factor = UNIT_TO_ML.get(_normalize_unit(unit))
    if not factor:
        return None
    return v * factor


def _parse_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _format_size_value(value: float | int | None) -> str:
    n = _parse_float(value)
    if n is None:
        return ""
    if n.is_integer():
        return str(int(n))
    return f"{n:.4f}".rstrip("0").rstrip(".")


def _display_unit(unit: str) -> str:
    normalized = _normalize_unit(unit)
    if normalized == "l":
        return "L"
    return (unit or "").strip()


def _ensure_ingredient_purchases_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS IngredientPurchases (
            id SERIAL PRIMARY KEY,
            ingredient_id INTEGER NOT NULL REFERENCES PossibleIngredients(id) ON DELETE CASCADE,
            purchase_date TEXT NOT NULL,
            location TEXT,
            size_value REAL NOT NULL,
            size_unit TEXT NOT NULL,
            price REAL NOT NULL,
            notes TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ingredient_purchases_ingredient_id ON IngredientPurchases (ingredient_id)"
    )
    conn.commit()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = app.config["SECRET_KEY"]

    app.config["LISTS"] = load_lists()

    app.register_blueprint(drink_maker.drink_maker_bp, url_prefix="/drink")
    app.register_blueprint(bar.bar_bp, url_prefix="/bar")
    app.register_blueprint(recipes.recipes_bp, url_prefix="/recipe")

    @app.teardown_appcontext
    def teardown_db(exception=None):
        close_db_connection(exception)

    @app.context_processor
    def inject_debug_toggle():
        # Global flag from config
        show_from_config = bool(current_app.config.get("SHOW_VIEWPORT_DEBUG", False))
        # Optional per-request override via query param: ?debug=1 / true / on
        arg = request.args.get("debug")
        if arg is not None:
            show = arg.lower() in {"1", "true", "on", "yes"}
        else:
            show = show_from_config
        return {"SHOW_VIEWPORT_DEBUG": show}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            submitted_username = request.form["username"]
            submitted_password = request.form["password"]
            expected_username = current_app.config.get("ADMIN_USERNAME")
            expected_password = current_app.config.get("ADMIN_PASSWORD")

            if (
                submitted_username == expected_username
                and submitted_password == expected_password
            ):
                session["logged_in"] = True
                return redirect(url_for("home"))

            flash("Invalid credentials")

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.pop("logged_in", None)
        flash("Logged out")
        return redirect(url_for("login"))

    @app.before_request
    def _perf_start():
        g._t0 = time.perf_counter()

    @app.after_request
    def _perf_log(response):
        try:
            dt_ms = (time.perf_counter() - g._t0) * 1000
            # Only log the slow endpoints (adjust threshold as you want)
            if request.path.startswith("/recipe/recipe") or dt_ms > 300:
                current_app.logger.warning(f"[PERF] {request.method} {request.path} -> {response.status_code} in {dt_ms:.0f} ms")
        except Exception:
            pass
        return response

    @app.before_request
    def require_login():
        allowed_routes = {"login", "static"}
        if request.endpoint is None:
            return None
        if not session.get("logged_in") and request.endpoint not in allowed_routes:
            return redirect(url_for("login"))

    @app.route("/")
    def home():
        return redirect(url_for("bar.bar"))

    @app.route("/subcategories/<category>")
    def get_subcategories(category):
        lists = current_app.config["LISTS"]
        subcategories = lists["subcategories"].get(category, [])
        return jsonify(subcategories)

    @app.route("/ingredients")
    def get_ingredients():
        lists = current_app.config["LISTS"]
        ingredients = set(lists["categories"])
        for subs in lists["subcategories"].values():
            ingredients.update(subs)

        conn = get_db_connection()
        try:
            # Add "owned" ingredient names
            owned_names = conn.execute(
                "SELECT name FROM possibleingredients WHERE in_bar = TRUE"
            ).fetchall()
            ingredients.update([row["name"] for row in owned_names])

            # Add all possible ingredient names
            possible_ingredients = conn.execute(
                "SELECT name FROM possibleingredients"
            ).fetchall()
            ingredients.update([row["name"] for row in possible_ingredients])

            serialized = sorted(ingredients)
        finally:
            close_db_connection()

        return jsonify(serialized)

    # --- Helpful 400 logging (Render currently only shows the status code) ---
    app.logger.setLevel(logging.INFO)

    @app.errorhandler(BadRequestKeyError)
    def handle_bad_request_key_error(e):
        # Typically: request.form['some_field'] missing
        app.logger.exception("BadRequestKeyError: %s", e)
        app.logger.info("POST %s content_type=%s", request.path, request.content_type)
        app.logger.info("form keys=%s", list(request.form.keys()))
        app.logger.info("files keys=%s", list(request.files.keys()))
        return "Bad Request (missing expected form field)", 400

    @app.errorhandler(BadRequest)
    def handle_bad_request(e):
        # Typically: invalid JSON, or abort(400)
        app.logger.exception("BadRequest: %s", getattr(e, "description", str(e)))
        app.logger.info("REQ %s %s content_type=%s len=%s",
                        request.method, request.path, request.content_type, request.content_length)
        app.logger.info("form keys=%s", list(request.form.keys()))
        app.logger.info("files keys=%s", list(request.files.keys()))
        app.logger.info("json=%s", request.get_json(silent=True))
        return "Bad Request", 400

    @app.route("/ingredient-details/<name>")
    def get_ingredient_details(name):
        conn = get_db_connection()
        try:
            ingredient = conn.execute(
                "SELECT category, sub_category FROM PossibleIngredients WHERE name = %s",
                (name,),
            ).fetchone()
        finally:
            close_db_connection()

        if ingredient:
            return jsonify(
                {
                    "category": ingredient["category"],
                    "sub_category": ingredient["sub_category"] or "",
                }
            )
        return jsonify({"error": "Ingredient not found"}), 404

    @app.route("/missing-ingredients")
    def missing_ingredients():
        if not current_app.config.get("ENABLE_FUTURE_ROUTES", False):
            abort(404)
        missing_drinks = fetch_drinks_missing_ingredients()
        return render_template(
            "missing_ingredients.html", missing_drinks=missing_drinks
        )

    @app.route("/have-base")
    def have_base():
        if not current_app.config.get("ENABLE_FUTURE_ROUTES", False):
            abort(404)
        have_base_spirit = fetch_drinks_with_base()
        return render_template("have_base.html", have_base_spirit=have_base_spirit)

    @app.route("/lists", methods=["GET", "POST"])
    def manage_lists():
        if request.method == "POST":
            conn = get_db_connection()
            try:
                conn.execute("DELETE FROM Subcategories")
                conn.execute("DELETE FROM Categories")
                conn.execute("DELETE FROM GlassTypes")
                conn.execute("DELETE FROM Methods")
                conn.execute("DELETE FROM IceOptions")
                conn.execute("DELETE FROM Units")

                categories_input = request.form.get("categories", "")
                new_categories = [
                    cat.strip() for cat in categories_input.split(",") if cat.strip()
                ]
                for cat in new_categories:
                    conn.execute("INSERT INTO Categories (name) VALUES (%s)", (cat,))

                for cat in new_categories:
                    subcats_input = request.form.get(f"subcategories_{cat}", "")
                    if subcats_input:
                        cursor = conn.execute(
                            "SELECT id FROM Categories WHERE name = %s", (cat,)
                        )
                        cat_id_row = cursor.fetchone()
                        if cat_id_row:
                            cat_id = cat_id_row["id"]
                            new_subcats = [
                                subcat.strip()
                                for subcat in subcats_input.split(",")
                                if subcat.strip()
                            ]
                            for subcat in new_subcats:
                                conn.execute(
                                    "INSERT INTO Subcategories (category_id, name) VALUES (%s, %s)",
                                    (cat_id, subcat),
                                )

                glass_types_input = request.form.get("glass_types", "")
                new_glass_types = [
                    glass.strip()
                    for glass in glass_types_input.split(",")
                    if glass.strip()
                ]
                for glass in new_glass_types:
                    conn.execute("INSERT INTO GlassTypes (name) VALUES (%s)", (glass,))

                methods_input = request.form.get("methods", "")
                new_methods = [
                    method.strip()
                    for method in methods_input.split(",")
                    if method.strip()
                ]
                for method in new_methods:
                    conn.execute("INSERT INTO Methods (name) VALUES (%s)", (method,))

                ice_options_input = request.form.get("ice_options", "")
                new_ice_options = [
                    ice.strip() for ice in ice_options_input.split(",") if ice.strip()
                ]
                for ice in new_ice_options:
                    conn.execute("INSERT INTO IceOptions (name) VALUES (%s)", (ice,))

                units_input = request.form.get("units", "")
                new_units = [
                    unit.strip() for unit in units_input.split(",") if unit.strip()
                ]
                for unit in new_units:
                    conn.execute("INSERT INTO Units (name) VALUES (%s)", (unit,))

                conn.commit()
            finally:
                close_db_connection()

            current_app.config["LISTS"] = load_lists()
            return redirect(url_for("manage_lists"))

        return render_template("lists.html", lists=current_app.config["LISTS"])

    @app.route("/possible-ingredients-json")
    def possible_ingredients_json():
        conn = get_db_connection()
        query = """
            SELECT DISTINCT name FROM PossibleIngredients WHERE name IS NOT NULL AND name != ''
            UNION
            SELECT DISTINCT category FROM PossibleIngredients WHERE category IS NOT NULL AND category != ''
            UNION
            SELECT DISTINCT sub_category FROM PossibleIngredients WHERE sub_category IS NOT NULL AND sub_category != ''
            ORDER BY 1
        """
        try:
            results = conn.execute(query).fetchall()
        finally:
            close_db_connection()
        all_options = []
        for row in results:
            first_val = row["name"]
            if first_val:
                all_options.append(first_val)
        return jsonify(all_options)

    @app.route("/possible-ingredients", methods=["GET", "POST"])
    def possible_ingredients():
        conn = get_db_connection()
        try:
            if request.method == "POST":
                name = request.form["name"].strip()
                category = request.form["category"]
                sub_category = request.form.get("sub_category", "")
                if name and category:
                    conn.execute(
                        """
                        INSERT INTO PossibleIngredients (name, category, sub_category)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (name, category, sub_category or None),
                    )
                    conn.commit()
                current_app.config["LISTS"] = load_lists()
                return redirect(url_for("possible_ingredients"))

            ingredients = conn.execute(
                "SELECT id, name, category, sub_category FROM PossibleIngredients ORDER BY name"
            ).fetchall()
            categories = conn.execute(
                "SELECT DISTINCT category FROM PossibleIngredients WHERE category IS NOT NULL ORDER BY category"
            ).fetchall()
        finally:
            close_db_connection()

        return render_template(
            "possible_ingredients.html",
            ingredients=ingredients,
            categories=[cat["category"] for cat in categories],
        )

    @app.route("/possible-ingredient-names")
    def get_possible_ingredient_names():
        conn = get_db_connection()
        try:
            names = conn.execute(
                "SELECT DISTINCT name FROM PossibleIngredients ORDER BY name"
            ).fetchall()
        finally:
            close_db_connection()
        return jsonify([row["name"] for row in names])

    @app.route("/ingredient-purchases/<int:ingredient_id>", methods=["GET", "POST"])
    def ingredient_purchases(ingredient_id):
        conn = get_db_connection()
        try:
            _ensure_ingredient_purchases_table(conn)

            if request.method == "POST":
                data = request.get_json(silent=True) or request.form
                purchase_date = (data.get("purchase_date") or "").strip()
                location = (data.get("location") or "").strip()
                size_value = _parse_float(data.get("size_value"))
                size_unit = (data.get("size_unit") or "").strip()
                price = _parse_float(data.get("price"))
                notes = (data.get("notes") or "").strip()

                if not purchase_date:
                    return jsonify({"message": "Purchase date is required."}), 400
                if size_value is None or size_value <= 0:
                    return jsonify({"message": "Size value must be a positive number."}), 400
                if not size_unit:
                    return jsonify({"message": "Size unit is required."}), 400
                if price is None or price <= 0:
                    return jsonify({"message": "Price must be a positive number."}), 400

                conn.execute(
                    """
                    INSERT INTO IngredientPurchases
                        (ingredient_id, purchase_date, location, size_value, size_unit, price, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ingredient_id,
                        purchase_date,
                        location or None,
                        size_value,
                        size_unit,
                        price,
                        notes or None,
                    ),
                )
                conn.commit()
                return jsonify({"message": "Purchase added."}), 201

            rows = conn.execute(
                """
                SELECT id, purchase_date, location, size_value, size_unit, price, notes
                FROM IngredientPurchases
                WHERE ingredient_id = %s
                ORDER BY purchase_date DESC, id DESC
                """,
                (ingredient_id,),
            ).fetchall()
        finally:
            close_db_connection()

        purchases = []
        for row in rows:
            size_value = row["size_value"]
            size_unit = row["size_unit"]
            size_ml = _convert_to_ml(size_value, size_unit)
            price = row["price"]
            price_per_ml = (price / size_ml) if (size_ml and price is not None) else None
            purchases.append(
                {
                    "id": row["id"],
                    "purchase_date": row["purchase_date"],
                    "location": row["location"] or "",
                    "size_value": size_value,
                    "size_unit": size_unit,
                    "size_ml": size_ml,
                    "price": price,
                    "price_per_ml": price_per_ml,
                    "notes": row["notes"] or "",
                }
            )
        return jsonify(purchases)

    @app.route("/prices", methods=["GET", "POST"])
    def prices():
        conn = get_db_connection()
        try:
            _ensure_ingredient_purchases_table(conn)

            if request.method == "POST":
                ingredient_id_raw = (request.form.get("ingredient_id") or "").strip()
                purchase_date = (request.form.get("purchase_date") or "").strip()
                location = (request.form.get("location") or "").strip()
                size_value = _parse_float(request.form.get("size_value"))
                size_unit = (request.form.get("size_unit") or "").strip()
                price = _parse_float(request.form.get("price"))
                notes = (request.form.get("notes") or "").strip()

                ingredient_id = None
                try:
                    ingredient_id = int(ingredient_id_raw)
                except (TypeError, ValueError):
                    ingredient_id = None

                if ingredient_id is None:
                    flash("Please select an ingredient.")
                    return redirect(url_for("prices"))

                ingredient_exists = conn.execute(
                    "SELECT id FROM PossibleIngredients WHERE id = %s",
                    (ingredient_id,),
                ).fetchone()
                if not ingredient_exists:
                    flash("Selected ingredient was not found.")
                    return redirect(url_for("prices"))

                if not purchase_date:
                    flash("Purchase date is required.")
                    return redirect(url_for("prices"))
                if size_value is None or size_value <= 0:
                    flash("Size value must be a positive number.")
                    return redirect(url_for("prices"))
                if not size_unit:
                    flash("Size unit is required.")
                    return redirect(url_for("prices"))
                if price is None or price <= 0:
                    flash("Price must be a positive number.")
                    return redirect(url_for("prices"))

                conn.execute(
                    """
                    INSERT INTO IngredientPurchases
                        (ingredient_id, purchase_date, location, size_value, size_unit, price, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ingredient_id,
                        purchase_date,
                        location or None,
                        size_value,
                        size_unit,
                        price,
                        notes or None,
                    ),
                )
                conn.commit()
                flash("Purchase added.")
                return redirect(url_for("prices"))

            ingredient_rows = conn.execute(
                "SELECT id, name FROM PossibleIngredients ORDER BY name"
            ).fetchall()
            purchase_rows = conn.execute(
                """
                SELECT
                    ip.id,
                    ip.ingredient_id,
                    pi.name AS ingredient_name,
                    ip.purchase_date,
                    ip.location,
                    ip.size_value,
                    ip.size_unit,
                    ip.price,
                    ip.notes
                FROM IngredientPurchases ip
                JOIN PossibleIngredients pi
                  ON pi.id = ip.ingredient_id
                ORDER BY ip.purchase_date DESC, ip.id DESC
                """
            ).fetchall()
        finally:
            close_db_connection()

        purchases = []
        for row in purchase_rows:
            size_value = row["size_value"]
            size_unit = row["size_unit"]
            size_ml = _convert_to_ml(size_value, size_unit)
            price = row["price"]
            price_per_ml = (price / size_ml) if (size_ml and price is not None) else None
            price_per_oz = (
                price_per_ml * UNIT_TO_ML["oz"] if price_per_ml is not None else None
            )
            purchases.append(
                {
                    "id": row["id"],
                    "ingredient_id": row["ingredient_id"],
                    "ingredient_name": row["ingredient_name"],
                    "purchase_date": row["purchase_date"],
                    "location": row["location"] or "",
                    "size_value": size_value,
                    "size_unit": size_unit,
                    "size_value_display": _format_size_value(size_value),
                    "size_unit_display": _display_unit(size_unit),
                    "size_ml": size_ml,
                    "price": price,
                    "price_per_ml": price_per_ml,
                    "price_per_oz": price_per_oz,
                    "notes": row["notes"] or "",
                }
            )

        return render_template(
            "prices.html",
            ingredients=ingredient_rows,
            purchases=purchases,
            purchase_units=PURCHASE_UNITS,
            today=date.today().isoformat(),
        )

    @app.route("/ingredient-purchase/<int:purchase_id>", methods=["DELETE"])
    def delete_ingredient_purchase(purchase_id):
        conn = get_db_connection()
        try:
            _ensure_ingredient_purchases_table(conn)
            conn.execute("DELETE FROM IngredientPurchases WHERE id = %s", (purchase_id,))
            conn.commit()
        finally:
            close_db_connection()
        return jsonify({"message": "Purchase deleted."}), 200

    @app.route("/delete_possible_ingredient/<int:id>", methods=["DELETE"])
    def delete_possible_ingredient(id):
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM PossibleIngredients WHERE id = %s", (id,))
            conn.commit()
        finally:
            close_db_connection()
        current_app.config["LISTS"] = load_lists()
        return jsonify({"message": "Ingredient deleted successfully"}), 200

    @app.route("/update_possible_ingredient/<id>", methods=["POST"])
    def update_possible_ingredient(id):
        conn = get_db_connection()
        name = request.form["name"].strip()
        category = request.form["category"]
        sub_category = request.form.get("sub_category", "")

        if not name or not category:
            close_db_connection()
            return jsonify({"message": "Name and category are required."}), 400

        try:
            conn.execute(
                "UPDATE PossibleIngredients SET name = %s, category = %s, sub_category = %s WHERE id = %s",
                (name, category, sub_category or None, id),
            )
            conn.commit()
            current_app.config["LISTS"] = load_lists()
            return jsonify({"message": "Ingredient updated successfully."}), 200
        except Exception as e:
            conn.rollback()
            return jsonify({"message": f"Error updating ingredient: {str(e)}"}), 500
        finally:
            close_db_connection()

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    return app


app = create_app()


def run_app():
    if app.config.get("FLASK_DEV"):
        print(">>> FLASK_DEV MODE ENABLED (Flask reloader via watchfiles if installed)")
        app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=True)
    else:
        app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    run_app()
