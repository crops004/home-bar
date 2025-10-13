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
            name = request.form['name']
            category = request.form['category']
            sub_category = request.form.get('sub_category', '')  # Optional, default to empty string
            cursor = conn.execute(
                'INSERT OR IGNORE INTO BarContents (name, category, sub_category) VALUES (?, ?, ?)',
                (name, category, sub_category or None)
            )  # Convert empty string to NULL
            conn.commit()

            if cursor.rowcount == 0:
                flash(f"{name} is already in your bar.", "info")
            else:
                flash(f"{name} added successfully to your bar.", "success")
            return redirect(url_for('bar.bar'))
            
        # Define spirit categories (based on your subcategories and context)
        spirit_categories = [
            'Absinthe', 'Aperitif', 'Bitters', 'Brandy', 'Cognac', 'Gin', 'Liqueur', 'Mezcal', 'Rum', 'Tequila', 'Vermouth', 'Vodka', 'Whiskey',
            'Digestif', 'Fortified Wine'
        ]

        # Fetch bar contents and possible ingredients
        bar_contents_rows = conn.execute('SELECT name, category, sub_category FROM BarContents ORDER BY category, name').fetchall()
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
        possible_names = conn.execute('SELECT DISTINCT name FROM PossibleIngredients ORDER BY name').fetchall()
        possible_names = [row['name'] for row in possible_names]
        
        return render_template('bar.html', items=bar_contents, possible_names=possible_names, lists=lists)
    finally:
        close_db_connection()

# Delete bar item route
@bar_bp.route('/delete_bar_item/<string:name>', methods=['DELETE'])
def delete_bar_item(name):
    conn = get_db_connection()
    try:
        # Log the name being deleted for debugging
        print(f"Attempting to delete item: '{name}'")
        # Check current contents to debug
        existing_items = conn.execute('SELECT name FROM BarContents WHERE name = ?', (name,)).fetchall()
        for item in existing_items:
            print(f"Existing item in DB: '{item['name']}'")
        
        # Perform case-insensitive delete
        cursor = conn.execute('DELETE FROM BarContents WHERE LOWER(name) = LOWER(?)', (name,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'message': f'No item named "{name}" found in bar'}), 404
        return jsonify({'message': f'{name} deleted from bar'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'message': f'Error deleting item: {str(e)}'}), 500
    finally:
        close_db_connection()
