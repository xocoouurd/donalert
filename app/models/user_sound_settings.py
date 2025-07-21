from datetime import datetime
from app.extensions import db

class UserSoundSettings(db.Model):
    __tablename__ = 'user_sound_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    is_enabled = db.Column(db.Boolean, default=False)
    price_per_sound = db.Column(db.Numeric(10,2), default=1000.00)
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
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def update_settings(self, is_enabled=None, price_per_sound=None):
        """Update settings with new values"""
        if is_enabled is not None:
            self.is_enabled = is_enabled
        if price_per_sound is not None:
            self.price_per_sound = price_per_sound
        
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def __repr__(self):
        return f'<UserSoundSettings user_id={self.user_id} enabled={self.is_enabled}>'