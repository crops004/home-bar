import sqlite3

def trim_names():
    # Connect to the database
    conn = sqlite3.connect('cocktail_app.db')
    conn.row_factory = sqlite3.Row  # Set row_factory to allow dictionary-like access
    
    # Create a cursor
    cursor = conn.cursor()
    
    # Update the name column to remove trailing spaces
    cursor.execute("UPDATE BarContents SET name = TRIM(name)")
    
    # Commit the changes
    conn.commit()
    
    # Verify the changes (optional print for debugging)
    updated_rows = cursor.execute("SELECT name FROM BarContents").fetchall()
    for row in updated_rows:
        print(f"Updated name: '{row['name']}'")
    
    # Close the connection
    conn.close()
    print("Database updated successfully. Trailing spaces removed from 'name' column.")

if __name__ == "__main__":
    trim_names()