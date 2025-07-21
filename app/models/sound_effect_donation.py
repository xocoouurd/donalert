from datetime import datetime
from app.extensions import db

class SoundEffectDonation(db.Model):
    __tablename__ = 'sound_effect_donations'
    
    id = db.Column(db.Integer, primary_key=True)
    sound_effect_id = db.Column(db.Integer, db.ForeignKey('sound_effects.id'), nullable=False)
    streamer_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    donor_name = db.Column(db.String(100), nullable=False)
    donor_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    amount = db.Column(db.Numeric(10,2), nullable=False)
    donation_payment_id = db.Column(db.Integer, db.ForeignKey('donation_payments.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_streamer_date', 'streamer_user_id', 'created_at'),
        db.Index('idx_sound_effect', 'sound_effect_id'),
    )
    
    sound_effect = db.relationship('SoundEffect', backref='sound_donations')
    streamer = db.relationship('User', foreign_keys=[streamer_user_id], backref='received_sound_donations')
    donor = db.relationship('User', foreign_keys=[donor_user_id], backref='sent_sound_donations')
    donation_payment = db.relationship('DonationPayment', backref='sound_effect_donation')
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'sound_effect_id': self.sound_effect_id,
            'sound_effect_name': self.sound_effect.name if self.sound_effect else None,
            'streamer_user_id': self.streamer_user_id,
            'donor_name': self.donor_name,
            'donor_user_id': self.donor_user_id,
            'amount': float(self.amount) if self.amount else 0,
            'donation_payment_id': self.donation_payment_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def get_recent_for_streamer(cls, streamer_user_id, limit=10):
        """Get recent sound effect donations for a streamer"""
        return cls.query.filter_by(streamer_user_id=streamer_user_id)\
                       .order_by(cls.created_at.desc())\
                       .limit(limit).all()
    
    @classmethod
    def get_popular_sounds_for_streamer(cls, streamer_user_id, limit=5):
        """Get most popular sound effects for a streamer"""
        from sqlalchemy import func
        return db.session.query(
            cls.sound_effect_id,
            func.count(cls.id).label('usage_count'),
            func.sum(cls.amount).label('total_revenue')
        ).filter_by(streamer_user_id=streamer_user_id)\
         .group_by(cls.sound_effect_id)\
         .order_by(func.count(cls.id).desc())\
         .limit(limit).all()
    
    @classmethod
    def get_monthly_revenue_for_streamer(cls, streamer_user_id, year, month):
        """Get total sound effect revenue for a streamer in a specific month"""
        from sqlalchemy import func, extract
        return db.session.query(func.sum(cls.amount))\
                         .filter(
                             cls.streamer_user_id == streamer_user_id,
                             extract('year', cls.created_at) == year,
                             extract('month', cls.created_at) == month
                         ).scalar() or 0
    
    def __repr__(self):
        return f'<SoundEffectDonation sound_id={self.sound_effect_id} amount={self.amount}>'