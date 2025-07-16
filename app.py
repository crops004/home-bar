from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from routes import drink_maker, bar, recipes
from utils import get_db_connection, load_lists
from helpers import fetch_drinks_missing_ingredients, fetch_drinks_with_base
import os
from dotenv import load_dotenv

load_dotenv()

import sqlite3

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
AUTH_USERNAME = os.getenv('USERNAME')
AUTH_PASSWORD = os.getenv('PASSWORD')
lists = load_lists()
app.config['LISTS'] = lists

app.register_blueprint(drink_maker.drink_maker_bp, url_prefix='/drink')
app.register_blueprint(bar.bar_bp, url_prefix='/bar')
app.register_blueprint(recipes.recipes_bp, url_prefix='/recipe')

# Login management
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        submitted_username = request.form['username']
        submitted_password = request.form['password']
        expected_username = os.getenv('USERNAME')
        expected_password = os.getenv('PASSWORD')

        # Debug output
        print(f"[DEBUG] Submitted username: {submitted_username}")
        print(f"[DEBUG] Submitted password: {submitted_password}")
        print(f"[DEBUG] Expected username: {expected_username}")
        print(f"[DEBUG] Expected password: {expected_password}")

        if submitted_username == expected_username and submitted_password == expected_password:
            session['logged_in'] = True
            return redirect(url_for('home'))  # or your home route
        else:
            flash('Invalid credentials')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Logged out')
    return redirect(url_for('login'))

@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if not session.get('logged_in') and request.endpoint not in allowed_routes:
        return redirect(url_for('login'))

# Homepage route
@app.route('/')
def home():
    return render_template('home.html')

# API to get subcategories for a given category
@app.route('/subcategories/<category>')
def get_subcategories(category):
    subcategories = lists['subcategories'].get(category, [])
    return jsonify(subcategories)

# API to get all ingredients (categories + subcategories + bar contents names + possible ingredients)
@app.route('/ingredients')
def get_ingredients():
    # Start with categories and subcategories from lists
    ingredients = set(lists['categories'])
    for subs in lists['subcategories'].values():
        ingredients.update(subs)
    
    # Add names from BarContents
    conn = get_db_connection()
    bar_names = conn.execute('SELECT name FROM BarContents').fetchall()
    ingredients.update([row['name'] for row in bar_names])
    
    # Add names from PossibleIngredients
    possible_ingredients = conn.execute('SELECT name FROM PossibleIngredients').fetchall()
    ingredients.update([row['name'] for row in possible_ingredients])
    
    conn.close()
    return jsonify(sorted(list(ingredients)))

# API to get category and subcategory for a given name from PossibleIngredients
@app.route('/ingredient-details/<name>')
def get_ingredient_details(name):
    conn = get_db_connection()
    ingredient = conn.execute('SELECT category, sub_category FROM PossibleIngredients WHERE name = ?', (name,)).fetchone()
    conn.close()
    if ingredient:
        return jsonify({
            'category': ingredient['category'],
            'sub_category': ingredient['sub_category'] or ''
        })
    return jsonify({'error': 'Ingredient not found'}), 404









@app.route('/missing-ingredients')
def missing_ingredients():
    missing_drinks = fetch_drinks_missing_ingredients()
    return render_template('missing_ingredients.html', missing_drinks=missing_drinks)

# Drinks with base spirit route
@app.route('/have-base')
def have_base():
    have_base_spirit = fetch_drinks_with_base()
    return render_template('have_base.html', have_base_spirit=have_base_spirit)

@app.route('/lists', methods=['GET', 'POST'])
def manage_lists():
    global lists
    conn = get_db_connection()
    if request.method == 'POST':
        # Clear existing data
        conn.execute('DELETE FROM Subcategories')
        conn.execute('DELETE FROM Categories')
        conn.execute('DELETE FROM GlassTypes')
        conn.execute('DELETE FROM Methods')
        conn.execute('DELETE FROM IceOptions')
        conn.execute('DELETE FROM Units')

        # Parse the form data
        # Categories
        categories_input = request.form.get('categories', '')
        new_categories = [cat.strip() for cat in categories_input.split(',') if cat.strip()]
        for cat in new_categories:
            conn.execute('INSERT INTO Categories (name) VALUES (?)', (cat,))

        # Subcategories
        for cat in new_categories:
            subcats_input = request.form.get(f'subcategories_{cat}', '')
            if subcats_input:
                cursor = conn.execute('SELECT id FROM Categories WHERE name = ?', (cat,))
                cat_id = cursor.fetchone()['id']
                new_subcats = [subcat.strip() for subcat in subcats_input.split(',') if subcat.strip()]
                for subcat in new_subcats:
                    conn.execute('INSERT INTO Subcategories (category_id, name) VALUES (?, ?)', (cat_id, subcat))

        # Glass Types
        glass_types_input = request.form.get('glass_types', '')
        new_glass_types = [glass.strip() for glass in glass_types_input.split(',') if glass.strip()]
        for glass in new_glass_types:
            conn.execute('INSERT INTO GlassTypes (name) VALUES (?)', (glass,))

        # Methods
        methods_input = request.form.get('methods', '')
        new_methods = [method.strip() for method in methods_input.split(',') if method.strip()]
        for method in new_methods:
            conn.execute('INSERT INTO Methods (name) VALUES (?)', (method,))

        # Ice Options
        ice_options_input = request.form.get('ice_options', '')
        new_ice_options = [ice.strip() for ice in ice_options_input.split(',') if ice.strip()]
        for ice in new_ice_options:
            conn.execute('INSERT INTO IceOptions (name) VALUES (?)', (ice,))

        # Units
        units_input = request.form.get('units', '')
        new_units = [unit.strip() for unit in units_input.split(',') if unit.strip()]
        for unit in new_units:
            conn.execute('INSERT INTO Units (name) VALUES (?)', (unit,))

        conn.commit()
        # Reload the lists
        lists.clear()
        lists.update(load_lists())
        return redirect(url_for('manage_lists'))

    conn.close()
    return render_template('lists.html', lists=lists)

# Route to get all unique names, categories, and subcategories as JSON
@app.route('/possible-ingredients-json')
def possible_ingredients_json():
    conn = get_db_connection()
    query = '''
        SELECT DISTINCT name FROM PossibleIngredients WHERE name IS NOT NULL AND name != ''
        UNION
        SELECT DISTINCT category FROM PossibleIngredients WHERE category IS NOT NULL AND category != ''
        UNION
        SELECT DISTINCT sub_category FROM PossibleIngredients WHERE sub_category IS NOT NULL AND sub_category != ''
        ORDER BY 1
    '''
    results = conn.execute(query).fetchall()
    conn.close()
    all_options = [row[0] for row in results if row[0]]
    return jsonify(all_options)

# Route to manage possible ingredients (render template or handle form submission)
@app.route('/possible-ingredients', methods=['GET', 'POST'])
def possible_ingredients():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category']
        sub_category = request.form.get('sub_category', '')  # Optional, default to empty string
        if name and category:
            try:
                conn.execute('INSERT OR IGNORE INTO PossibleIngredients (name, category, sub_category) VALUES (?, ?, ?)',
                             (name, category, sub_category or None))
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # Ignore if the combination already exists due to UNIQUE constraint
        conn.close()
        return redirect(url_for('possible_ingredients'))

    # For GET: Render the template with the list of ingredients
    ingredients = conn.execute('SELECT id, name, category, sub_category FROM PossibleIngredients ORDER BY name').fetchall()
    categories = conn.execute('SELECT DISTINCT category FROM PossibleIngredients WHERE category IS NOT NULL ORDER BY category').fetchall()
    conn.close()
    return render_template('possible_ingredients.html', ingredients=ingredients, categories=[cat['category'] for cat in categories])

# API to get only the names from PossibleIngredients
@app.route('/possible-ingredient-names')
def get_possible_ingredient_names():
    conn = get_db_connection()
    names = conn.execute('SELECT DISTINCT name FROM PossibleIngredients ORDER BY name').fetchall()
    conn.close()
    return jsonify([row['name'] for row in names])

# Route to delete a possible ingredient
@app.route('/delete_possible_ingredient/<int:id>', methods=['DELETE'])
def delete_possible_ingredient(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM PossibleIngredients WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Ingredient deleted successfully'}), 200

@app.route('/update_possible_ingredient/<id>', methods=['POST'])
def update_possible_ingredient(id):
    conn = get_db_connection()
    name = request.form['name'].strip()
    category = request.form['category']
    sub_category = request.form.get('sub_category', '')  # Optional, default to empty string

    if not name or not category:
        conn.close()
        return jsonify({'message': 'Name and category are required.'}), 400

    try:
        conn.execute('UPDATE PossibleIngredients SET name = ?, category = ?, sub_category = ? WHERE id = ?',
                     (name, category, sub_category or None, id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Ingredient updated successfully.'}), 200
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'message': f'Error updating ingredient: {str(e)}'}), 500


    
if __name__ == '__main__':
    app.run(debug=True)