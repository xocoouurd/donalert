from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from app.extensions import db
import secrets
import logging

logger = logging.getLogger(__name__)

class Marathon(db.Model):
    __tablename__ = 'marathons'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Marathon settings
    minute_price = db.Column(db.Numeric(precision=10, scale=2), nullable=False, default=1000)  # MNT per minute
    
    # Time settings (stored in total minutes for easier calculation)
    initial_time_minutes = db.Column(db.Integer, nullable=False, default=0)  # Initial time set by streamer
    remaining_time_minutes = db.Column(db.Integer, nullable=False, default=0)  # Current remaining time
    remaining_time_seconds = db.Column(db.Integer, nullable=False, default=0)  # Current remaining seconds (0-59)
    donated_time_minutes = db.Column(db.Integer, nullable=False, default=0)  # Time added through donations
    manual_adjustments_minutes = db.Column(db.Integer, nullable=False, default=0)  # Manual time additions/removals
    
    # Donation tracking during marathon
    accumulated_donations = db.Column(db.Numeric(precision=12, scale=2), nullable=False, default=0)  # Total donations during this marathon
    
    # Countdown timer font settings
    timer_font_size = db.Column(db.Integer, nullable=False, default=48)
    timer_font_weight = db.Column(db.Integer, nullable=False, default=700)
    timer_font_color = db.Column(db.String(7), nullable=False, default='#ffffff')
    
    # Notification font settings (for "XX minutes added" messages)
    notification_font_size = db.Column(db.Integer, nullable=False, default=24)
    notification_font_weight = db.Column(db.Integer, nullable=False, default=600)
    notification_font_color = db.Column(db.String(7), nullable=False, default='#10b981')
    
    # Animation settings
    timer_animation = db.Column(db.String(50), nullable=False, default='none')
    
    # Marathon state
    started_at = db.Column(db.DateTime, nullable=True)  # When marathon countdown started
    paused_at = db.Column(db.DateTime, nullable=True)  # When marathon was paused
    is_paused = db.Column(db.Boolean, nullable=False, default=False)
    total_paused_duration = db.Column(db.Integer, nullable=False, default=0)  # Total minutes paused
    
    # Security
    overlay_token = db.Column(db.String(64), nullable=True, unique=True)  # Random token for overlay URL
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='marathons')
    
    def __repr__(self):
        return f'<Marathon {self.id}: {self.user.username} - {self.remaining_time_minutes} min remaining>'
    
    @classmethod
    def get_or_create_for_user(cls, user_id):
        """Get or create marathon settings for a user"""
        marathon = cls.query.filter_by(user_id=user_id).first()
        if not marathon:
            marathon = cls(user_id=user_id)
            marathon.generate_overlay_token()
            db.session.add(marathon)
            db.session.commit()
        elif not marathon.overlay_token:
            # Generate token for existing marathons without one
            marathon.generate_overlay_token()
            db.session.commit()
        return marathon
    
    def generate_overlay_token(self):
        """Generate a secure random token for overlay URL"""
        self.overlay_token = secrets.token_urlsafe(32)
    
    
    @classmethod
    def get_by_overlay_token(cls, token):
        """Get marathon by overlay token"""
        return cls.query.filter_by(overlay_token=token).first()
    
    def get_total_time_minutes(self):
        """Get total time including manual adjustments and donations"""
        return self.initial_time_minutes + self.donated_time_minutes + self.manual_adjustments_minutes
    
    def get_time_breakdown(self):
        """Get time broken down into days, hours, minutes, seconds"""
        total_minutes = max(0, self.remaining_time_minutes)
        seconds = max(0, self.remaining_time_seconds)
        
        days = total_minutes // (24 * 60)
        remaining_after_days = total_minutes % (24 * 60)
        hours = remaining_after_days // 60
        minutes = remaining_after_days % 60
        
        return {
            'days': days,
            'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
            'total_minutes': total_minutes
        }
    
    def set_initial_time(self, days, hours, minutes, auto_commit=True):
        """Set initial time from days, hours, minutes"""
        total_minutes = (days * 24 * 60) + (hours * 60) + minutes
        self.initial_time_minutes = total_minutes
        self.remaining_time_minutes = total_minutes
        self.remaining_time_seconds = 0  # Reset seconds when setting new time
        self.updated_at = datetime.utcnow()
        
        if auto_commit:
            db.session.commit()
            # Send real-time update
            self._send_marathon_update()
    
    def add_time_minutes(self, minutes, source='manual'):
        """Add time to the marathon (positive or negative for removal)"""
        if source == 'donation':
            self.donated_time_minutes += minutes
        else:  # manual
            self.manual_adjustments_minutes += minutes
        
        # Update remaining time
        self.remaining_time_minutes += minutes
        
        # Ensure remaining time doesn't go below 0
        if self.remaining_time_minutes < 0:
            self.remaining_time_minutes = 0
        
        self.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Send real-time update (skip time recalculation for donations to preserve added time)
        self._send_marathon_update(skip_time_calc=(source == 'donation'))
        
        # Send notification about time change
        self._send_time_notification(minutes, source)
        
        return self.remaining_time_minutes
    
    def add_donation_amount(self, amount):
        """Add donation amount to accumulated donations (only if marathon is running)"""
        if self.started_at and not self.is_paused:
            from decimal import Decimal
            
            # Convert amount to Decimal to match the database field type
            amount_decimal = Decimal(str(amount))
            self.accumulated_donations += amount_decimal
            self.updated_at = datetime.utcnow()
            db.session.commit()
            
            from flask import current_app
            current_app.logger.info(f"Added {amount}₮ to marathon donations - total now: {self.accumulated_donations}₮")
            
            # Send real-time update
            self._send_marathon_update()
            
            return True
        return False
    
    def update_countdown_state(self, minutes, seconds):
        """Update the countdown state (minutes and seconds) - called by client-side countdown"""
        self.remaining_time_minutes = max(0, minutes)
        self.remaining_time_seconds = max(0, min(59, seconds))  # Ensure seconds are 0-59
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def start_countdown(self):
        """Start the marathon countdown"""
        now = datetime.utcnow()
        
        if not self.is_paused:
            # Starting fresh - initialize remaining time with total available time
            self.started_at = now
            total_time = self.get_total_time_minutes()
            self.remaining_time_minutes = total_time
            self.remaining_time_seconds = 0
            
            from flask import current_app
            current_app.logger.info(f"MARATHON START: Marathon {self.id}, initial_time: {self.initial_time_minutes}, total_time: {total_time}, set remaining_time to: {self.remaining_time_minutes}")
        else:
            # Resume from pause - update paused duration
            if self.paused_at:
                pause_duration_minutes = (now - self.paused_at).total_seconds() / 60
                self.total_paused_duration += int(pause_duration_minutes)
            
            self.is_paused = False
            self.paused_at = None
        
        self.updated_at = now
        db.session.commit()
        
        # Send real-time update
        self._send_marathon_update(skip_time_calc=True)
    
    def pause_countdown(self):
        """Pause the marathon countdown"""
        if not self.is_paused and self.started_at:
            from flask import current_app
            current_app.logger.info(f"PAUSE COUNTDOWN: Before pause - minutes: {self.remaining_time_minutes}, seconds: {self.remaining_time_seconds}")
            
            self.is_paused = True
            self.paused_at = datetime.utcnow()
            
            # Don't recalculate time here - rely on client-side countdown state
            # The remaining_time_minutes and remaining_time_seconds should already be
            # up-to-date from the client-side countdown via update_countdown_state()
            
            self.updated_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"PAUSE COUNTDOWN: After pause and commit - minutes: {self.remaining_time_minutes}, seconds: {self.remaining_time_seconds}")
            
            # Send real-time update but skip time calculation to preserve paused state
            self._send_marathon_update(skip_time_calc=True)
    
    def get_current_remaining_time(self):
        """Get current remaining time accounting for elapsed time if running"""
        if not self.started_at or self.is_paused:
            return self.remaining_time_minutes
        
        # Check if time was recently updated by donation (within last 10 seconds)
        # If so, don't recalculate to preserve donation time additions
        from datetime import timedelta
        recent_update_threshold = datetime.utcnow() - timedelta(seconds=10)
        if self.updated_at > recent_update_threshold:
            from flask import current_app
            current_app.logger.info(f"MARATHON TIME: Skipping recalculation - recent update at {self.updated_at}")
            return self.remaining_time_minutes
        
        # Calculate elapsed time since last database update
        elapsed_seconds = self._calculate_elapsed_seconds_since_update()
        
        # Start with stored remaining time (which was last updated by client-side countdown)
        total_remaining_seconds = (self.remaining_time_minutes * 60) + self.remaining_time_seconds
        current_remaining_seconds = max(0, total_remaining_seconds - elapsed_seconds)
        
        # Convert back to minutes and seconds
        current_remaining_minutes = current_remaining_seconds // 60
        current_seconds = current_remaining_seconds % 60
        
        # Update stored remaining time
        if current_remaining_minutes != self.remaining_time_minutes or current_seconds != self.remaining_time_seconds:
            self.remaining_time_minutes = current_remaining_minutes
            self.remaining_time_seconds = current_seconds
            db.session.commit()
        
        return current_remaining_minutes
    
    def _calculate_elapsed_minutes(self):
        """Calculate total elapsed minutes since marathon started"""
        if not self.started_at:
            return 0
        
        now = datetime.utcnow()
        
        if self.is_paused and self.paused_at:
            # Use paused time as end point
            total_elapsed = (self.paused_at - self.started_at).total_seconds() / 60
        else:
            # Use current time as end point
            total_elapsed = (now - self.started_at).total_seconds() / 60
        
        # Subtract any paused duration
        total_elapsed -= self.total_paused_duration
        
        return max(0, int(total_elapsed))
    
    def _calculate_elapsed_seconds(self):
        """Calculate total elapsed seconds since marathon started"""
        if not self.started_at:
            return 0
        
        now = datetime.utcnow()
        
        if self.is_paused and self.paused_at:
            # Use paused time as end point
            total_elapsed = (self.paused_at - self.started_at).total_seconds()
        else:
            # Use current time as end point
            total_elapsed = (now - self.started_at).total_seconds()
        
        # Subtract any paused duration (convert to seconds)
        total_elapsed -= (self.total_paused_duration * 60)
        
        return max(0, int(total_elapsed))
    
    def _calculate_elapsed_seconds_since_update(self):
        """Calculate elapsed seconds since the last database update"""
        if not self.started_at or self.is_paused:
            return 0
        
        now = datetime.utcnow()
        
        # Calculate elapsed time since last update
        elapsed_since_update = (now - self.updated_at).total_seconds()
        
        return max(0, int(elapsed_since_update))
    
    def reset_marathon(self):
        """Reset marathon to initial state - sets everything including initial time to 0"""
        from flask import current_app
        current_app.logger.info(f"MARATHON RESET: Before reset - initial: {self.initial_time_minutes}, remaining: {self.remaining_time_minutes}, donations: {self.accumulated_donations}")
        
        # Reset everything to 0, including initial time and accumulated donations
        self.initial_time_minutes = 0
        self.remaining_time_minutes = 0
        self.remaining_time_seconds = 0
        self.donated_time_minutes = 0
        self.manual_adjustments_minutes = 0
        self.accumulated_donations = 0
        self.started_at = None
        self.paused_at = None
        self.is_paused = False
        self.total_paused_duration = 0
        self.updated_at = datetime.utcnow()
        
        current_app.logger.info(f"MARATHON RESET: After reset - initial: {self.initial_time_minutes}, remaining: {self.remaining_time_minutes}, donations: {self.accumulated_donations}")
        db.session.commit()
        current_app.logger.info(f"MARATHON RESET: After commit - remaining: {self.remaining_time_minutes}")
        
        # Send real-time update
        self._send_marathon_update()
    
    def auto_reset_marathon(self):
        """Auto-reset marathon when timer reaches 0 - sets initial time to 0 and stops marathon"""
        logger.info(f"MARATHON AUTO-RESET: Starting auto-reset for marathon {self.id}")
        logger.info(f"MARATHON AUTO-RESET: Before auto-reset - initial: {self.initial_time_minutes}, remaining: {self.remaining_time_minutes}:{self.remaining_time_seconds}, donations: {self.accumulated_donations}")
        logger.info(f"MARATHON AUTO-RESET: Before auto-reset - started_at: {self.started_at}, is_paused: {self.is_paused}")
        
        # Set initial time to 0 and reset everything else including accumulated donations
        self.initial_time_minutes = 0
        self.remaining_time_minutes = 0
        self.remaining_time_seconds = 0
        self.donated_time_minutes = 0
        self.manual_adjustments_minutes = 0
        self.accumulated_donations = 0
        self.started_at = None  # This makes the marathon inactive
        self.paused_at = None
        self.is_paused = False
        self.total_paused_duration = 0
        self.updated_at = datetime.utcnow()
        
        logger.info(f"MARATHON AUTO-RESET: After auto-reset - initial: {self.initial_time_minutes}, remaining: {self.remaining_time_minutes}:{self.remaining_time_seconds}, donations: {self.accumulated_donations}")
        logger.info(f"MARATHON AUTO-RESET: After auto-reset - started_at: {self.started_at}, is_paused: {self.is_paused}")
        logger.info(f"MARATHON AUTO-RESET: Marathon is now inactive (started_at is None)")
        
        db.session.commit()
        logger.info(f"MARATHON AUTO-RESET: Changes committed to database")
        
        # Send real-time update to notify all connected clients
        logger.info(f"MARATHON AUTO-RESET: Sending WebSocket update to notify marathon is now inactive")
        self._send_marathon_update()
    
    def _send_marathon_update(self, skip_time_calc=False):
        """Send real-time marathon update via WebSocket"""
        try:
            from app.extensions import socketio
            from flask import current_app
            
            # Get current time breakdown - update current time if marathon is running
            if not skip_time_calc and self.started_at and not self.is_paused:
                self.get_current_remaining_time()  # This updates the database with current time
            
            time_breakdown = self.get_time_breakdown()
            
            current_app.logger.info(f"MARATHON WEBSOCKET: Sending update for Marathon {self.id}, User {self.user_id}, Time: {time_breakdown}")
            
            # Prepare marathon data - include all fields for settings page updates
            marathon_data = {
                'id': self.id,
                'user_id': self.user_id,
                'minute_price': float(self.minute_price),
                'remaining_time': time_breakdown,
                'time_breakdown': time_breakdown,  # For consistency with to_dict()
                'total_time_minutes': self.get_total_time_minutes(),
                'donated_time_minutes': self.donated_time_minutes,  # Include for settings page
                'accumulated_donations': float(self.accumulated_donations),  # Include for settings page
                'is_running': self.started_at is not None and not self.is_paused,
                'is_paused': self.is_paused,
                'timer_font_size': self.timer_font_size,
                'timer_font_weight': self.timer_font_weight,
                'timer_font_color': self.timer_font_color,
                'timer_animation': self.timer_animation,
                'updated_at': self.updated_at.isoformat()
            }
            
            # Send to marathon overlay room
            marathon_room = f"marathon_overlay_{self.user_id}"
            current_app.logger.info(f"MARATHON WEBSOCKET: Emitting to room {marathon_room}")
            socketio.emit('marathon_updated', marathon_data, room=marathon_room)
            
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Failed to send marathon update: {str(e)}")
    
    def _send_time_notification(self, minutes_added, source):
        """Send notification about time being added/removed"""
        try:
            from app.extensions import socketio
            
            logger.info(f"MARATHON NOTIFICATION: Starting notification for {minutes_added} minutes from {source}")
            logger.info(f"MARATHON NOTIFICATION: Marathon ID: {self.id}, User ID: {self.user_id}")
            
            # Determine notification text
            if minutes_added > 0:
                if source == 'donation':
                    notification_text = f"+{minutes_added} минут хандиваар нэмэгдлээ!"
                else:
                    notification_text = f"+{minutes_added} минут нэмэгдлээ!"
            else:
                notification_text = f"{minutes_added} минут хасагдлаа!"
            
            logger.info(f"MARATHON NOTIFICATION: Notification text: {notification_text}")
            
            # Prepare notification data
            notification_data = {
                'text': notification_text,
                'minutes': minutes_added,
                'source': source,
                'font_size': self.notification_font_size,
                'font_weight': self.notification_font_weight,
                'font_color': self.notification_font_color,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"MARATHON NOTIFICATION: Notification data prepared: {notification_data}")
            
            # Send to marathon overlay room
            marathon_room = f"marathon_overlay_{self.user_id}"
            logger.info(f"MARATHON NOTIFICATION: Emitting to room {marathon_room}")
            
            # Check if SocketIO is available
            if socketio is None:
                logger.error("MARATHON NOTIFICATION: SocketIO instance is None!")
                return
            
            logger.info(f"MARATHON NOTIFICATION: SocketIO instance is available")
            socketio.emit('marathon_notification', notification_data, room=marathon_room)
            logger.info(f"MARATHON NOTIFICATION: Successfully emitted to room {marathon_room}")
            
        except Exception as e:
            logger.error(f"MARATHON NOTIFICATION: Failed to send notification: {str(e)}")
            import traceback
            logger.error(f"MARATHON NOTIFICATION: Traceback: {traceback.format_exc()}")
    
    def calculate_minutes_from_donation(self, donation_amount):
        """Calculate how many minutes to add based on donation amount"""
        if self.minute_price <= 0:
            return 0
        return int(float(donation_amount) / float(self.minute_price))
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        time_breakdown = self.get_time_breakdown()
        
        return {
            'id': self.id,
            'user_id': self.user_id,
            'minute_price': float(self.minute_price),
            'initial_time_minutes': self.initial_time_minutes,
            'remaining_time_minutes': self.remaining_time_minutes,
            'donated_time_minutes': self.donated_time_minutes,
            'manual_adjustments_minutes': self.manual_adjustments_minutes,
            'accumulated_donations': float(self.accumulated_donations),
            'total_time_minutes': self.get_total_time_minutes(),
            'time_breakdown': time_breakdown,
            'remaining_time': time_breakdown,  # Use time_breakdown for remaining_time to ensure consistency
            'timer_font_size': self.timer_font_size,
            'timer_font_weight': self.timer_font_weight,
            'timer_font_color': self.timer_font_color,
            'timer_animation': self.timer_animation,
            'notification_font_size': self.notification_font_size,
            'notification_font_weight': self.notification_font_weight,
            'notification_font_color': self.notification_font_color,
            'is_running': self.started_at is not None and not self.is_paused,
            'is_paused': self.is_paused,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }