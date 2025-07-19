from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from app.models.user import User
from app.extensions import db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Амжилттай гарлаа.', 'info')
    
    # Check if there's a next URL to redirect to
    next_url = request.args.get('next')
    if next_url:
        return redirect(next_url)
    
    return redirect(url_for('main.home'))

