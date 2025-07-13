import pandas as pd

# Read bar contents CSV
bar_df = pd.read_csv("bar_contents.csv")
bar_df["Ingredient"] = bar_df["Ingredient"].str.strip()  # Remove whitespace
bar_ingredients_lower = set(ing.lower() for ing in bar_df["Ingredient"])  # Case-insensitive set

# Read drink recipes CSV
recipes_df = pd.read_csv("drink_recipes.csv", index_col=0)  # First column as index
recipes_df.index = recipes_df.index.str.strip()  # Clean index

# Define detail labels to separate recipe details from ingredients
detail_labels = ["Glass", "Garnish", "Method", "Ice", "Notes", "Base Spirit"]

# Get drink names (exclude "Measurement" column)
drinks = recipes_df.columns[1:]

# Initialize result lists
can_make = []
missing_one = []
have_base_spirit = []

# Process each drink
for drink in drinks:
    # Extract base spirit
    base_spirit = recipes_df.loc["Base Spirit", drink].strip()
    
    # Get required ingredients (rows not in detail_labels with non-null values)
    required_ingredients = [
        index for index in recipes_df.index 
        if index not in detail_labels and pd.notna(recipes_df.loc[index, drink])
    ]
    
    # Find missing ingredients
    missing_ingredients = [
        ing for ing in required_ingredients 
        if ing.lower() not in bar_ingredients_lower
    ]
    
    # Categorize the drink
    if not missing_ingredients:
        can_make.append(drink)
    else:
        if len(missing_ingredients) == 1:
            missing_one.append((drink, missing_ingredients[0]))
        if base_spirit.lower() in bar_ingredients_lower:
            have_base_spirit.append((drink, missing_ingredients))

# Function to get recipe details
def get_recipe(drink):
    # Get details (e.g., Glass, Garnish), only including non-empty values
    details = {}
    for label in detail_labels:
        value = recipes_df.loc[label, drink]
        if pd.notna(value) and value != "":
            details[label] = value
    
    # Get ingredients with quantities and units
    ingredients = []
    for index in recipes_df.index:
        if index not in detail_labels and pd.notna(recipes_df.loc[index, drink]):
            quantity = str(recipes_df.loc[index, drink])  # Convert quantity to string
            unit = recipes_df.loc[index, "Measurement"]
            if pd.notna(unit):
                ingredient_str = f"{quantity} {unit} {index}"
            else:
                ingredient_str = f"{quantity} {index}"  # Omit unit if missing
            ingredients.append(ingredient_str)
    
    # Format the recipe
    recipe = f"Drink: {drink}\n"
    for label, value in details.items():
        recipe += f"{label}: {value}\n"
    recipe += "Ingredients:\n"
    for ing in ingredients:
        recipe += f"- {ing}\n"
    return recipe

# Display results
print("Drinks I can make:")
for drink in sorted(can_make):
    print(get_recipe(drink))
    print("-" * 40)  # Separator line for readability

print("\nDrinks where I'm missing one ingredient:")
for drink, missing in sorted(missing_one):
    print(f"- {drink}: missing {missing}")

print("\nDrinks where I have the base spirit but missing other ingredients:")
for drink, missing in sorted(have_base_spirit):
    print(f"- {drink}: missing {', '.join(missing)}")