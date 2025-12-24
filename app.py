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
)
from routes import drink_maker, bar, recipes
from utils import get_db_connection, load_lists, close_db_connection
from helpers import fetch_drinks_missing_ingredients, fetch_drinks_with_base
from config import Config
import sqlite3
import os


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
            bar_names = conn.execute("SELECT name FROM BarContents").fetchall()
            ingredients.update([row["name"] for row in bar_names])

            possible_ingredients = conn.execute(
                "SELECT name FROM PossibleIngredients"
            ).fetchall()
            ingredients.update([row["name"] for row in possible_ingredients])
            serialized = sorted(ingredients)
        finally:
            close_db_connection()

        return jsonify(serialized)

    @app.route("/ingredient-details/<name>")
    def get_ingredient_details(name):
        conn = get_db_connection()
        try:
            ingredient = conn.execute(
                "SELECT category, sub_category FROM PossibleIngredients WHERE name = ?",
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
        missing_drinks = fetch_drinks_missing_ingredients()
        return render_template(
            "missing_ingredients.html", missing_drinks=missing_drinks
        )

    @app.route("/have-base")
    def have_base():
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
                    conn.execute("INSERT INTO Categories (name) VALUES (?)", (cat,))

                for cat in new_categories:
                    subcats_input = request.form.get(f"subcategories_{cat}", "")
                    if subcats_input:
                        cursor = conn.execute(
                            "SELECT id FROM Categories WHERE name = ?", (cat,)
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
                                    "INSERT INTO Subcategories (category_id, name) VALUES (?, ?)",
                                    (cat_id, subcat),
                                )

                glass_types_input = request.form.get("glass_types", "")
                new_glass_types = [
                    glass.strip()
                    for glass in glass_types_input.split(",")
                    if glass.strip()
                ]
                for glass in new_glass_types:
                    conn.execute("INSERT INTO GlassTypes (name) VALUES (?)", (glass,))

                methods_input = request.form.get("methods", "")
                new_methods = [
                    method.strip()
                    for method in methods_input.split(",")
                    if method.strip()
                ]
                for method in new_methods:
                    conn.execute("INSERT INTO Methods (name) VALUES (?)", (method,))

                ice_options_input = request.form.get("ice_options", "")
                new_ice_options = [
                    ice.strip() for ice in ice_options_input.split(",") if ice.strip()
                ]
                for ice in new_ice_options:
                    conn.execute("INSERT INTO IceOptions (name) VALUES (?)", (ice,))

                units_input = request.form.get("units", "")
                new_units = [
                    unit.strip() for unit in units_input.split(",") if unit.strip()
                ]
                for unit in new_units:
                    conn.execute("INSERT INTO Units (name) VALUES (?)", (unit,))

                conn.commit()
            finally:
                close_db_connection()

            current_app.config["LISTS"] = load_lists()
            close_db_connection()
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
            # Works for both sqlite3.Row and psycopg dict rows
            first_val = row[0] if not isinstance(row, dict) else next(iter(row.values()))
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
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO PossibleIngredients (name, category, sub_category) VALUES (?, ?, ?)",
                            (name, category, sub_category or None),
                        )
                        conn.commit()
                    except sqlite3.IntegrityError:
                        pass
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

    @app.route("/delete_possible_ingredient/<int:id>", methods=["DELETE"])
    def delete_possible_ingredient(id):
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM PossibleIngredients WHERE id = ?", (id,))
            conn.commit()
        finally:
            close_db_connection()
        current_app.config["LISTS"] = load_lists()
        close_db_connection()
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
                "UPDATE PossibleIngredients SET name = ?, category = ?, sub_category = ? WHERE id = ?",
                (name, category, sub_category or None, id),
            )
            conn.commit()
            current_app.config["LISTS"] = load_lists()
            return jsonify({"message": "Ingredient updated successfully."}), 200
        except sqlite3.Error as e:
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
        from livereload import Server
        import webbrowser
        import threading

        def open_browser():
            webbrowser.open_new("http://localhost:5000")

        if app.config.get("AUTO_OPEN_BROWSER"):
            threading.Timer(1.0, open_browser).start()

        print(">>> FLASK_DEV MODE ENABLED")

        server = Server(app.wsgi_app)
        server.watch("templates/*.html")
        server.watch("static/**/*.css")
        server.watch("static/**/*.js")
        server.serve(port=5000, debug=True)
    else:
        app.run(debug=False)


if __name__ == "__main__":
    run_app()
