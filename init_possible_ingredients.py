import sqlite3

# Legacy helper retained for historical/local SQLite workflows.
# The active app runtime uses Postgres via DATABASE_URL.

def init_possible_ingredients():
    try:
        # Connect to the database
        conn = sqlite3.connect('cocktail_app.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Drop the existing PossibleIngredients table if it exists
        cursor.execute('DROP TABLE IF EXISTS PossibleIngredients')

        # Create the PossibleIngredients table with the same structure as BarContents plus an id column
        cursor.execute('''
            CREATE TABLE PossibleIngredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                sub_category TEXT,
                UNIQUE(name, category, sub_category)
            )
        ''')

        # Populate the table with data from BarContents
        cursor.execute('''
            INSERT OR IGNORE INTO PossibleIngredients (name, category, sub_category)
            SELECT name, category, sub_category FROM BarContents
        ''')

        # Commit the changes
        conn.commit()
        print("Successfully created and populated the PossibleIngredients table.")

        # Optional: Print the contents of the table to verify
        cursor.execute('SELECT * FROM PossibleIngredients')
        ingredients = cursor.fetchall()
        if ingredients:
            print("Current PossibleIngredients:")
            for ing in ingredients:
                print(f"ID: {ing['id']}, Name: {ing['name']}, Category: {ing['category']}, Sub Category: {ing['sub_category'] or 'None'}")
        else:
            print("No ingredients were added to PossibleIngredients (BarContents may be empty).")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    init_possible_ingredients()
