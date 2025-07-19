from datetime import datetime, timedelta
from sqlalchemy import Numeric, Enum
from app.extensions import db
import enum

class PlatformType(enum.Enum):
    TWITCH = "twitch"
    YOUTUBE = "youtube"
    KICK = "kick"

class PlatformConnection(db.Model):
    __tablename__ = 'platform_connections'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key to user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Platform details
    platform_type = db.Column(Enum(PlatformType), nullable=False)
    platform_user_id = db.Column(db.String(100), nullable=False)  # Platform's internal user ID
    platform_username = db.Column(db.String(100), nullable=False)  # Display name on platform
    platform_email = db.Column(db.String(255), nullable=True)  # Email from platform (if available)
    
    # OAuth tokens
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Platform-specific data
    platform_data = db.Column(db.JSON, nullable=True)  # Store platform-specific info
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_primary = db.Column(db.Boolean, default=False)  # Primary platform for the user
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sync = db.Column(db.DateTime, nullable=True)
    
    # Unique constraint: one connection per user per platform
    __table_args__ = (
        db.UniqueConstraint('user_id', 'platform_type', name='_user_platform_uc'),
    )
    
    def is_token_expired(self):
        """Check if access token is expired"""
        if not self.token_expires_at:
            return False
        return datetime.utcnow() > self.token_expires_at
    
    def update_tokens(self, access_token, refresh_token=None, expires_in=None):
        """Update OAuth tokens"""
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        if expires_in:
            self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def __repr__(self):
        return f'<PlatformConnection {self.platform_type.value}:{self.platform_username}>'