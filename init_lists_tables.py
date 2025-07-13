import sqlite3

def init_lists_tables():
    try:
        # Connect to the database
        conn = sqlite3.connect('cocktail_app.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('DROP TABLE IF EXISTS Subcategories')
        cursor.execute('DROP TABLE IF EXISTS Categories')
        cursor.execute('DROP TABLE IF EXISTS GlassTypes')
        cursor.execute('DROP TABLE IF EXISTS Methods')
        cursor.execute('DROP TABLE IF EXISTS IceOptions')
        cursor.execute('DROP TABLE IF EXISTS Units')

        # Create Categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')

        # Create Subcategories table (with foreign key to Categories)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Subcategories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(category_id, name),
                FOREIGN KEY (category_id) REFERENCES Categories(id) ON DELETE CASCADE
            )
        ''')

        # Create GlassTypes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS GlassTypes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')

        # Create Methods table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')

        # Create IceOptions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS IceOptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')

        # Create Units table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')

        # Hardcoded data from app.py
        categories = [
            'Absinthe', 'Aperitif', 'Bitters', 'Brandy', 'Cognac', 'Digestif', 'Fortified Wine', 'Gin', 'Liqueur',
            'Mezcal', 'Pisco', 'Rum', 'Tequila', 'Vermouth', 'Vodka', 'Whiskey', 'Citrus',
            'Soda', 'Juice', 'Syrup', 'Garnish', 'Fruit', 'Vegetable', 'Herb', 'Spice', 'Nut', 'Dairy', 'Coffee', 'Other'
        ]

        subcategories = {
            'Absinthe': ['Verte', 'Blanche'],
            'Brandy': ['Cognac', 'Armagnac', 'Calvados'],
            'Cognac': ['VS', 'VSOP', 'XO'],
            'Gin': ['London Dry Gin', 'Plymouth Gin', 'Old Tom Gin', 'Sloe Gin', 'Navy Strength Gin'],
            'Liqueur': ['Almond Liqueur', 'Elderflower Liqueur', 'Orange Liqueur', 'Peach Liqueur', 'Peppermint Liqueur', 'Raspberry Liqueur', 'Coffee Liqueur', 'Blackberry Liqueur', 'Black Currant Liqueur', 
                        'Black Raspberry Liqueur', 'Aloe Liqueur', 'Herbal Liqueur', 'Maraschino Liqueur', 'Apricot Liqueur', 'Banana Liqueur', 'Spiced Pear Liqueur'],
            'Mezcal': ['Joven', 'Reposado', 'Anejo', 'Oaxaca'],
            'Rum': ['White Rum', 'Dark Rum', 'Spiced Rum', 'Overproof Rum', 'Light Rum', 'Demerara Rum', 'Rum Agricole', 'Puerto Rican Rum', 'Cuban Rum'],
            'Tequila': ['Blanco', 'Reposado', 'Anejo'],
            'Whiskey': ['Bourbon', 'Rye', 'Scotch', 'Irish'],
        }

        glass_types = [
            'Coupe', 'Martini', 'Rocks', 'Highball', 'Collins', 'Shot', 'Flute'
        ]

        methods = [
            'Shake', 'Stir', 'Build', 'Blend', 'Shake and Strain', 'Shake and Double Strain', 'Stir and Strain'
        ]

        ice_options = [
            'None', 'Cubed', 'Crushed', 'Shaved', 'Block'
        ]

        units = [
            'oz', 'ml', 'dash', 'tsp', 'tbsp', 'splash', 'whole', 'barspoon', 'pinch'
        ]

        # Populate Categories
        for cat in categories:
            cursor.execute('INSERT OR IGNORE INTO Categories (name) VALUES (?)', (cat,))

        # Populate Subcategories
        for cat_name, subs in subcategories.items():
            # Get the category ID
            cursor.execute('SELECT id FROM Categories WHERE name = ?', (cat_name,))
            cat_id = cursor.fetchone()['id']
            for sub in subs:
                cursor.execute('INSERT OR IGNORE INTO Subcategories (category_id, name) VALUES (?, ?)', (cat_id, sub))

        # Populate GlassTypes
        for glass in glass_types:
            cursor.execute('INSERT OR IGNORE INTO GlassTypes (name) VALUES (?)', (glass,))

        # Populate Methods
        for method in methods:
            cursor.execute('INSERT OR IGNORE INTO Methods (name) VALUES (?)', (method,))

        # Populate IceOptions
        for ice in ice_options:
            cursor.execute('INSERT OR IGNORE INTO IceOptions (name) VALUES (?)', (ice,))

        # Populate Units
        for unit in units:
            cursor.execute('INSERT OR IGNORE INTO Units (name) VALUES (?)', (unit,))

        # Commit the changes
        conn.commit()
        print("Successfully created and populated the lists tables.")

        # Verify the data
        tables = ['Categories', 'Subcategories', 'GlassTypes', 'Methods', 'IceOptions', 'Units']
        for table in tables:
            cursor.execute(f'SELECT * FROM {table}')
            rows = cursor.fetchall()
            print(f"\nContents of {table}:")
            for row in rows:
                if table == 'Subcategories':
                    cursor.execute('SELECT name FROM Categories WHERE id = ?', (row['category_id'],))
                    cat_name = cursor.fetchone()['name']
                    print(f"Category: {cat_name}, Subcategory: {row['name']}")
                else:
                    print(f"Name: {row['name']}")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    init_lists_tables()