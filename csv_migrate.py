import sqlite3
import pandas as pd

# Connect to SQLite database
conn = sqlite3.connect('cocktail_app.db')

# Load and save bar contents
bar_df = pd.read_csv('bar_contents.csv')
bar_df.to_sql('BarContents', conn, if_exists='replace', index=False)

# Load drink recipes CSV
recipes_df = pd.read_csv('drink_recipes.csv', index_col=0)

# Insert drink details into Recipes table
details = recipes_df.loc[['Glass', 'Garnish', 'Method', 'Ice', 'Notes', 'Base Spirit']].T
details.columns = [col.replace(' ', '_') for col in details.columns]  # Match schema
details.reset_index().rename(columns={'index': 'drink'}).to_sql('Recipes', conn, if_exists='replace', index=False)

# Insert ingredients into RecipeIngredients
ingredients_data = []
for drink in recipes_df.columns[1:]:  # Skip 'Measurement' column
    for ing in recipes_df.index:
        if ing not in ['Glass', 'Garnish', 'Method', 'Ice', 'Notes', 'Base Spirit']:
            qty = recipes_df.loc[ing, drink]
            if pd.notna(qty):
                unit = recipes_df.loc[ing, recipes_df.columns[0]]  # Measurement from Column B
                ingredients_data.append((drink, ing, qty, unit))

pd.DataFrame(ingredients_data, columns=['drink', 'ingredient', 'quantity', 'unit']).to_sql('RecipeIngredients', conn, if_exists='replace', index=False)

conn.close()