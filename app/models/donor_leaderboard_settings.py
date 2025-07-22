from app.extensions import db
from datetime import datetime
import json

class DonorLeaderboardSettings(db.Model):
    """
    Leaderboard display settings for streamers.
    Controls how the donor leaderboard appears in overlays.
    """
    __tablename__ = 'donor_leaderboard_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    is_enabled = db.Column(db.Boolean, default=False)
    positions_count = db.Column(db.Integer, default=3)  # 1-10 positions
    show_amounts = db.Column(db.Boolean, default=True)
    show_donation_counts = db.Column(db.Boolean, default=True)
    
    # Visual styling (JSON config)
    throne_styling = db.Column(db.Text)  # JSON: colors, fonts, effects for #1
    podium_styling = db.Column(db.Text)  # JSON: colors, fonts, effects for #2-3
    standard_styling = db.Column(db.Text)  # JSON: colors, fonts, effects for #4+
    global_styling = db.Column(db.Text)  # JSON: background, transparency, fonts
    overlay_token = db.Column(db.String(32), unique=True)  # Secure random token for overlay URL
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        db.UniqueConstraint('user_id', name='unique_user_settings'),
    )
    
    # Relationships
    user = db.relationship('User', backref='donor_leaderboard_settings')
    
    @classmethod
    def get_or_create_for_user(cls, user_id):
        """Get or create settings for user"""
        settings = cls.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = cls(user_id=user_id)
            settings._generate_overlay_token()
            db.session.add(settings)
            db.session.commit()
        elif not settings.overlay_token:
            settings._generate_overlay_token()
            db.session.commit()
        return settings
    
    def _generate_overlay_token(self):
        """Generate a secure random token for overlay URL"""
        import secrets
        import string
        
        # Generate 32-character random string
        alphabet = string.ascii_letters + string.digits
        self.overlay_token = ''.join(secrets.choice(alphabet) for _ in range(32))
    
    def regenerate_overlay_token(self):
        """Regenerate overlay token (for security purposes)"""
        self._generate_overlay_token()
        self.updated_at = datetime.utcnow()
    
    def get_throne_styling(self):
        """Get throne styling configuration"""
        if self.throne_styling:
            try:
                return json.loads(self.throne_styling)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Default throne styling
        return {
            'background_color': '#FFD700',  # Gold
            'text_color': '#1A1A1A',
            'border_color': '#FFA500',
            'font_size': '1.4em',
            'font_weight': 'bold',
            'icon': 'crown',
            'glow_effect': True,
            'animation': 'pulse'
        }
    
    def get_podium_styling(self):
        """Get podium styling configuration"""
        if self.podium_styling:
            try:
                return json.loads(self.podium_styling)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Default podium styling
        return {
            'background_color': '#C0C0C0',  # Silver
            'text_color': '#1A1A1A',
            'border_color': '#A0A0A0',
            'font_size': '1.2em',
            'font_weight': '600',
            'icons': ['medal', 'medal'],  # Silver, Bronze
            'colors': ['#C0C0C0', '#CD7F32'],  # Silver, Bronze
            'animation': 'fade'
        }
    
    def get_standard_styling(self):
        """Get standard styling configuration"""
        if self.standard_styling:
            try:
                return json.loads(self.standard_styling)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Default standard styling
        return {
            'background_color': 'rgba(255, 255, 255, 0.1)',
            'text_color': '#FFFFFF',
            'border_color': 'rgba(255, 255, 255, 0.3)',
            'font_size': '1em',
            'font_weight': 'normal',
            'animation': 'none'
        }
    
    def get_global_styling(self):
        """Get global styling configuration"""
        if self.global_styling:
            try:
                return json.loads(self.global_styling)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Default global styling
        return {
            'font_family': 'Inter, sans-serif',
            'background_transparency': 0.9,
            'border_radius': '15px',
            'padding': '20px',
            'backdrop_filter': 'blur(20px)',
            'container_background': 'rgba(255, 255, 255, 0.1)',
            'container_border': 'rgba(255, 255, 255, 0.3)'
        }
    
    def set_throne_styling(self, styling_dict):
        """Set throne styling configuration"""
        self.throne_styling = json.dumps(styling_dict)
        self.updated_at = datetime.utcnow()
    
    def set_podium_styling(self, styling_dict):
        """Set podium styling configuration"""
        self.podium_styling = json.dumps(styling_dict)
        self.updated_at = datetime.utcnow()
    
    def set_standard_styling(self, styling_dict):
        """Set standard styling configuration"""
        self.standard_styling = json.dumps(styling_dict)
        self.updated_at = datetime.utcnow()
    
    def set_global_styling(self, styling_dict):
        """Set global styling configuration"""
        self.global_styling = json.dumps(styling_dict)
        self.updated_at = datetime.utcnow()
    
    def update_settings(self, **kwargs):
        """Update settings with provided values"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                if key == 'positions_count':
                    # Validate positions count (1-10)
                    value = max(1, min(10, int(value)))
                setattr(self, key, value)
        
        self.updated_at = datetime.utcnow()
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'is_enabled': self.is_enabled,
            'positions_count': self.positions_count,
            'show_amounts': self.show_amounts,
            'show_donation_counts': self.show_donation_counts,
            'throne_styling': self.get_throne_styling(),
            'podium_styling': self.get_podium_styling(),
            'standard_styling': self.get_standard_styling(),
            'global_styling': self.get_global_styling(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<DonorLeaderboardSettings user_id={self.user_id} enabled={self.is_enabled} positions={self.positions_count}>'