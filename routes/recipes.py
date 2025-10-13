from collections import defaultdict

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app
from utils import get_db_connection, load_lists, close_db_connection

recipes_bp = Blueprint('recipes', __name__)

SPIRIT_CATEGORIES = [
    'Absinthe',
    'Aperitif',
    'Bitters',
    'Brandy',
    'Cognac',
    'Digestif',
    'Fortified Wine',
    'Gin',
    'Liqueur',
    'Mezcal',
    'Rum',
    'Tequila',
    'Vermouth',
    'Vodka',
    'Whiskey',
]


def _get_lists():
    """Fetch shared option lists from the application config, refreshing if needed."""
    cached = current_app.config.get('LISTS')
    if not cached:
        cached = load_lists()
        current_app.config['LISTS'] = cached
    return cached

# Recipe collection route
@recipes_bp.route('/recipe', methods=['GET', 'POST'])
def recipes():
    lists_data = _get_lists()
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            drink = request.form['drink'].strip().title()
            glass = request.form['glass']
            garnish = request.form['garnish']
            method = request.form['method']
            ice = request.form['Ice']
            notes = request.form['notes']
            base_spirit = request.form['base_spirit']
            
            conn.execute('INSERT INTO Recipes (drink, glass, garnish, method, Ice, notes, Base_Spirit) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (drink, glass, garnish, method, ice, notes, base_spirit))
            
            i = 0
            while f'ingredient_{i}' in request.form:
                ingredient = request.form[f'ingredient_{i}']
                quantity = request.form[f'quantity_{i}']
                unit = request.form[f'unit_{i}']
                conn.execute('INSERT INTO RecipeIngredients (drink, ingredient, quantity, unit) VALUES (?, ?, ?, ?)',
                             (drink, ingredient, quantity, unit))
                i += 1
            
            conn.commit()
            return redirect(url_for('recipes.recipes'))
        raw_recipes = conn.execute(
            '''
            SELECT
                r.drink,
                COALESCE(r.Base_Spirit, '') AS base_spirit
            FROM Recipes AS r
            ORDER BY
                CASE WHEN r.Base_Spirit IS NULL OR r.Base_Spirit = '' THEN 1 ELSE 0 END,
                LOWER(r.Base_Spirit),
                LOWER(r.drink)
            '''
        ).fetchall()

        category_lookup = {}
        subcategories = lists_data.get('subcategories', {})
        for category, subs in subcategories.items():
            category_lookup[category.lower()] = category
            for sub in subs:
                category_lookup[sub.lower()] = category
        for category in lists_data.get('categories', []):
            category_lookup.setdefault(category.lower(), category)

        spirit_category_set = {value.lower() for value in SPIRIT_CATEGORIES}

        possible_rows = conn.execute(
            'SELECT name, category, sub_category FROM PossibleIngredients'
        ).fetchall()
        possible_lookup = {
            (row['name'] or '').strip().lower(): {
                'category': (row['category'] or '').strip(),
                'sub_category': (row['sub_category'] or '').strip(),
            }
            for row in possible_rows
        }

        spirits_by_recipe = defaultdict(list)
        seen_spirits = defaultdict(set)
        ingredient_rows = conn.execute(
            'SELECT drink, ingredient FROM RecipeIngredients ORDER BY rowid'
        ).fetchall()
        for row in ingredient_rows:
            drink = row['drink']
            ingredient_name = (row['ingredient'] or '').strip()
            if not ingredient_name:
                continue
            info = possible_lookup.get(ingredient_name.lower())
            category = (info.get('category') if info else '') or ''
            sub_category = (info.get('sub_category') if info else '') or ''

            resolved_category = ''
            if sub_category:
                resolved_category = category_lookup.get(sub_category.lower(), sub_category)
            if not resolved_category and category:
                resolved_category = category_lookup.get(category.lower(), category)
            if not resolved_category:
                resolved_category = category_lookup.get(ingredient_name.lower(), ingredient_name)
            resolved_category = (resolved_category or '').strip()
            if resolved_category.lower() in spirit_category_set:
                seen = seen_spirits[drink]
                if ingredient_name not in seen:
                    spirits_by_recipe[drink].append(ingredient_name)
                    seen.add(ingredient_name)

        all_recipes = []
        for row in raw_recipes:
            drink = row['drink']
            base_spirit = (row['base_spirit'] or '').strip()
            category_key = base_spirit.lower()
            resolved_category = category_lookup.get(category_key, base_spirit or 'Unknown')
            resolved_category = (resolved_category or 'Unknown').strip() or 'Unknown'
            spirit_summary = ' | '.join(spirits_by_recipe.get(drink, []))
            all_recipes.append(
                {
                    'drink': drink,
                    'base_spirit': base_spirit,
                    'base_spirit_category': resolved_category,
                    'ingredient_summary': spirit_summary,
                }
            )

        all_recipes.sort(
            key=lambda item: (
                1 if item['base_spirit_category'].lower() == 'unknown' else 0,
                item['base_spirit_category'].lower(),
                item['drink'].lower(),
            )
        )

        return render_template(
            'recipes.html',
            all_recipes=all_recipes,
            lists=lists_data,
            spirit_categories=SPIRIT_CATEGORIES,
        )
    finally:
        close_db_connection()

# Route to fetch details of a specific recipe
@recipes_bp.route('/<string:drink>', methods=['GET'])
def get_recipe(drink):
    conn = get_db_connection()
    try:
        recipe = conn.execute('SELECT * FROM Recipes WHERE drink = ?', (drink,)).fetchone()
        ingredients = conn.execute(
            '''
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
            ORDER BY ri.rowid
            ''',
            (drink,),
        ).fetchall()
    finally:
        close_db_connection()
    if recipe:
        recipe_data = {
            'name': recipe['drink'],
            'glass': recipe['Glass'],
            'garnish': recipe['Garnish'],
            'method': recipe['Method'],
            'ice': recipe['Ice'],
            'notes': recipe['Notes'],
            'base_spirit': recipe['Base_Spirit']
        }
        recipe_data['ingredients'] = [
            {
                'ingredient': ing['ingredient'],
                'quantity': ing['quantity'],
                'unit': ing['unit'],
                'category': ing['category'],
                'sub_category': ing['sub_category'],
            }
            for ing in ingredients
        ]
        return jsonify(recipe_data)
    return jsonify({'error': 'Recipe not found'}), 404

# Route to delete a recipe
@recipes_bp.route('/delete_recipe/<string:drink>', methods=['DELETE'])
def delete_recipe(drink):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM Recipes WHERE drink = ?', (drink,))
        conn.execute('DELETE FROM RecipeIngredients WHERE drink = ?', (drink,))
        conn.commit()
    finally:
        close_db_connection()
    return jsonify({'message': 'Recipe deleted successfully'}), 200

# Route to edit a recipe
@recipes_bp.route('/edit_recipe/<drink>', methods=['POST'])
def edit_recipe(drink):
    data = request.get_json()
    original_drink = data.get('original_drink')
    new_drink = data.get('drink')
    glass = data.get('glass')
    garnish = data.get('garnish')
    method = data.get('method')
    ice = data.get('Ice')  # Map frontend's Ice to database's Ice
    notes = data.get('notes')
    base_spirit = data.get('base_spirit')
    ingredients = data.get('ingredients', [])

    if not original_drink or not new_drink:
        return jsonify({'success': False, 'message': 'Drink name is required.'}), 400

    conn = get_db_connection()
    try:
        # Update the recipe
        conn.execute('''
            UPDATE Recipes 
            SET drink = ?, glass = ?, garnish = ?, method = ?, Ice = ?, notes = ?, Base_Spirit = ?
            WHERE drink = ?
        ''', (new_drink, glass or None, garnish or None, method or None, ice or None, notes or None, base_spirit, original_drink))

        # Delete existing ingredients
        conn.execute('DELETE FROM RecipeIngredients WHERE drink = ?', (original_drink,))

        # Update ingredients (use new_drink if the name changed)
        target_drink = new_drink if new_drink != original_drink else original_drink
        for ingredient in ingredients:
            conn.execute('INSERT INTO RecipeIngredients (drink, ingredient, quantity, unit) VALUES (?, ?, ?, ?)',
                         (target_drink, ingredient['ingredient'], ingredient['quantity'], ingredient['unit']))

        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection()
