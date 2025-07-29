from unicodedata import name
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from utils import get_db_connection, load_lists

bar_bp = Blueprint('bar', __name__, template_folder='../templates')
lists = load_lists()

# Bar contents route
@bar_bp.route('/bar', methods=['GET', 'POST'])
def bar():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        sub_category = request.form.get('sub_category', '')  # Optional, default to empty string
        conn.execute('INSERT OR IGNORE INTO BarContents (name, category, sub_category) VALUES (?, ?, ?)', 
                     (name, category, sub_category or None))  # Convert empty string to NULL
        conn.commit()
        conn.close()

        # After successful insert
        flash(f"{name} added successfully to your bar.")

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
    for item in bar_contents:
        is_spirit = (
            item['category'] in spirit_categories or 
            any(sub in spirit_categories for sub in lists['subcategories'].get(item['category'], []))
        )
        item['type'] = 'spirit' if is_spirit else 'modifier'

    # Fetch possible names for the dropdown
    possible_names = conn.execute('SELECT DISTINCT name FROM PossibleIngredients ORDER BY name').fetchall()
    possible_names = [row['name'] for row in possible_names]
    
    conn.close()
    return render_template('bar.html', items=bar_contents, possible_names=possible_names, lists=lists)

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
            conn.close()
            return jsonify({'message': f'No item named "{name}" found in bar'}), 404
        conn.close()
        return jsonify({'message': f'{name} deleted from bar'}), 200
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'message': f'Error deleting item: {str(e)}'}), 500