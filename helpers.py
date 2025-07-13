from utils import get_db_connection
from typing import List, Dict, Optional, Tuple

def get_drinks_can_make() -> List[Dict[str, str]]:
    """
    Returns a list of drinks that can be made with the current bar contents.
    Each item contains the drink name and its base spirit.
    """
    conn = get_db_connection()
    query = """
    SELECT DISTINCT r.drink, r.Base_Spirit
    FROM Recipes r
    WHERE NOT EXISTS (
        SELECT 1
        FROM RecipeIngredients ri
        WHERE ri.drink = r.drink
        AND NOT EXISTS (
            SELECT 1
            FROM BarContents bc
            WHERE
                -- Exact name match
                LOWER(ri.ingredient) = LOWER(bc.name)
                OR
                -- Subcategory match
                (LOWER(ri.ingredient) = LOWER(bc.sub_category) AND bc.sub_category IS NOT NULL)
                OR
                -- Category match
                LOWER(ri.ingredient) = LOWER(bc.category)
        )
    )
    """
    drinks = conn.execute(query).fetchall()
    conn.close()
    return [{'drink': row['drink'], 'base_spirit': row['Base_Spirit'] if row['Base_Spirit'] else 'N/A'} for row in drinks]

def get_drinks_missing_one() -> List[Tuple[str, str]]:
    """
    Returns a list of drinks missing exactly one ingredient, along with the missing ingredient(s).
    """
    conn = get_db_connection()
    query = """
    SELECT r.drink, (
        SELECT GROUP_CONCAT(ri.ingredient, ', ') FROM RecipeIngredients ri
        WHERE ri.drink = r.drink
        AND LOWER(ri.ingredient) NOT IN (
            SELECT LOWER(name) FROM BarContents
            UNION
            SELECT LOWER(category) FROM BarContents
            UNION
            SELECT LOWER(sub_category) FROM BarContents WHERE sub_category IS NOT NULL
        )
    ) AS missing_ingredients
    FROM Recipes r
    WHERE (
        SELECT COUNT(*) FROM RecipeIngredients ri
        WHERE ri.drink = r.drink
        AND LOWER(ri.ingredient) NOT IN (
            SELECT LOWER(name) FROM BarContents
            UNION
            SELECT LOWER(category) FROM BarContents
            UNION
            SELECT LOWER(sub_category) FROM BarContents WHERE sub_category IS NOT NULL
        )
    ) > 0
    """
    results = conn.execute(query).fetchall()
    conn.close()
    return [(row['drink'], row['missing_ingredients']) for row in results if row['missing_ingredients']]


def get_drinks_with_replacements() -> List[Dict]:
    """
    Returns a list of drinks that have missing ingredients but where replacements may exist.
    """
    conn = get_db_connection()
    # Get all recipes and their ingredients
    recipes = conn.execute('SELECT drink, Base_Spirit FROM Recipes').fetchall()
    result = []
    
    for recipe in recipes:
        drink_name = recipe['drink']
        recipe_ings = conn.execute('SELECT ingredient FROM RecipeIngredients WHERE drink = ?', (drink_name,)).fetchall()
        missing = []
        replacements = {}
        
        for ing in recipe_ings:
            ing_name = ing['ingredient']
            # Check if the ingredient is missing
            match_found = conn.execute(
                '''
                SELECT 1
                FROM BarContents bc
                WHERE
                    LOWER(?) = LOWER(bc.name)
                    OR (LOWER(?) = LOWER(bc.sub_category) AND bc.sub_category IS NOT NULL)
                    OR LOWER(?) = LOWER(bc.category)
                ''',
                (ing_name, ing_name, ing_name)
            ).fetchone()
            
            if not match_found:
                missing.append(ing_name)
                # Find the category of the missing ingredient
                category = conn.execute(
                    'SELECT category FROM PossibleIngredients WHERE name = ? OR sub_category = ? OR category = ? LIMIT 1',
                    (ing_name, ing_name, ing_name)
                ).fetchone()
                if category:
                    # Get potential replacements from BarContents with the same category
                    replacements[ing_name] = conn.execute(
                        '''
                        SELECT name FROM BarContents
                        WHERE LOWER(category) = LOWER(?) AND LOWER(name) != LOWER(?)
                        ''',
                        (category['category'], ing_name)
                    ).fetchall()
    
        if missing:  # Only include drinks with at least one missing ingredient
            result.append({
                'drink': drink_name,
                'base_spirit': recipe['Base_Spirit'] if recipe['Base_Spirit'] else 'N/A',
                'missing_ingredients': missing,
                'replacements': {k: [r['name'] for r in v] for k, v in replacements.items()}  # Convert tuples to lists
            })
    
    conn.close()
    return result

def fetch_recipe(drink: str) -> Optional[Dict]:
    """
    Fetches the full recipe data from the Recipes table for a specific drink.
    """
    conn = get_db_connection()
    recipe = conn.execute('SELECT * FROM Recipes WHERE drink = ?', (drink,)).fetchone()
    conn.close()
    if recipe:
        recipe_dict = dict(recipe)
        print(f"Recipe for {drink}: {recipe_dict}")  # Debug print
        return recipe_dict
    return None

def fetch_drinks_missing_ingredients() -> List[Dict]:
    """
    Returns drinks that are missing one or more ingredients based on current BarContents.
    """
    conn = get_db_connection()
    
    # Get all recipes
    recipes = conn.execute('SELECT drink, Base_Spirit FROM Recipes').fetchall()
    missing_data = []
    
    for recipe in recipes:
        drink_name = recipe['drink']
        
        # Get recipe ingredients
        recipe_ings = conn.execute('SELECT ingredient FROM RecipeIngredients WHERE drink = ?', (drink_name,)).fetchall()
        missing = []
        
        for ing in recipe_ings:
            ing_name = ing['ingredient']
            # Check if the ingredient matches anything in the user's bar
            match_found = conn.execute(
                '''
                SELECT 1
                FROM BarContents bc
                WHERE
                    LOWER(?) = LOWER(bc.name)
                    OR (LOWER(?) = LOWER(bc.sub_category) AND bc.sub_category IS NOT NULL)
                    OR LOWER(?) = LOWER(bc.category)
                ''',
                (ing_name, ing_name, ing_name)
            ).fetchone()
            
            if not match_found:
                missing.append(ing_name)
        
        if missing:
            missing_data.append({
                'drink': drink_name,
                'base_spirit': recipe['Base_Spirit'] if recipe['Base_Spirit'] else 'N/A',
                'missing': missing
            })
    
    conn.close()
    return missing_data

def fetch_drinks_with_base() -> List[Tuple[str, List[str]]]:
    """
    Returns drinks where the base spirit is in the bar, but one or more ingredients are missing.
    """
    conn = get_db_connection()
    query = """
    SELECT r.drink, (
        SELECT GROUP_CONCAT(ri.ingredient) FROM RecipeIngredients ri
        WHERE ri.drink = r.drink
        AND LOWER(ri.ingredient) NOT IN (
            SELECT LOWER(name) FROM BarContents
            UNION
            SELECT LOWER(category) FROM BarContents
            UNION
            SELECT LOWER(sub_category) FROM BarContents WHERE sub_category IS NOT NULL
        )
    ) AS missing
    FROM Recipes r
    WHERE r.Base_Spirit IN (SELECT sub_category FROM BarContents WHERE sub_category IS NOT NULL)
    AND EXISTS (
        SELECT 1 FROM RecipeIngredients ri
        WHERE ri.drink = r.drink
        AND LOWER(ri.ingredient) NOT IN (
            SELECT LOWER(name) FROM BarContents
            UNION
            SELECT LOWER(category) FROM BarContents
            UNION
            SELECT LOWER(sub_category) FROM BarContents WHERE sub_category IS NOT NULL
        )
    )
    """
    results = conn.execute(query).fetchall()
    conn.close()
    return [(row['drink'], row['missing'].split(',') if row['missing'] else []) for row in results]