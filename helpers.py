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


def get_drinks_can_make() -> list[dict[str, str]]:
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT r.drink, r.base_spirit
            FROM recipes r
            WHERE NOT EXISTS (
            SELECT 1
            FROM recipeingredients ri
            WHERE ri.drink = r.drink
                AND NOT EXISTS (
                    SELECT 1
                    FROM possibleingredients pi
                    WHERE pi.in_bar = TRUE
                        AND (
                            lower(trim(ri.ingredient)) = lower(trim(pi.name))
                            OR lower(trim(ri.ingredient)) = lower(trim(pi.category))
                            OR (
                                pi.sub_category IS NOT NULL
                                AND lower(trim(ri.ingredient)) = lower(trim(pi.sub_category))
                            )
                        )
                    )
                )
            """
        ).fetchall()
    finally:
        close_db_connection()

    return [
        {
            "drink": row["drink"],
            "base_spirit": (row["base_spirit"] or "").strip(),
        }
        for row in rows
    ]


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

def get_drinks_missing_one() -> list[tuple[str, str]]:
    """
    Returns drinks missing exactly one ingredient, along with that missing ingredient.
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            WITH available AS (
              SELECT lower(name) AS v FROM possibleingredients WHERE in_bar = TRUE
              UNION
              SELECT lower(category) AS v FROM possibleingredients WHERE in_bar = TRUE AND category IS NOT NULL AND category <> ''
              UNION
              SELECT lower(sub_category) AS v FROM possibleingredients WHERE in_bar = TRUE AND sub_category IS NOT NULL AND sub_category <> ''
            ),
            missing AS (
              SELECT
                ri.drink,
                ri.ingredient
              FROM recipeingredients ri
              WHERE lower(ri.ingredient) NOT IN (SELECT v FROM available)
            ),
            missing_count AS (
              SELECT drink, COUNT(*) AS cnt
              FROM missing
              GROUP BY drink
            )
            SELECT
              m.drink,
              string_agg(m.ingredient, ', ' ORDER BY m.ingredient) AS missing_ingredients
            FROM missing m
            JOIN missing_count mc
              ON mc.drink = m.drink
            WHERE mc.cnt = 1
            GROUP BY m.drink
            ORDER BY lower(m.drink)
            """
        ).fetchall()
    finally:
        close_db_connection()

    return [(row["drink"], row["missing_ingredients"]) for row in rows]


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
            recipe_ings = conn.execute('SELECT ingredient FROM RecipeIngredients WHERE drink = %s', (drink_name,)).fetchall()
            missing = []
            replacements = {}
            
            for ing in recipe_ings:
                ing_name = ing['ingredient']
                # Check if the ingredient is missing
                # match_found using in_bar
                match_found = conn.execute(
                    """
                    SELECT 1
                    FROM possibleingredients pi
                    WHERE pi.in_bar = TRUE
                    AND (
                        lower(%s) = lower(pi.name)
                        OR lower(%s) = lower(pi.category)
                        OR (pi.sub_category IS NOT NULL AND lower(%s) = lower(pi.sub_category))
                    )
                    LIMIT 1
                    """,
                    (ing_name, ing_name, ing_name),
                ).fetchone()
                
                if not match_found:
                    missing.append(ing_name)
                    # Find the category of the missing ingredient
                    category = conn.execute(
                        'SELECT category FROM PossibleIngredients WHERE name = %s OR sub_category = %s OR category = %s LIMIT 1',
                        (ing_name, ing_name, ing_name)
                    ).fetchone()
                    if category:
                        # Get potential replacements from possibleingredients.in_bar with the same category
                        replacements[ing_name] = conn.execute(
                            """
                            SELECT name
                            FROM possibleingredients
                            WHERE in_bar = TRUE
                            AND lower(category) = lower(%s)
                            AND lower(name) <> lower(%s)
                            ORDER BY name
                            """,
                            (category["category"], ing_name),
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
        recipe = conn.execute('SELECT * FROM Recipes WHERE drink = %s', (drink,)).fetchone()
    finally:
        close_db_connection()
    if recipe:
        recipe_dict = dict(recipe)
        print(f"Recipe for {drink}: {recipe_dict}")  # Debug print
        return recipe_dict
    return None

def fetch_drinks_missing_ingredients() -> list[dict]:
    """
    Returns drinks that are missing one or more ingredients based on in_bar.
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            WITH available AS (
              SELECT lower(name) AS v FROM possibleingredients WHERE in_bar = TRUE
              UNION
              SELECT lower(category) AS v FROM possibleingredients WHERE in_bar = TRUE AND category IS NOT NULL AND category <> ''
              UNION
              SELECT lower(sub_category) AS v FROM possibleingredients WHERE in_bar = TRUE AND sub_category IS NOT NULL AND sub_category <> ''
            ),
            missing AS (
              SELECT
                r.drink,
                COALESCE(r.base_spirit, '') AS base_spirit,
                ri.ingredient
              FROM recipes r
              JOIN recipeingredients ri
                ON ri.drink = r.drink
              WHERE lower(ri.ingredient) NOT IN (SELECT v FROM available)
            )
            SELECT
              drink,
              base_spirit,
              array_agg(ingredient ORDER BY ingredient) AS missing
            FROM missing
            GROUP BY drink, base_spirit
            ORDER BY lower(base_spirit), lower(drink)
            """
        ).fetchall()
    finally:
        close_db_connection()

    return [
        {
            "drink": row["drink"],
            "base_spirit": row["base_spirit"] or "N/A",
            "missing": row["missing"] or [],
        }
        for row in rows
    ]

def fetch_drinks_with_base() -> list[tuple[str, list[str]]]:
    """
    Returns drinks where the base spirit is in the bar (match against owned sub_category),
    but one or more ingredients are missing.
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            WITH available AS (
              SELECT lower(name) AS v FROM possibleingredients WHERE in_bar = TRUE
              UNION
              SELECT lower(category) AS v FROM possibleingredients WHERE in_bar = TRUE AND category IS NOT NULL AND category <> ''
              UNION
              SELECT lower(sub_category) AS v FROM possibleingredients WHERE in_bar = TRUE AND sub_category IS NOT NULL AND sub_category <> ''
            ),
            owned_base AS (
              SELECT DISTINCT lower(sub_category) AS v
              FROM possibleingredients
              WHERE in_bar = TRUE AND sub_category IS NOT NULL AND sub_category <> ''
            ),
            missing AS (
              SELECT
                r.drink,
                ri.ingredient
              FROM recipes r
              JOIN recipeingredients ri
                ON ri.drink = r.drink
              WHERE lower(ri.ingredient) NOT IN (SELECT v FROM available)
            )
            SELECT
              r.drink,
              array_agg(m.ingredient ORDER BY m.ingredient) AS missing
            FROM recipes r
            JOIN missing m
              ON m.drink = r.drink
            WHERE lower(COALESCE(r.base_spirit, '')) IN (SELECT v FROM owned_base)
            GROUP BY r.drink
            ORDER BY lower(r.drink)
            """
        ).fetchall()
    finally:
        close_db_connection()

    return [(row["drink"], row["missing"] or []) for row in rows]
