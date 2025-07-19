"""
Subscription Payment Model for DonAlert
Tracks subscription payment transactions and their status
"""

from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import Numeric
import uuid
import json

class SubscriptionPayment(db.Model):
    __tablename__ = 'subscription_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=True)
    
    # Payment details
    payment_reference = db.Column(db.String(100), unique=True, nullable=False)
    tier = db.Column(db.String(20), nullable=False)  # 'basic', 'premium', 'enterprise'
    months = db.Column(db.Integer, nullable=False, default=1)
    amount = db.Column(Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='MNT')
    
    # QuickPay details
    quickpay_invoice_id = db.Column(db.String(100), nullable=True, unique=True)
    quickpay_merchant_id = db.Column(db.String(100), nullable=True)
    quickpay_terminal_id = db.Column(db.String(100), nullable=True)
    
    # Payment status
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, paid, failed, cancelled, expired
    payment_method = db.Column(db.String(50), nullable=True)
    
    # Callback and webhook
    webhook_token = db.Column(db.String(100), nullable=True)
    callback_url = db.Column(db.String(500), nullable=True)
    callback_data = db.Column(db.Text, nullable=True)
    
    # Invoice data
    qr_code_text = db.Column(db.Text, nullable=True)
    qr_image_base64 = db.Column(db.Text, nullable=True)
    app_links = db.Column(db.Text, nullable=True)  # JSON string
    payment_url = db.Column(db.String(500), nullable=True)
    
    # Metadata
    request_payload = db.Column(db.Text, nullable=True)
    response_data = db.Column(db.Text, nullable=True)
    customer_name = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='subscription_payments', lazy=True)
    subscription = db.relationship('Subscription', backref='payments', lazy=True)
    
    def __repr__(self):
        return f'<SubscriptionPayment {self.payment_reference} - {self.status}>'
    
    @staticmethod
    def create_payment_record(user_id, tier, months, amount, invoice_data):
        """
        Create a new subscription payment record
        
        Args:
            user_id: ID of the user
            tier: Subscription tier
            months: Number of months
            amount: Payment amount
            invoice_data: Invoice data from QuickPay
            
        Returns:
            SubscriptionPayment: Created payment record
        """
        payment_reference = f"sub_{uuid.uuid4().hex[:12]}"
        
        payment = SubscriptionPayment(
            user_id=user_id,
            payment_reference=payment_reference,
            tier=tier,
            months=months,
            amount=amount,
            currency='MNT',
            quickpay_invoice_id=invoice_data.get('invoice_id'),
            quickpay_merchant_id=invoice_data.get('merchant_id'),
            quickpay_terminal_id=invoice_data.get('terminal_id'),
            webhook_token=invoice_data.get('webhook_token'),
            callback_url=invoice_data.get('callback_url'),
            qr_code_text=invoice_data.get('qr_code'),
            qr_image_base64=invoice_data.get('qr_image'),
            app_links=json.dumps(invoice_data.get('app_links', [])),
            payment_url=invoice_data.get('payment_url'),
            request_payload=json.dumps(invoice_data.get('request_payload', {})),
            response_data=json.dumps(invoice_data.get('response_data', {})),
            customer_name=invoice_data.get('customer_name'),
            description=invoice_data.get('description'),
            status='pending'
        )
        
        # Set expiry (24 hours from creation)
        payment.expires_at = datetime.utcnow() + timedelta(hours=24)
        
        db.session.add(payment)
        db.session.commit()
        
        return payment
    
    def mark_as_paid(self, payment_data=None):
        """
        Mark payment as paid and update related data
        
        Args:
            payment_data: Payment callback data
        """
        self.status = 'paid'
        self.paid_at = datetime.utcnow()
        
        if payment_data:
            self.callback_data = json.dumps(payment_data)
            self.payment_method = payment_data.get('payment_method')
        
        db.session.commit()
    
    def mark_as_failed(self, reason=None):
        """
        Mark payment as failed
        
        Args:
            reason: Failure reason
        """
        self.status = 'failed'
        
        if reason:
            existing_data = {}
            if self.callback_data:
                try:
                    existing_data = json.loads(self.callback_data)
                except:
                    pass
            
            existing_data['failure_reason'] = reason
            self.callback_data = json.dumps(existing_data)
        
        db.session.commit()
    
    def mark_as_cancelled(self):
        """Mark payment as cancelled"""
        self.status = 'cancelled'
        db.session.commit()
    
    def mark_as_expired(self):
        """Mark payment as expired"""
        self.status = 'expired'
        db.session.commit()
    
    def is_expired(self):
        """Check if payment is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def get_app_links(self):
        """Get app links as list"""
        if not self.app_links:
            return []
        try:
            return json.loads(self.app_links)
        except:
            return []
    
    def get_callback_data(self):
        """Get callback data as dict"""
        if not self.callback_data:
            return {}
        try:
            return json.loads(self.callback_data)
        except:
            return {}
    
    def get_request_payload(self):
        """Get request payload as dict"""
        if not self.request_payload:
            return {}
        try:
            return json.loads(self.request_payload)
        except:
            return {}
    
    def get_response_data(self):
        """Get response data as dict"""
        if not self.response_data:
            return {}
        try:
            return json.loads(self.response_data)
        except:
            return {}
    
    @classmethod
    def get_by_invoice_id(cls, invoice_id):
        """Get payment by QuickPay invoice ID"""
        return cls.query.filter_by(quickpay_invoice_id=invoice_id).first()
    
    @classmethod
    def get_by_webhook_token(cls, webhook_token):
        """Get payment by webhook token"""
        return cls.query.filter_by(webhook_token=webhook_token).first()
    
    @classmethod
    def get_user_payments(cls, user_id, limit=10):
        """Get user's payment history"""
        return cls.query.filter_by(user_id=user_id).order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_pending_payments(cls):
        """Get all pending payments"""
        return cls.query.filter_by(status='pending').all()
    
    @classmethod
    def get_expired_payments(cls):
        """Get all expired payments that haven't been marked as expired"""
        return cls.query.filter(
            cls.status == 'pending',
            cls.expires_at < datetime.utcnow()
        ).all()
    
    def to_dict(self):
        """Convert payment to dictionary"""
        return {
            'id': self.id,
            'payment_reference': self.payment_reference,
            'tier': self.tier,
            'months': self.months,
            'amount': float(self.amount),
            'currency': self.currency,
            'status': self.status,
            'payment_method': self.payment_method,
            'customer_name': self.customer_name,
            'description': self.description,
            'quickpay_invoice_id': self.quickpay_invoice_id,
            'qr_code_text': self.qr_code_text,
            'payment_url': self.payment_url,
            'app_links': self.get_app_links(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired()
        }