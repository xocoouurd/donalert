import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Environment
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Security headers for production
    SESSION_COOKIE_SECURE = FLASK_ENV == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Database configuration
    db_user = os.environ.get('DB_USER', 'xocoo')
    db_password = os.environ.get('DB_PASSWORD', 'Nuutsug123%21%40%23%24')  # Already URL encoded
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_name = os.environ.get('DB_NAME', 'py_donalert')
    
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{db_user}:{db_password}"
        f"@{db_host}/{db_name}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File upload configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_IMAGE_SIZE_MB', 16)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # Server configuration
    # Keep SERVER_NAME for OAuth/payment functionality in both dev and production
    # Socket.IO will work with proper client configuration
    SERVER_NAME = os.environ.get('SERVER_NAME', 'donalert.invictamotus.com')
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')
    SOCKETIO_URL = os.environ.get('SOCKETIO_URL', 'http://localhost:5013')
    
    # OAuth Configuration
    TWITCH_CLIENT_ID = os.environ.get('TWITCH_CLIENT_ID')
    TWITCH_CLIENT_SECRET = os.environ.get('TWITCH_CLIENT_SECRET')  # Note: Fixed typo in .env
    
    YOUTUBE_CLIENT_ID = os.environ.get('YOUTUBE_CLIENT_ID')
    YOUTUBE_CLIENT_SECRET = os.environ.get('YOUTUBE_CLIENT_SECRET')
    
    KICK_CLIENT_ID = os.environ.get('KICK_CLIENT_ID')
    KICK_CLIENT_SECRET = os.environ.get('KICK_CLIENT_SECRET')
    
    # Logging configuration
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
            }
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'detailed'
            },
            'file': {
                'level': 'INFO',
                'class': 'logging.FileHandler',
                'filename': 'logs/app.log',
                'formatter': 'detailed'
            },
            'marathon': {
                'level': 'INFO',
                'class': 'logging.FileHandler',
                'filename': 'logs/marathon.log',
                'formatter': 'detailed'
            },
            'donation': {
                'level': 'INFO',
                'class': 'logging.FileHandler',
                'filename': 'logs/donation.log',
                'formatter': 'detailed'
            }
        },
        'loggers': {
            'app.models.marathon': {
                'handlers': ['marathon'],
                'level': 'INFO',
                'propagate': True
            },
            'app.models.donation_payment': {
                'handlers': ['donation'],
                'level': 'INFO',
                'propagate': True
            }
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': 'INFO'
        }
    }