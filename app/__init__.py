from flask import Flask
from config import Config
from app.extensions import db, login_manager, migrate, socketio
from datetime import datetime
import logging.config
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Set up logging
    os.makedirs('logs', exist_ok=True)
    logging.config.dictConfig(Config.LOGGING_CONFIG)
    
    # Add template globals
    @app.template_global()
    def moment():
        return datetime.now()
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Import all models for Flask-Migrate
    from app import models
    from app.models import subscription, subscription_payment, user_asset, donation_alert_settings, alert_configuration, tts_usage, donation_payment, donation_goal, marathon
    from app.models import sound_effect, user_sound_settings, sound_effect_donation
    
    # Register blueprints
    from app.routes import main_bp, auth_bp, oauth_bp
    from app.routes.tts import tts_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(oauth_bp)
    app.register_blueprint(tts_bp)
    
    return app