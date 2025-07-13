import sqlite3

conn = sqlite3.connect('cocktail_app.db')
conn.execute('''
    CREATE TABLE BarContents_new (
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        sub_category TEXT,
        PRIMARY KEY (name)
    )
''')
conn.execute('''
    INSERT INTO BarContents_new (name, category, sub_category)
    SELECT ingredient, category, NULL FROM BarContents
''')
conn.execute('DROP TABLE BarContents')
conn.execute('ALTER TABLE BarContents_new RENAME TO BarContents')
conn.commit()
conn.close()
print("BarContents table migrated successfully.")