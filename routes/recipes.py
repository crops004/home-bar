from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from utils import get_db_connection, load_lists

recipes_bp = Blueprint('recipes', __name__)

# Recipe collection route
@recipes_bp.route('/recipe', methods=['GET', 'POST'])
def recipes():
    conn = get_db_connection()
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
    
    all_recipes = conn.execute('SELECT drink, Base_Spirit AS base_spirit FROM Recipes ORDER BY LOWER(drink)').fetchall()
    print("Fetched recipes:", all_recipes)
    conn.close()
    return render_template('recipes.html', all_recipes=all_recipes, lists=load_lists())

# Route to fetch details of a specific recipe
@recipes_bp.route('/<string:drink>', methods=['GET'])
def get_recipe(drink):
    conn = get_db_connection()
    recipe = conn.execute('SELECT * FROM Recipes WHERE drink = ?', (drink,)).fetchone()
    ingredients = conn.execute('SELECT ingredient, quantity, unit FROM RecipeIngredients WHERE drink = ?', (drink,)).fetchall()
    conn.close()
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
            {'ingredient': ing['ingredient'], 'quantity': ing['quantity'], 'unit': ing['unit']}
            for ing in ingredients
        ]
        return jsonify(recipe_data)
    return jsonify({'error': 'Recipe not found'}), 404

# Route to delete a recipe
@recipes_bp.route('/delete_recipe/<string:drink>', methods=['DELETE'])
def delete_recipe(drink):
    conn = get_db_connection()
    conn.execute('DELETE FROM Recipes WHERE drink = ?', (drink,))
    conn.execute('DELETE FROM RecipeIngredients WHERE drink = ?', (drink,))
    conn.commit()
    conn.close()
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
        conn.close()