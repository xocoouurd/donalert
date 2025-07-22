from datetime import datetime
from app.extensions import db

class UserSoundSettings(db.Model):
    __tablename__ = 'user_sound_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    is_enabled = db.Column(db.Boolean, default=False)
    price_per_sound = db.Column(db.Numeric(10,2), default=1000.00)
    volume_level = db.Column(db.Integer, default=70)  # Volume percentage (0-100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', name='unique_user_sound_settings'),
    )
    
    user = db.relationship('User', backref='sound_settings')
    
    @classmethod
    def get_or_create_for_user(cls, user_id):
        """Get existing settings or create new ones for user"""
        settings = cls.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = cls(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'is_enabled': self.is_enabled,
            'price_per_sound': float(self.price_per_sound) if self.price_per_sound else 0,
            'volume_level': self.volume_level if self.volume_level is not None else 70,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def update_settings(self, is_enabled=None, price_per_sound=None, volume_level=None):
        """Update settings with new values"""
        if is_enabled is not None:
            self.is_enabled = is_enabled
        if price_per_sound is not None:
            self.price_per_sound = price_per_sound
        if volume_level is not None:
            # Ensure volume is between 0 and 100
            self.volume_level = max(0, min(100, int(volume_level)))
        
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def __repr__(self):
        return f'<UserSoundSettings user_id={self.user_id} enabled={self.is_enabled}>'