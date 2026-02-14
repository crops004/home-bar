from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
    current_app,
)
from utils import get_db_connection, load_lists, close_db_connection

bar_bp = Blueprint('bar', __name__, template_folder='../templates')


def _get_lists():
    """Ensure the latest shared lists are available from the app config."""
    cached = current_app.config.get('LISTS')
    if not cached:
        cached = load_lists()
        current_app.config['LISTS'] = cached
    return cached

# Bar contents route
@bar_bp.route('/bar', methods=['GET', 'POST'])
def bar():
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            submitted_name = (request.form.get('name') or '').strip()
            existing = conn.execute(
                """
                SELECT name, in_bar
                FROM possibleingredients
                WHERE lower(name) = lower(%s)
                LIMIT 1
                """,
                (submitted_name,),
            ).fetchone()

            if not existing:
                flash(f'"{submitted_name}" not found in Possible Ingredients.', "error")
                return redirect(url_for("bar.bar"))

            canonical_name = existing['name']
            if existing['in_bar']:
                flash(f"{canonical_name} already exists in your bar.", "info")
                return redirect(url_for("bar.bar"))

            conn.execute(
                """
                UPDATE possibleingredients
                SET in_bar = TRUE
                WHERE lower(name) = lower(%s)
                """,
                (submitted_name,),
            )
            conn.commit()
            flash(f"{canonical_name} added successfully to your bar.", "success")

            return redirect(url_for("bar.bar"))
            
        # Define spirit categories (based on your subcategories and context)
        spirit_categories = [
            'Absinthe', 'Aperitif', 'Bitters', 'Brandy', 'Cognac', 'Gin', 'Liqueur', 'Mezcal', 'Rum', 'Tequila', 'Vermouth', 'Vodka', 'Whiskey',
            'Digestif', 'Fortified Wine'
        ]

        # Fetch bar contents and possible ingredients
        bar_contents_rows = conn.execute(
            """
            SELECT name, category, sub_category
            FROM possibleingredients
            WHERE in_bar = TRUE
            ORDER BY category, name
            """
        ).fetchall()
        bar_contents = [dict(row) for row in bar_contents_rows]
        
        # Tag each item with 'type': 'spirit' or 'modifier'
        lists = _get_lists()
        for item in bar_contents:
            is_spirit = (
                item['category'] in spirit_categories or 
                any(sub in spirit_categories for sub in lists['subcategories'].get(item['category'], []))
            )
            item['type'] = 'spirit' if is_spirit else 'modifier'

        # Fetch possible names for the dropdown
        possible_names = conn.execute('SELECT DISTINCT name FROM possibleingredients ORDER BY name').fetchall()
        possible_names = [row['name'] for row in possible_names]
        
        return render_template('bar.html', items=bar_contents, possible_names=possible_names, lists=lists)
    finally:
        close_db_connection()

# Delete bar item route
@bar_bp.route("/delete_bar_item/<string:name>", methods=["DELETE"])
def delete_bar_item(name):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE possibleingredients
            SET in_bar = FALSE
            WHERE lower(name) = lower(%s)
            """,
            (name,),
        )
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": f'No item named "{name}" found'}), 404

        return jsonify({"message": f'{name} removed from bar'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"message": f"Error removing item: {str(e)}"}), 500
    finally:
        close_db_connection()
