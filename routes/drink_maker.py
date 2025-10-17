from flask import Blueprint, render_template, redirect, url_for
from helpers import get_drinks_missing_one, get_drinks_with_replacements

drink_maker_bp = Blueprint('drink_maker', __name__)

# Drink maker route
@drink_maker_bp.route('/drink-maker')
def drink_maker():
    return redirect(url_for('recipes.recipes'))

# Drinks missing ingredients route
@drink_maker_bp.route('/missing_one')
def missing_one():
    missing_one = get_drinks_missing_one()
    return render_template('missing_one.html', missing_one=missing_one)

@drink_maker_bp.route('/replacements')
def replacements():
    drinks_with_replacements = get_drinks_with_replacements()
    return render_template('replacements.html', replacements=drinks_with_replacements)
