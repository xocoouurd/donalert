from functools import wraps
from flask import redirect, url_for, flash, request
from flask_login import current_user

def subscription_required(f):
    """Decorator to require an active subscription"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Нэвтрэх шаардлагатай', 'error')
            return redirect(url_for('auth.login'))
        
        if not current_user.has_active_subscription():
            flash('Үйлчилгээ ашиглахын тулд багц худалдан авна уу', 'error')
            return redirect(url_for('subscription.plans'))
        
        return f(*args, **kwargs)
    return decorated_function

def trial_or_subscription_required(f):
    """Decorator to require either trial or active subscription"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Нэвтрэх шаардлагатай', 'error')
            return redirect(url_for('auth.login'))
        
        subscription_status = current_user.get_subscription_status()
        
        if not subscription_status['is_active']:
            if subscription_status['is_expired']:
                flash('Таны багц дууссан байна. Үргэлжлүүлэхийн тулд сэргээнэ үү', 'error')
                return redirect(url_for('subscription.plans'))
            else:
                flash('Үйлчилгээ ашиглахын тулд багц худалдан авна уу', 'error')
                return redirect(url_for('subscription.plans'))
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Нэвтрэх шаардлагатай', 'error')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin:
            flash('Зөвхөн админ хандах боломжтой', 'error')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def check_subscription_status():
    """Middleware function to check subscription status on each request"""
    if current_user.is_authenticated:
        subscription_status = current_user.get_subscription_status()
        
        # Add subscription info to request context
        request.subscription_status = subscription_status
        
        # Check if subscription is about to expire (3 days warning)
        if (subscription_status['is_active'] and 
            subscription_status['days_remaining'] <= 3 and 
            not subscription_status['is_trial']):
            flash(f'Таны багц {subscription_status["days_remaining"]} хоногийн дараа дуусна', 'warning')
        
        # Check if trial is about to expire (1 day warning)
        if (subscription_status['is_trial'] and 
            subscription_status['is_active'] and 
            subscription_status['days_remaining'] <= 1):
            flash(f'Таны үнэгүй туршилт {subscription_status["days_remaining"]} хоногийн дараа дуусна', 'warning')