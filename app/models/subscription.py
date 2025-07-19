from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import Enum
from app.extensions import db
import enum

class SubscriptionTier(enum.Enum):
    FREE_TRIAL = "free_trial"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"  # 3 months
    BIANNUAL = "biannual"    # 6 months
    ANNUAL = "annual"        # 12 months

class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key to user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Subscription details
    tier = db.Column(Enum(SubscriptionTier), nullable=False)
    status = db.Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)
    
    # Pricing (in MNT - Mongolian Tugrik)
    price_mnt = db.Column(db.Integer, nullable=False, default=0)  # Price in MNT
    
    # Dates
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    
    # Payment tracking
    payment_id = db.Column(db.String(255), nullable=True)  # Payment gateway transaction ID
    payment_method = db.Column(db.String(50), nullable=True)  # e.g., 'qpay', 'bank_transfer'
    payment_status = db.Column(db.String(50), nullable=True)  # e.g., 'completed', 'pending'
    
    # Auto-renewal
    auto_renew = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='subscriptions')
    
    @staticmethod
    def get_pricing():
        """Get subscription pricing in MNT"""
        return {
            SubscriptionTier.FREE_TRIAL: 0,
            SubscriptionTier.MONTHLY: 40000,     # 40,000 MNT per month
            SubscriptionTier.QUARTERLY: 110000,  # 110,000 MNT for 3 months (save ~8%)
            SubscriptionTier.BIANNUAL: 200000,   # 200,000 MNT for 6 months (save ~17%)
            SubscriptionTier.ANNUAL: 380000,     # 380,000 MNT for 12 months (save ~20%)
        }
    
    @staticmethod
    def get_duration_months():
        """Get duration in months for each tier"""
        return {
            SubscriptionTier.FREE_TRIAL: 0,
            SubscriptionTier.MONTHLY: 1,
            SubscriptionTier.QUARTERLY: 3,
            SubscriptionTier.BIANNUAL: 6,
            SubscriptionTier.ANNUAL: 12,
        }
    
    @staticmethod
    def calculate_subscription_cost(tier, months):
        """Calculate subscription cost based on tier and months"""
        if tier == 'basic':
            return 40000 * months  # 40,000 MNT per month
        elif tier == 'premium':
            return 80000 * months  # 80,000 MNT per month
        elif tier == 'enterprise':
            return 120000 * months  # 120,000 MNT per month
        else:
            return None
    
    @staticmethod
    def create_or_extend_subscription(user_id, tier, months, payment_id=None):
        """Create or extend subscription after successful payment"""
        from app.models.user import User
        
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")
        
        # Calculate cost
        cost = Subscription.calculate_subscription_cost(tier, months)
        if not cost:
            raise ValueError(f"Invalid subscription tier: {tier}")
        
        # Get current subscription
        current_subscription = user.get_current_subscription()
        current_time = datetime.utcnow()
        
        # Calculate start and end dates
        if current_subscription and current_subscription.is_active():
            # User has active subscription - extend from current end date
            start_date = current_subscription.end_date
            end_date = start_date + relativedelta(months=months)
        elif current_subscription and not current_subscription.is_expired():
            # User is in grace period - extend from original end date
            start_date = current_subscription.end_date
            end_date = start_date + relativedelta(months=months)
        else:
            # User has no active subscription or expired - start from now
            start_date = current_time
            end_date = current_time + relativedelta(months=months)
        
        # Map tier to SubscriptionTier enum
        def get_subscription_tier(tier, months):
            if months == 1:
                return SubscriptionTier.MONTHLY
            elif months == 3:
                return SubscriptionTier.QUARTERLY
            elif months == 6:
                return SubscriptionTier.BIANNUAL
            elif months == 12:
                return SubscriptionTier.ANNUAL
            else:
                return SubscriptionTier.MONTHLY
        
        subscription_tier = get_subscription_tier(tier, months)
        
        # Create new subscription
        subscription = Subscription(
            user_id=user_id,
            tier=subscription_tier,
            status=SubscriptionStatus.ACTIVE,
            price_mnt=cost,
            start_date=start_date,
            end_date=end_date,
            payment_id=str(payment_id) if payment_id else None,
            payment_method='quickpay',
            payment_status='completed'
        )
        
        # Mark previous subscription as expired if exists
        if current_subscription and current_subscription.id:
            current_subscription.status = SubscriptionStatus.EXPIRED
        
        db.session.add(subscription)
        db.session.commit()
        return subscription
    
    @staticmethod
    def create_free_trial(user_id):
        """Create a free trial subscription for a new user"""
        from app.models.user import User
        
        # Check if user already has a subscription
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")
        
        existing_subscription = user.get_current_subscription()
        if existing_subscription:
            # User already has a subscription, don't create another trial
            return existing_subscription
        
        # Check if user has ever had a free trial before
        previous_trial = Subscription.query.filter_by(
            user_id=user_id,
            tier=SubscriptionTier.FREE_TRIAL
        ).first()
        
        if previous_trial:
            # User has already used their free trial
            raise ValueError(f"User {user_id} has already used their free trial")
        
        trial_end = datetime.utcnow() + timedelta(days=3)  # 3 days free trial
        
        subscription = Subscription(
            user_id=user_id,
            tier=SubscriptionTier.FREE_TRIAL,
            status=SubscriptionStatus.ACTIVE,
            price_mnt=0,
            start_date=datetime.utcnow(),
            end_date=trial_end,
            payment_status='completed'
        )
        
        db.session.add(subscription)
        db.session.commit()
        return subscription
    
    @staticmethod
    def create_paid_subscription(user_id, tier, payment_id=None, payment_method=None):
        """Create a paid subscription with calendar month calculation"""
        from app.models.user import User
        
        pricing = Subscription.get_pricing()
        duration_months = Subscription.get_duration_months()
        
        if tier not in pricing:
            raise ValueError(f"Invalid subscription tier: {tier}")
        
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")
        
        # Calculate start and end dates based on current subscription status
        start_date, end_date = Subscription._calculate_subscription_dates(user, tier)
        
        subscription = Subscription(
            user_id=user_id,
            tier=tier,
            status=SubscriptionStatus.PENDING,  # Will be activated after payment
            price_mnt=pricing[tier],
            start_date=start_date,
            end_date=end_date,
            payment_id=payment_id,
            payment_method=payment_method,
            payment_status='pending'
        )
        
        db.session.add(subscription)
        db.session.commit()
        return subscription
    
    @staticmethod
    def _calculate_subscription_dates(user, tier):
        """Calculate start and end dates for subscription with prepaying logic"""
        duration_months = Subscription.get_duration_months()[tier]
        current_time = datetime.utcnow()
        
        # Get user's current subscription
        current_subscription = user.get_current_subscription()
        
        if current_subscription and current_subscription.is_active():
            # User has active subscription - extend from current end date
            start_date = current_subscription.end_date
            end_date = start_date + relativedelta(months=duration_months)
        elif current_subscription and not current_subscription.is_expired():
            # User is in grace period - extend from original end date
            start_date = current_subscription.end_date
            end_date = start_date + relativedelta(months=duration_months)
        else:
            # User has no active subscription or expired - start from now
            start_date = current_time
            end_date = current_time + relativedelta(months=duration_months)
        
        return start_date, end_date
    
    def is_active(self):
        """Check if subscription is currently active (includes grace period)"""
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        
        # Check if we're still within the grace period
        grace_period_end = self.end_date + timedelta(hours=24)
        return datetime.utcnow() <= grace_period_end
    
    def is_expired(self):
        """Check if subscription has expired (including grace period)"""
        grace_period_end = self.end_date + timedelta(hours=24)
        return datetime.utcnow() > grace_period_end
    
    def is_in_grace_period(self):
        """Check if subscription is in the 24-hour grace period"""
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        
        current_time = datetime.utcnow()
        return self.end_date < current_time <= (self.end_date + timedelta(hours=24))
    
    def days_remaining(self):
        """Get days remaining in subscription (not including grace period)"""
        current_time = datetime.utcnow()
        if self.end_date <= current_time:
            return 0
        return (self.end_date - current_time).days
    
    def hours_remaining_in_grace(self):
        """Get hours remaining in grace period"""
        if not self.is_in_grace_period():
            return 0
        
        current_time = datetime.utcnow()
        grace_period_end = self.end_date + timedelta(hours=24)
        return int((grace_period_end - current_time).total_seconds() / 3600)
    
    def activate(self):
        """Activate the subscription (after successful payment)"""
        self.status = SubscriptionStatus.ACTIVE
        self.payment_status = 'completed'
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def cancel(self):
        """Cancel the subscription"""
        self.status = SubscriptionStatus.CANCELLED
        self.auto_renew = False
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def get_tier_display_name(self):
        """Get display name for subscription tier"""
        display_names = {
            SubscriptionTier.FREE_TRIAL: "Үнэгүй туршилт",
            SubscriptionTier.MONTHLY: "Сарын",
            SubscriptionTier.QUARTERLY: "3 сарын",
            SubscriptionTier.BIANNUAL: "6 сарын",
            SubscriptionTier.ANNUAL: "Жилийн",
        }
        return display_names.get(self.tier, self.tier.value)
    
    def __repr__(self):
        return f'<Subscription {self.user_id}:{self.tier.value}>'