from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func

class TTSUsage(db.Model):
    __tablename__ = 'tts_usage'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    request_type = db.Column(db.String(20), nullable=False)  # 'donation', 'test', 'manual'
    character_count = db.Column(db.Integer, nullable=False)
    voice_id = db.Column(db.String(50), nullable=False)
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='tts_usage')
    
    @classmethod
    def get_user_usage_today(cls, user_id):
        """Get user's TTS usage for today"""
        today = datetime.utcnow().date()
        return cls.query.filter(
            cls.user_id == user_id,
            func.date(cls.created_at) == today,
            cls.success == True
        ).count()
    
    @classmethod
    def get_user_usage_this_month(cls, user_id):
        """Get user's TTS usage for this month"""
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return cls.query.filter(
            cls.user_id == user_id,
            cls.created_at >= start_of_month,
            cls.success == True
        ).count()
    
    @classmethod
    def get_user_character_count_today(cls, user_id):
        """Get user's character count for today"""
        today = datetime.utcnow().date()
        result = db.session.query(func.sum(cls.character_count)).filter(
            cls.user_id == user_id,
            func.date(cls.created_at) == today,
            cls.success == True
        ).scalar()
        return result or 0
    
    @classmethod
    def get_user_character_count_this_month(cls, user_id):
        """Get user's character count for this month"""
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = db.session.query(func.sum(cls.character_count)).filter(
            cls.user_id == user_id,
            cls.created_at >= start_of_month,
            cls.success == True
        ).scalar()
        return result or 0
    
    @classmethod
    def get_recent_requests(cls, user_id, minutes=5):
        """Get recent requests in the last N minutes"""
        time_limit = datetime.utcnow() - timedelta(minutes=minutes)
        return cls.query.filter(
            cls.user_id == user_id,
            cls.created_at >= time_limit
        ).count()
    
    @classmethod
    def log_usage(cls, user_id, request_type, character_count, voice_id, success=True, error_message=None, ip_address=None):
        """Log TTS usage"""
        usage = cls(
            user_id=user_id,
            request_type=request_type,
            character_count=character_count,
            voice_id=voice_id,
            success=success,
            error_message=error_message,
            ip_address=ip_address
        )
        db.session.add(usage)
        db.session.commit()
        return usage