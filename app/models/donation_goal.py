from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from app.extensions import db

class DonationGoal(db.Model):
    __tablename__ = 'donation_goals'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Goal settings
    title = db.Column(db.String(200), nullable=False, default='Зорилго')
    goal_amount = db.Column(db.Numeric(precision=12, scale=2), nullable=False, default=0)
    current_amount = db.Column(db.Numeric(precision=12, scale=2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    # Manual adjustments
    manual_adjustments = db.Column(db.Numeric(precision=12, scale=2), nullable=False, default=0)
    
    # Title styling
    title_font_size = db.Column(db.Integer, nullable=False, default=24)
    title_font_weight = db.Column(db.Integer, nullable=False, default=600)
    title_color = db.Column(db.String(7), nullable=False, default='#333333')
    
    # Progress bar styling
    progress_height = db.Column(db.Integer, nullable=False, default=30)
    progress_text_size = db.Column(db.Integer, nullable=False, default=14)
    progress_font_weight = db.Column(db.Integer, nullable=False, default=500)
    progress_font_color = db.Column(db.String(7), nullable=False, default='#333333')
    progress_color = db.Column(db.String(7), nullable=False, default='#6366f1')
    progress_background_color = db.Column(db.String(7), nullable=False, default='#ffffff')
    progress_animation = db.Column(db.String(20), nullable=False, default='none')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='donation_goals')
    
    def __repr__(self):
        return f'<DonationGoal {self.id}: {self.title} - {self.current_amount}/{self.goal_amount}>'
    
    @classmethod
    def get_or_create_for_user(cls, user_id):
        """Get or create donation goal settings for a user"""
        goal = cls.query.filter_by(user_id=user_id, is_active=True).first()
        if not goal:
            goal = cls(user_id=user_id)
            db.session.add(goal)
            db.session.commit()
        return goal
    
    def get_progress_percentage(self):
        """Calculate progress percentage"""
        if self.goal_amount <= 0:
            return 0
        total_amount = float(self.current_amount) + float(self.manual_adjustments)
        return min((total_amount / float(self.goal_amount)) * 100, 100)
    
    def get_total_amount(self):
        """Get total amount including manual adjustments"""
        return float(self.current_amount) + float(self.manual_adjustments)
    
    def add_donation(self, amount):
        """Add donation amount to current total"""
        from decimal import Decimal
        self.current_amount += Decimal(str(amount))
        self.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Send real-time update
        self._send_goal_update()
    
    def add_manual_adjustment(self, amount):
        """Add manual adjustment to goal"""
        from decimal import Decimal
        self.manual_adjustments += Decimal(str(amount))
        self.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Send real-time update
        self._send_goal_update()
    
    def reset_goal(self):
        """Reset goal progress"""
        self.current_amount = 0
        self.manual_adjustments = 0
        self.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Send real-time update
        self._send_goal_update()
    
    def override_total_amount(self, new_total):
        """Override the total accumulated amount"""
        from decimal import Decimal
        
        # Reset current amount and set manual adjustments to achieve the new total
        self.current_amount = 0
        self.manual_adjustments = Decimal(str(new_total))
        self.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Send real-time update
        self._send_goal_update()
    
    def _send_goal_update(self):
        """Send real-time goal update via WebSocket"""
        try:
            from app.extensions import socketio
            
            # Prepare goal data with styling
            goal_data = {
                'id': self.id,
                'title': self.title,
                'goal_amount': float(self.goal_amount),
                'current_amount': float(self.current_amount),
                'manual_adjustments': float(self.manual_adjustments),
                'total_amount': self.get_total_amount(),
                'progress_percentage': self.get_progress_percentage(),
                'is_active': self.is_active,
                'title_font_size': self.title_font_size,
                'title_font_weight': self.title_font_weight,
                'title_color': self.title_color,
                'progress_height': self.progress_height,
                'progress_text_size': self.progress_text_size,
                'progress_font_weight': self.progress_font_weight,
                'progress_font_color': self.progress_font_color,
                'progress_color': self.progress_color,
                'progress_background_color': self.progress_background_color,
                'progress_animation': self.progress_animation,
                'updated_at': self.updated_at.isoformat()
            }
            
            # Send to goal overlay room
            goal_room = f"goal_overlay_{self.user_id}"
            socketio.emit('goal_updated', goal_data, room=goal_room)
            
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Failed to send goal update: {str(e)}")
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'goal_amount': float(self.goal_amount),
            'current_amount': float(self.current_amount),
            'manual_adjustments': float(self.manual_adjustments),
            'total_amount': self.get_total_amount(),
            'progress_percentage': self.get_progress_percentage(),
            'is_active': self.is_active,
            'title_font_size': self.title_font_size,
            'title_font_weight': self.title_font_weight,
            'title_color': self.title_color,
            'progress_height': self.progress_height,
            'progress_text_size': self.progress_text_size,
            'progress_font_weight': self.progress_font_weight,
            'progress_font_color': self.progress_font_color,
            'progress_color': self.progress_color,
            'progress_background_color': self.progress_background_color,
            'progress_animation': self.progress_animation,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }