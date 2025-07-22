from datetime import datetime
import json
from flask import url_for
from app.extensions import db

class SoundEffect(db.Model):
    __tablename__ = 'sound_effects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    duration_seconds = db.Column(db.Numeric(4,2), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    tags = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_active', 'is_active'),
        db.Index('idx_category', 'category'),
    )
    
    def get_file_url(self):
        """Get public URL for the sound effect file"""
        return url_for('static', filename=f'assets/sound_effects/{self.filename}')
    
    def get_tags_list(self):
        """Parse tags from JSON string to list"""
        if not self.tags:
            return []
        try:
            return json.loads(self.tags)
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_tags_list(self, tags_list):
        """Set tags from list to JSON string"""
        if isinstance(tags_list, list):
            self.tags = json.dumps(tags_list)
        else:
            self.tags = None
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'filename': self.filename,
            'duration_seconds': float(self.duration_seconds) if self.duration_seconds else 0,
            'file_size': self.file_size,
            'tags': self.get_tags_list(),
            'category': self.category,
            'is_active': self.is_active,
            'file_url': self.get_file_url(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def get_active_sounds(cls, category=None, search_term=None):
        """Get active sound effects with optional filtering"""
        query = cls.query.filter_by(is_active=True)
        
        if category:
            query = query.filter_by(category=category)
        
        if search_term:
            search_filter = f"%{search_term}%"
            query = query.filter(
                db.or_(
                    cls.name.ilike(search_filter),
                    cls.tags.ilike(search_filter)
                )
            )
        
        return query.order_by(cls.name).all()
    
    @classmethod
    def get_categories(cls):
        """Get list of unique categories for active sounds"""
        categories = db.session.query(cls.category).filter(
            cls.is_active == True,
            cls.category.isnot(None)
        ).distinct().all()
        return [cat[0] for cat in categories if cat[0]]
    
    # Relationships will be defined by other models
    
    def __repr__(self):
        return f'<SoundEffect {self.name}>'