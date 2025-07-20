from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import Enum
from app.extensions import db
import enum

# Feature-based subscription tiers (what features user gets)
class SubscriptionTier(enum.Enum):
    BASIC = "basic"
    ADVANCED = "advanced"

# Duration-based billing cycles (how often user pays)
class BillingCycle(enum.Enum):
    TRIAL = "trial"          # Free trial period
    MONTHLY = "monthly"      # 1 month
    QUARTERLY = "quarterly"  # 3 months
    BIANNUAL = "biannual"    # 6 months  
    ANNUAL = "annual"        # 12 months

# Legacy enum for backward compatibility during migration
class LegacySubscriptionTier(enum.Enum):
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
    
    # New subscription details (separated concepts)
    feature_tier = db.Column(Enum(SubscriptionTier), nullable=True)  # basic, advanced
    billing_cycle = db.Column(Enum(BillingCycle), nullable=True)     # monthly, quarterly, etc.
    
    # Legacy field for backward compatibility during migration
    tier = db.Column(Enum(LegacySubscriptionTier), nullable=True)    # old mixed concept
    
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
    def get_tier_monthly_price():
        """Get monthly price for each feature tier in MNT"""
        return {
            SubscriptionTier.BASIC: 40000,       # 40,000 MNT per month
            SubscriptionTier.ADVANCED: 80000,    # 80,000 MNT per month
        }
    
    @staticmethod
    def get_billing_cycle_months():
        """Get duration in months for each billing cycle"""
        return {
            BillingCycle.TRIAL: 0,
            BillingCycle.MONTHLY: 1,
            BillingCycle.QUARTERLY: 3,
            BillingCycle.BIANNUAL: 6,
            BillingCycle.ANNUAL: 12,
        }
    
    @staticmethod
    def calculate_price(feature_tier, billing_cycle):
        """Calculate total price for feature tier + billing cycle combination"""
        monthly_prices = Subscription.get_tier_monthly_price()
        cycle_months = Subscription.get_billing_cycle_months()
        
        if feature_tier not in monthly_prices or billing_cycle not in cycle_months:
            return None
            
        monthly_price = monthly_prices[feature_tier]
        months = cycle_months[billing_cycle]
        
        if billing_cycle == BillingCycle.TRIAL:
            return 0
        
        # Apply bulk discounts for longer billing cycles
        total_price = monthly_price * months
        if billing_cycle == BillingCycle.QUARTERLY:
            total_price = int(total_price * 0.92)  # 8% discount
        elif billing_cycle == BillingCycle.BIANNUAL:
            total_price = int(total_price * 0.83)  # 17% discount  
        elif billing_cycle == BillingCycle.ANNUAL:
            total_price = int(total_price * 0.80)  # 20% discount
            
        return total_price
    
    # Legacy methods for backward compatibility
    @staticmethod
    def get_pricing():
        """Legacy method - maps old tier enum to pricing"""
        return {
            LegacySubscriptionTier.FREE_TRIAL: 0,
            LegacySubscriptionTier.MONTHLY: 40000,
            LegacySubscriptionTier.QUARTERLY: 110000,
            LegacySubscriptionTier.BIANNUAL: 200000,
            LegacySubscriptionTier.ANNUAL: 380000,
        }
    
    @staticmethod
    def get_duration_months():
        """Legacy method - maps old tier enum to months"""
        return {
            LegacySubscriptionTier.FREE_TRIAL: 0,
            LegacySubscriptionTier.MONTHLY: 1,
            LegacySubscriptionTier.QUARTERLY: 3,
            LegacySubscriptionTier.BIANNUAL: 6,
            LegacySubscriptionTier.ANNUAL: 12,
        }
    
    @staticmethod
    def calculate_subscription_cost(tier, months):
        """Calculate subscription cost based on tier and months"""
        if tier == 'basic':
            return 40000 * months  # 40,000 MNT per month
        elif tier == 'advanced':
            return 80000 * months  # 80,000 MNT per month
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
        
        # Check if user has ever had a free trial before (check both systems)
        previous_trial = Subscription.query.filter(
            (Subscription.user_id == user_id) &
            (
                (Subscription.tier == LegacySubscriptionTier.FREE_TRIAL) |
                (Subscription.billing_cycle == BillingCycle.TRIAL)
            )
        ).first()
        
        if previous_trial:
            # User has already used their free trial
            raise ValueError(f"User {user_id} has already used their free trial")
        
        trial_end = datetime.utcnow() + timedelta(days=3)  # 3 days free trial
        
        subscription = Subscription(
            user_id=user_id,
            # Use new separated system
            feature_tier=SubscriptionTier.BASIC,
            billing_cycle=BillingCycle.TRIAL,
            # Keep legacy field for backward compatibility
            tier=LegacySubscriptionTier.FREE_TRIAL,
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
    def create_paid_subscription(user_id, feature_tier, billing_cycle, payment_id=None, payment_method=None):
        """Create a paid subscription with separated feature tier and billing cycle"""
        from app.models.user import User
        
        # Convert string parameters to enums if needed
        if isinstance(feature_tier, str):
            feature_tier = SubscriptionTier.BASIC if feature_tier == 'basic' else SubscriptionTier.ADVANCED
        if isinstance(billing_cycle, str):
            billing_cycle_map = {
                'monthly': BillingCycle.MONTHLY,
                'quarterly': BillingCycle.QUARTERLY,
                'biannual': BillingCycle.BIANNUAL,
                'annual': BillingCycle.ANNUAL
            }
            billing_cycle = billing_cycle_map.get(billing_cycle, BillingCycle.MONTHLY)
        
        # Calculate subscription cost using new system
        subscription_cost = Subscription.calculate_price(feature_tier, billing_cycle)
        if subscription_cost is None:
            raise ValueError(f"Invalid subscription configuration: {feature_tier}, {billing_cycle}")
        
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")
        
        # Calculate start and end dates
        current_time = datetime.utcnow()
        start_date = current_time
        months = Subscription.get_billing_cycle_months()[billing_cycle]
        end_date = current_time + relativedelta(months=months)
        
        # Map to legacy tier for backward compatibility
        legacy_tier_map = {
            BillingCycle.MONTHLY: LegacySubscriptionTier.MONTHLY,
            BillingCycle.QUARTERLY: LegacySubscriptionTier.QUARTERLY,
            BillingCycle.BIANNUAL: LegacySubscriptionTier.BIANNUAL,
            BillingCycle.ANNUAL: LegacySubscriptionTier.ANNUAL
        }
        legacy_tier = legacy_tier_map.get(billing_cycle, LegacySubscriptionTier.MONTHLY)
        
        subscription = Subscription(
            user_id=user_id,
            # New separated system
            feature_tier=feature_tier,
            billing_cycle=billing_cycle,
            # Legacy field for backward compatibility
            tier=legacy_tier,
            status=SubscriptionStatus.PENDING,  # Will be activated after payment
            price_mnt=subscription_cost,
            start_date=start_date,
            end_date=end_date,
            payment_id=payment_id,
            payment_method=payment_method,
            payment_status='pending'
        )
        
        db.session.add(subscription)
        db.session.commit()
        return subscription
    
    # Legacy method for backward compatibility
    @staticmethod
    def create_paid_subscription_legacy(user_id, tier, payment_id=None, payment_method=None):
        """Legacy method that assumes basic tier and monthly billing"""
        feature_tier = SubscriptionTier.BASIC if tier == 'basic' else SubscriptionTier.ADVANCED
        return Subscription.create_paid_subscription(
            user_id, feature_tier, BillingCycle.MONTHLY, payment_id, payment_method
        )
    
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
    
    def get_feature_tier_display_name(self):
        """Get display name for feature tier"""
        if not self.feature_tier:
            return "Тодорхойгүй"
        
        display_names = {
            SubscriptionTier.BASIC: "Үндсэн",
            SubscriptionTier.ADVANCED: "Дэвшилтэт",
        }
        return display_names.get(self.feature_tier, self.feature_tier.value)
    
    def get_billing_cycle_display_name(self):
        """Get display name for billing cycle"""
        if not self.billing_cycle:
            return "Тодорхойгүй"
            
        display_names = {
            BillingCycle.TRIAL: "Үнэгүй туршилт",
            BillingCycle.MONTHLY: "Сарын",
            BillingCycle.QUARTERLY: "3 сарын", 
            BillingCycle.BIANNUAL: "6 сарын",
            BillingCycle.ANNUAL: "Жилийн",
        }
        return display_names.get(self.billing_cycle, self.billing_cycle.value)
    
    def get_full_display_name(self):
        """Get combined display name (e.g. 'Дэвшилтэт - Жилийн')"""
        if self.feature_tier and self.billing_cycle:
            feature_name = self.get_feature_tier_display_name()
            cycle_name = self.get_billing_cycle_display_name()
            return f"{feature_name} - {cycle_name}"
        else:
            # Fallback to legacy display for backward compatibility
            return self.get_tier_display_name()
    
    # Legacy method for backward compatibility
    def get_tier_display_name(self):
        """Legacy display name method"""
        if self.tier:
            display_names = {
                LegacySubscriptionTier.FREE_TRIAL: "Үнэгүй туршилт",
                LegacySubscriptionTier.MONTHLY: "Сарын",
                LegacySubscriptionTier.QUARTERLY: "3 сарын",
                LegacySubscriptionTier.BIANNUAL: "6 сарын",
                LegacySubscriptionTier.ANNUAL: "Жилийн",
            }
            return display_names.get(self.tier, self.tier.value)
        else:
            return self.get_full_display_name()
    
    def __repr__(self):
        return f'<Subscription {self.user_id}:{self.tier.value}>'