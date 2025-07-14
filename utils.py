import sqlite3
import os

def get_db_connection():
    # Default to local dev DB
    db_file = 'cocktail_dev.db'

    # On Render, use the production DB filename
    if os.environ.get("RENDER") == "true":
        db_file = 'cocktail_app.db'

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn

# Load lists from the database
def load_lists():
    conn = get_db_connection()
    lists = {
        'categories': [],
        'subcategories': {},
        'glass_types': [],
        'methods': [],
        'ice_options': [],
        'units': []
    }

    # Load categories
    categories = conn.execute('SELECT name FROM Categories ORDER BY name').fetchall()
    lists['categories'] = [row['name'] for row in categories]

    # Load subcategories
    for cat in lists['categories']:
        cursor = conn.execute('SELECT id FROM Categories WHERE name = ?', (cat,))
        cat_id = cursor.fetchone()['id']
        subcategories = conn.execute('SELECT name FROM Subcategories WHERE category_id = ? ORDER BY name', (cat_id,)).fetchall()
        lists['subcategories'][cat] = [row['name'] for row in subcategories]

    # Load glass types
    glass_types = conn.execute('SELECT name FROM GlassTypes ORDER BY name').fetchall()
    lists['glass_types'] = [row['name'] for row in glass_types]

    # Load methods
    methods = conn.execute('SELECT name FROM Methods ORDER BY name').fetchall()
    lists['methods'] = [row['name'] for row in methods]

    # Load ice options
    ice_options = conn.execute('SELECT name FROM IceOptions ORDER BY name').fetchall()
    lists['ice_options'] = [row['name'] for row in ice_options]

    # Load units
    units = conn.execute('SELECT name FROM Units ORDER BY name').fetchall()
    lists['units'] = [row['name'] for row in units]

    # Add ingredients dictionary by name
    ingredients = conn.execute('SELECT * FROM PossibleIngredients').fetchall()
    lists['ingredients'] = {row['name']: row for row in ingredients}

    conn.close()
    return lists