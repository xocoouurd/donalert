from datetime import datetime
import secrets
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Authentication fields
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    overlay_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    
    # Profile information
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    display_name = db.Column(db.String(100), nullable=True)  # For public display
    
    # Status fields
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Bank account information for donation payments
    bank_account_name = db.Column(db.String(100), nullable=True)
    bank_account_number = db.Column(db.String(50), nullable=True)
    bank_iban = db.Column(db.String(24), nullable=True)  # IBAN format: MN + 18 digits
    bank_code = db.Column(db.String(10), nullable=True)
    bank_name = db.Column(db.String(100), nullable=True)
    is_bank_verified = db.Column(db.Boolean, default=False)
    
    # API/Integration fields (will be modularized later)
    # api_key = db.Column(db.String(64), unique=True, nullable=True)
    # webhook_url = db.Column(db.String(255), nullable=True)
    
    def set_password(self, password):
        """Hash and store password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_overlay_token(self):
        """Generate a secure random overlay token"""
        self.overlay_token = secrets.token_urlsafe(32)  # 32 bytes = 43 characters URL-safe
        return self.overlay_token
    
    def get_overlay_token(self):
        """Get overlay token, generating one if it doesn't exist"""
        if not self.overlay_token:
            self.generate_overlay_token()
            db.session.commit()
        return self.overlay_token
    
    def regenerate_overlay_token(self):
        """Regenerate overlay token (for security purposes)"""
        self.generate_overlay_token()
        db.session.commit()
        return self.overlay_token
    
    def get_full_name(self):
        """Return full name or username if no name provided"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def get_display_name(self):
        """Return display name for public use"""
        # First try to get display name from primary platform
        primary_connection = next((conn for conn in self.platform_connections if getattr(conn, 'is_primary', False)), None)
        
        if primary_connection and primary_connection.platform_data:
            display_name = self._extract_display_name_from_connection(primary_connection)
            if display_name:
                return display_name
        
        # Fallback to user's stored display name
        if self.display_name:
            return self.display_name
        
        # Final fallback to full name or username
        return self.get_full_name()
    
    def _extract_display_name_from_connection(self, connection):
        """Extract display name from a platform connection"""
        platform_name = connection.platform_type.name.lower()
        
        if platform_name == 'twitch':
            # Twitch uses "display_name"
            if 'display_name' in connection.platform_data:
                return connection.platform_data['display_name']
        elif platform_name == 'youtube':
            # YouTube/Google uses "name"
            if 'name' in connection.platform_data:
                return connection.platform_data['name']
        elif platform_name == 'kick':
            # Kick uses "name"
            if 'name' in connection.platform_data:
                return connection.platform_data['name']
        
        # Fallback: check for common field names
        for field in ['display_name', 'name', 'username', 'login']:
            if field in connection.platform_data and connection.platform_data[field]:
                return connection.platform_data[field]
        
        return None
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    # Relationships
    platform_connections = db.relationship('PlatformConnection', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def get_platform_connection(self, platform_type):
        """Get connection for a specific platform"""
        from app.models.platform_connection import PlatformConnection
        return PlatformConnection.query.filter_by(
            user_id=self.id, 
            platform_type=platform_type
        ).first()
    
    def has_platform_connection(self, platform_type):
        """Check if user has a connection to specific platform"""
        return self.get_platform_connection(platform_type) is not None
    
    def get_profile_picture(self):
        """Get user's profile picture from platform connections"""
        # First try to get profile picture from primary platform
        primary_connection = next((conn for conn in self.platform_connections if getattr(conn, 'is_primary', False)), None)
        
        if primary_connection and primary_connection.platform_data:
            picture = self._extract_profile_picture_from_connection(primary_connection)
            if picture:
                return picture
        
        # Fallback: try to get profile picture from any platform connection
        for connection in self.platform_connections:
            if connection.platform_data:
                picture = self._extract_profile_picture_from_connection(connection)
                if picture:
                    return picture
        
        # Return None if no profile picture found
        return None
    
    def _extract_profile_picture_from_connection(self, connection):
        """Extract profile picture from a platform connection"""
        platform_name = connection.platform_type.name.lower()
        
        if platform_name == 'twitch':
            # Twitch uses "profile_image_url"
            if 'profile_image_url' in connection.platform_data:
                return connection.platform_data['profile_image_url']
        elif platform_name == 'youtube':
            # YouTube/Google uses "picture"
            if 'picture' in connection.platform_data:
                return connection.platform_data['picture']
        elif platform_name == 'kick':
            # Kick uses "profile_picture"
            if 'profile_picture' in connection.platform_data:
                return connection.platform_data['profile_picture']
        
        # Fallback: check for common field names
        for field in ['picture', 'profile_image_url', 'profile_picture', 'avatar_url', 'avatar']:
            if field in connection.platform_data and connection.platform_data[field]:
                return connection.platform_data[field]
        
        return None
    
    def get_profile_picture_or_default(self):
        """Get profile picture or return default avatar URL"""
        picture = self.get_profile_picture()
        if picture:
            return picture
        
        # Return a default avatar (you can customize this)
        return f"https://ui-avatars.com/api/?name={self.get_display_name()}&background=6366f1&color=fff&size=96"
    
    def get_primary_platform(self):
        """Get the primary platform the user is signed in with"""
        # Check if user has a preferred platform set
        primary_connection = next((conn for conn in self.platform_connections if getattr(conn, 'is_primary', False)), None)
        if primary_connection:
            return primary_connection.platform_type.name.lower()
        
        # Return the first connected platform as fallback
        for connection in self.platform_connections:
            if connection.platform_type:
                return connection.platform_type.name.lower()
        return None
    
    def set_primary_platform(self, platform_type):
        """Set a platform as the primary platform"""
        from app.models.platform_connection import PlatformType
        
        # Reset all platforms to not primary
        for connection in self.platform_connections:
            if hasattr(connection, 'is_primary'):
                connection.is_primary = False
        
        # Set the specified platform as primary
        if isinstance(platform_type, str):
            platform_type = PlatformType[platform_type.upper()]
        
        target_connection = self.get_platform_connection(platform_type)
        if target_connection:
            target_connection.is_primary = True
            db.session.commit()
            return True
        return False
    
    def get_current_subscription(self):
        """Get user's current active subscription"""
        from app.models.subscription import Subscription, SubscriptionStatus
        return Subscription.query.filter_by(
            user_id=self.id,
            status=SubscriptionStatus.ACTIVE
        ).order_by(Subscription.end_date.desc()).first()
    
    def has_active_subscription(self):
        """Check if user has an active subscription"""
        subscription = self.get_current_subscription()
        return subscription and subscription.is_active()
    
    def is_subscription_expired(self):
        """Check if user's subscription has expired"""
        subscription = self.get_current_subscription()
        return not subscription or subscription.is_expired()
    
    def get_subscription_status(self):
        """Get user's subscription status info"""
        subscription = self.get_current_subscription()
        
        if not subscription:
            return {
                'has_subscription': False,
                'is_trial': False,
                'is_active': False,
                'is_expired': True,
                'is_in_grace_period': False,
                'days_remaining': 0,
                'hours_remaining_in_grace': 0,
                'tier': None,
                'tier_display': 'Багц байхгүй'
            }
        
        from app.models.subscription import LegacySubscriptionTier, BillingCycle
        # Check for trial using new or legacy system
        is_trial = (
            subscription.billing_cycle == BillingCycle.TRIAL if subscription.billing_cycle 
            else subscription.tier == LegacySubscriptionTier.FREE_TRIAL
        )
        
        return {
            'has_subscription': True,
            'is_trial': is_trial,
            'is_active': subscription.is_active(),
            'is_expired': subscription.is_expired(),
            'is_in_grace_period': subscription.is_in_grace_period(),
            'days_remaining': subscription.days_remaining(),
            'hours_remaining_in_grace': subscription.hours_remaining_in_grace(),
            'tier': subscription.tier,
            'tier_display': subscription.get_tier_display_name(),
            'end_date': subscription.end_date
        }
    
    def create_free_trial(self):
        """Create a free trial subscription for this user"""
        from app.models.subscription import Subscription
        return Subscription.create_free_trial(self.id)
    
    def can_create_free_trial(self):
        """Check if user is eligible for a free trial"""
        from app.models.subscription import Subscription, LegacySubscriptionTier, BillingCycle
        
        # Check if user already has a subscription
        if self.get_current_subscription():
            return False
        
        # Check if user has ever had a free trial before (check both systems)
        previous_trial = Subscription.query.filter(
            (Subscription.user_id == self.id) &
            (
                (Subscription.tier == LegacySubscriptionTier.FREE_TRIAL) |
                (Subscription.billing_cycle == BillingCycle.TRIAL)
            )
        ).first()
        
        return previous_trial is None
    
    def has_bank_account(self):
        """Check if user has bank account information"""
        return bool(self.bank_iban and self.bank_account_name and self.bank_code)
    
    def set_bank_account(self, account_name, account_number, bank_iban, bank_code, bank_name=None):
        """Set user's bank account information"""
        self.bank_account_name = account_name
        self.bank_account_number = account_number
        self.bank_iban = bank_iban
        self.bank_code = bank_code
        self.bank_name = bank_name
        self.is_bank_verified = False  # Reset verification status
        db.session.commit()
    
    def get_bank_account_info(self):
        """Get user's bank account information"""
        if not self.has_bank_account():
            return None
        
        return {
            'account_name': self.bank_account_name,
            'account_number': self.bank_account_number,
            'bank_iban': self.bank_iban,
            'bank_code': self.bank_code,
            'bank_name': self.bank_name,
            'is_verified': self.is_bank_verified
        }
    
    def get_formatted_iban(self):
        """Get formatted IBAN with spaces for display"""
        if not self.bank_iban or len(self.bank_iban) < 20:
            return self.bank_iban
        
        # Format: MN75 0015 00 1205284753
        iban = self.bank_iban
        return f"{iban[:4]} {iban[4:8]} {iban[8:10]} {iban[10:]}"
    
    def verify_bank_account(self):
        """Mark bank account as verified"""
        self.is_bank_verified = True
        db.session.commit()
    
    def clear_bank_account(self):
        """Clear bank account information"""
        self.bank_account_name = None
        self.bank_account_number = None
        self.bank_iban = None
        self.bank_code = None
        self.bank_name = None
        self.is_bank_verified = False
        db.session.commit()
    
    def __repr__(self):
        return f'<User {self.username}>'