from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from utils import get_db_connection, close_db_connection, load_lists


SPIRIT_CATEGORIES = {
    'absinthe',
    'aperitif',
    'bitters',
    'brandy',
    'cognac',
    'digestif',
    'fortified wine',
    'gin',
    'liqueur',
    'mezcal',
    'rum',
    'tequila',
    'vermouth',
    'vodka',
    'whiskey',
}


def get_drinks_can_make() -> List[Dict[str, str]]:
    """
    Returns a list of drinks that can be made with the current bar contents.
    Each item contains the drink name, base spirit, a resolved spirit category, and a list of spirit ingredients.
    """
    lists = load_lists()
    category_lookup = _build_category_lookup(lists)

    conn = get_db_connection()
    try:
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
                    LOWER(ri.ingredient) = LOWER(bc.name)
                    OR (LOWER(ri.ingredient) = LOWER(bc.sub_category) AND bc.sub_category IS NOT NULL)
                    OR LOWER(ri.ingredient) = LOWER(bc.category)
            )
        )
        """
        drinks = conn.execute(query).fetchall()
        spirit_lookup = _map_spirit_ingredients(conn, lists, category_lookup)
    finally:
        close_db_connection()

    result = []
    for row in drinks:
        drink_name = row['drink']
        base_spirit_raw = (row['base_spirit'] or '').strip()
        base_spirit = base_spirit_raw if base_spirit_raw else 'N/A'
        resolved_category = category_lookup.get(base_spirit_raw.lower() if base_spirit_raw else '', base_spirit_raw or 'Unknown')
        resolved_category = (resolved_category or 'Unknown').strip() or 'Unknown'
        spirits = spirit_lookup.get(drink_name, [])
        spirit_summary = ' | '.join(spirits)
        result.append(
            {
                'drink': drink_name,
                'base_spirit': base_spirit,
                'base_spirit_category': resolved_category,
                'spirits': spirits,
                'spirit_summary': spirit_summary,
            }
        )
    return result


def _build_category_lookup(lists: Dict) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    subcategories = lists.get('subcategories', {})
    for category, subs in subcategories.items():
        lookup[category.lower()] = category
        for sub in subs:
            lookup[sub.lower()] = category
    for category in lists.get('categories', []):
        lookup.setdefault(category.lower(), category)
    return lookup


def _map_spirit_ingredients(conn, lists, category_lookup) -> Dict[str, List[str]]:
    """
    Build a mapping of drink name -> list of spirit ingredient names using possibleingredients metadata.
    """

    possible_lookup = {}
    rows = conn.execute('SELECT name, category, sub_category FROM possibleingredients').fetchall()
    for row in rows:
        name = (row['name'] or '').strip()
        if not name:
            continue
        possible_lookup[name.lower()] = {
            'category': (row['category'] or '').strip(),
            'sub_category': (row['sub_category'] or '').strip(),
        }

    spirits_by_drink: Dict[str, List[str]] = defaultdict(list)
    seen: Dict[str, set] = defaultdict(set)

    ingredient_rows = conn.execute(
        'SELECT drink, ingredient FROM recipeingredients ORDER BY id'
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

        if (resolved_category or '').strip().lower() in SPIRIT_CATEGORIES:
            bucket = seen[drink]
            if ingredient_name not in bucket:
                spirits_by_drink[drink].append(ingredient_name)
                bucket.add(ingredient_name)

    return spirits_by_drink

def get_drinks_missing_one() -> List[Tuple[str, str]]:
    """
    Returns a list of drinks missing exactly one ingredient, along with the missing ingredient(s).
    """
    conn = get_db_connection()
    try:
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
    finally:
        close_db_connection()
    return [(row['drink'], row['missing_ingredients']) for row in results if row['missing_ingredients']]


def get_drinks_with_replacements() -> List[Dict]:
    """
    Returns a list of drinks that have missing ingredients but where replacements may exist.
    """
    conn = get_db_connection()
    try:
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
    finally:
        close_db_connection()
    return result

def fetch_recipe(drink: str) -> Optional[Dict]:
    """
    Fetches the full recipe data from the Recipes table for a specific drink.
    """
    conn = get_db_connection()
    try:
        recipe = conn.execute('SELECT * FROM Recipes WHERE drink = ?', (drink,)).fetchone()
    finally:
        close_db_connection()
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
    try:
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
    finally:
        close_db_connection()
    return missing_data

def fetch_drinks_with_base() -> List[Tuple[str, List[str]]]:
    """
    Returns drinks where the base spirit is in the bar, but one or more ingredients are missing.
    """
    conn = get_db_connection()
    try:
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
    finally:
        close_db_connection()
    return [(row['drink'], row['missing'].split(',') if row['missing'] else []) for row in results]
