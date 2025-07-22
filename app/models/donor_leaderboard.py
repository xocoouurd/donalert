from app.extensions import db
from datetime import datetime
from sqlalchemy import func

class DonorLeaderboard(db.Model):
    """
    Donor analytics aggregation table for performance optimization.
    Stores pre-calculated donation totals per donor per streamer.
    """
    __tablename__ = 'donor_leaderboard'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    donor_name = db.Column(db.String(255), nullable=False)
    donor_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    donation_count = db.Column(db.Integer, nullable=False, default=0)
    biggest_single_donation = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    last_donation_date = db.Column(db.DateTime, nullable=False)
    first_donation_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        db.UniqueConstraint('user_id', 'donor_name', name='unique_streamer_donor'),
        db.Index('idx_leaderboard', 'user_id', 'total_amount'),
        db.Index('idx_donor_user', 'donor_user_id'),
    )
    
    # Relationships
    streamer = db.relationship('User', foreign_keys=[user_id], backref='donor_leaderboard')
    donor_user = db.relationship('User', foreign_keys=[donor_user_id])
    
    @classmethod
    def update_donor_entry(cls, streamer_id, donation):
        """Update leaderboard entry with new donation"""
        try:
            # Always group by donor_name only (merge guest + registered donations)
            entry = cls.query.filter_by(
                user_id=streamer_id,
                donor_name=donation.donor_name
            ).first()
            
            if not entry:
                entry = cls(
                    user_id=streamer_id,
                    donor_name=donation.donor_name,
                    donor_user_id=None,  # Always None for merged entries
                    first_donation_date=donation.created_at,
                    last_donation_date=donation.created_at
                )
                db.session.add(entry)
            
            # Update entry with new donation
            entry.add_donation(donation.amount, donation.created_at)
            db.session.commit()
            return entry
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    def add_donation(self, amount, donation_date):
        """Add a donation to this leaderboard entry"""
        from decimal import Decimal
        
        # Convert amount to Decimal if it's not already
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
            
        self.total_amount += amount
        self.donation_count += 1
        
        if amount > self.biggest_single_donation:
            self.biggest_single_donation = amount
            
        if donation_date > self.last_donation_date:
            self.last_donation_date = donation_date
            
        if donation_date < self.first_donation_date:
            self.first_donation_date = donation_date
            
        self.updated_at = datetime.utcnow()
    
    @classmethod
    def get_top_donors(cls, streamer_id, limit=10):
        """Get top N donors for streamer"""
        return cls.query.filter_by(user_id=streamer_id)\
                      .order_by(cls.total_amount.desc())\
                      .limit(limit).all()
    
    @classmethod
    def get_donor_position(cls, streamer_id, donor_name, donor_user_id=None):
        """Get donor's current position in leaderboard (1-based)"""
        # Always search by donor_name only (merged entries)
        entry = cls.query.filter_by(
            user_id=streamer_id,
            donor_name=donor_name
        ).first()
        
        if not entry:
            return None
        
        # Count how many donors have higher total amounts
        higher_count = cls.query.filter(
            cls.user_id == streamer_id,
            cls.total_amount > entry.total_amount
        ).count()
        
        return higher_count + 1
    
    def check_position_change(self, old_amount):
        """Detect if donor position changed with new donation"""
        old_position = self.__class__.get_donor_position_by_amount(
            self.user_id, old_amount
        )
        new_position = self.__class__.get_donor_position_by_amount(
            self.user_id, float(self.total_amount)
        )
        
        return {
            'changed': old_position != new_position,
            'old_position': old_position,
            'new_position': new_position,
            'is_throne_takeover': new_position == 1 and old_position != 1
        }
    
    @classmethod
    def get_donor_position_by_amount(cls, streamer_id, amount):
        """Get position based on donation amount"""
        higher_count = cls.query.filter(
            cls.user_id == streamer_id,
            cls.total_amount > amount
        ).count()
        
        return higher_count + 1
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'donor_name': self.donor_name,
            'donor_user_id': self.donor_user_id,
            'total_amount': float(self.total_amount),
            'donation_count': self.donation_count,
            'biggest_single_donation': float(self.biggest_single_donation),
            'last_donation_date': self.last_donation_date.isoformat() if self.last_donation_date else None,
            'first_donation_date': self.first_donation_date.isoformat() if self.first_donation_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<DonorLeaderboard {self.donor_name}: {self.total_amount}₮ ({self.donation_count} donations)>'