# Routes package
from .main import main_bp
from .auth import auth_bp
from .oauth import oauth_bp

__all__ = ['main_bp', 'auth_bp', 'oauth_bp']