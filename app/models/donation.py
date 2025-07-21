from app.extensions import db
from datetime import datetime
from sqlalchemy import desc, asc

class Donation(db.Model):
    __tablename__ = 'donations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    donor_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    message = db.Column(db.Text, nullable=True)
    platform = db.Column(db.String(50), nullable=False, default='guest')
    donor_platform_id = db.Column(db.String(100), nullable=True)
    donation_id = db.Column(db.String(50), nullable=False, unique=True)
    donation_payment_id = db.Column(db.Integer, db.ForeignKey('donation_payments.id'), nullable=True)
    is_test = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship to user
    user = db.relationship('User', backref=db.backref('donations', lazy=True))
    
    def __repr__(self):
        return f'<Donation {self.id}: {self.donor_name} - {self.amount}₮>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'donor_name': self.donor_name,
            'amount': self.amount,
            'message': self.message,
            'platform': self.platform,
            'donation_id': self.donation_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }
    
    @classmethod
    def create_donation(cls, user_id, donor_name, amount, message, platform='guest', donor_platform_id=None, donation_id=None, is_test=False):
        """Create a new donation record"""
        import uuid
        
        if not donation_id:
            donation_id = f"don_{uuid.uuid4().hex[:12]}"
        
        donation = cls(
            user_id=user_id,
            donor_name=donor_name,
            amount=amount,
            message=message,
            platform=platform,
            donor_platform_id=donor_platform_id,
            donation_id=donation_id,
            is_test=is_test,
            processed_at=datetime.utcnow()
        )
        
        db.session.add(donation)
        db.session.commit()
        return donation
    
    @classmethod
    def get_user_donations(cls, user_id, page=1, per_page=20, search=None, sort_by='created_at', sort_order='desc'):
        """Get donations for a user with pagination, search, and sorting"""
        query = cls.query.filter_by(user_id=user_id)
        
        # Apply search filter
        if search:
            query = query.filter(
                db.or_(
                    cls.donor_name.ilike(f'%{search}%'),
                    cls.message.ilike(f'%{search}%'),
                    cls.platform.ilike(f'%{search}%')
                )
            )
        
        # Apply sorting
        if sort_by == 'created_at':
            order_column = cls.created_at
        elif sort_by == 'donor_name':
            order_column = cls.donor_name
        elif sort_by == 'amount':
            order_column = cls.amount
        else:
            order_column = cls.created_at
        
        if sort_order == 'desc':
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(asc(order_column))
        
        # Apply pagination
        return query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
    
    @classmethod
    def get_user_donation_stats(cls, user_id):
        """Get donation statistics for a user"""
        from sqlalchemy import func
        
        stats = db.session.query(
            func.count(cls.id).label('total_donations'),
            func.sum(cls.amount).label('total_amount'),
            func.avg(cls.amount).label('average_amount')
        ).filter_by(user_id=user_id).first()
        
        return {
            'total_donations': stats.total_donations or 0,
            'total_amount': float(stats.total_amount or 0),
            'average_amount': float(stats.average_amount or 0)
        }
    
    @classmethod
    def get_recent_donations(cls, user_id, limit=10):
        """Get recent donations for a user"""
        return cls.query.filter_by(user_id=user_id)\
                      .order_by(desc(cls.created_at))\
                      .limit(limit)\
                      .all()
    
    @classmethod
    def get_top_donors(cls, user_id, limit=10):
        """Get top donors for a user"""
        from sqlalchemy import func
        
        return db.session.query(
            cls.donor_name,
            func.sum(cls.amount).label('total_amount'),
            func.count(cls.id).label('donation_count')
        ).filter_by(user_id=user_id)\
         .group_by(cls.donor_name)\
         .order_by(desc(func.sum(cls.amount)))\
         .limit(limit)\
         .all()