from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from app.extensions import db
from app.utils.quickpay_payment import create_donation_invoice
import logging

logger = logging.getLogger(__name__)

class DonationPayment(db.Model):
    __tablename__ = 'donation_payments'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys
    streamer_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Donation details
    donor_name = db.Column(db.String(100), nullable=False)
    donor_platform = db.Column(db.String(50), nullable=True)  # 'guest', 'twitch', 'youtube', 'kick'
    donor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # If donor is authenticated
    amount = db.Column(db.Numeric(precision=10, scale=2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='MNT')
    message = db.Column(db.Text, nullable=True)
    
    # QuickPay details
    quickpay_invoice_id = db.Column(db.String(100), nullable=True, unique=True)
    quickpay_merchant_id = db.Column(db.String(100), nullable=True)
    quickpay_terminal_id = db.Column(db.String(100), nullable=True)
    
    # Payment status
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, paid, failed, expired
    payment_method = db.Column(db.String(50), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    
    # Webhook details
    webhook_token = db.Column(db.String(64), nullable=True)
    callback_url = db.Column(db.String(255), nullable=True)
    
    # QPay response data
    qr_code = db.Column(db.Text, nullable=True)
    qr_image = db.Column(db.Text, nullable=True)
    payment_url = db.Column(db.Text, nullable=True)
    app_links = db.Column(db.Text, nullable=True)  # JSON string of app links
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    streamer = db.relationship('User', foreign_keys=[streamer_user_id], backref='received_donation_payments')
    donor_user = db.relationship('User', foreign_keys=[donor_user_id], backref='sent_donation_payments')
    
    def __repr__(self):
        return f'<DonationPayment {self.id}: {self.donor_name} -> {self.streamer.username} ({self.amount} {self.currency})>'
    
    @classmethod
    def create_donation_payment(cls, streamer_user_id, donor_name, amount, message="", donor_platform="guest", donor_user_id=None):
        """
        Create a new donation payment and QPay invoice
        
        Args:
            streamer_user_id: ID of the streamer receiving the donation
            donor_name: Name of the donor
            amount: Donation amount in MNT
            message: Optional donation message
            donor_platform: Platform of the donor ('guest', 'twitch', 'youtube', 'kick')
            donor_user_id: ID of the donor if authenticated
            
        Returns:
            dict: Payment creation response
        """
        try:
            # Create QPay invoice
            invoice_result = create_donation_invoice(streamer_user_id, donor_name, amount, message)
            
            if not invoice_result.get('success'):
                return invoice_result
            
            # Create donation payment record
            donation_payment = cls(
                streamer_user_id=streamer_user_id,
                donor_name=donor_name,
                donor_platform=donor_platform,
                donor_user_id=donor_user_id,
                amount=amount,
                currency='MNT',
                message=message,
                quickpay_invoice_id=invoice_result.get('invoice_id'),
                quickpay_merchant_id=invoice_result.get('raw_response', {}).get('merchant_id'),
                quickpay_terminal_id=invoice_result.get('raw_response', {}).get('terminal_id'),
                webhook_token=invoice_result.get('webhook_token'),
                callback_url=invoice_result.get('callback_url'),
                qr_code=invoice_result.get('qr_code'),
                qr_image=invoice_result.get('qr_image'),
                payment_url=invoice_result.get('payment_url'),
                app_links=str(invoice_result.get('app_links', [])),
                status='pending',
                expires_at=datetime.utcnow().replace(hour=23, minute=59, second=59)  # Expires at end of day
            )
            
            db.session.add(donation_payment)
            db.session.commit()
            
            return {
                'success': True,
                'donation_payment_id': donation_payment.id,
                'invoice_id': donation_payment.quickpay_invoice_id,
                'qr_code': donation_payment.qr_code,
                'qr_image': donation_payment.qr_image,
                'payment_url': donation_payment.payment_url,
                'app_links': eval(donation_payment.app_links) if donation_payment.app_links else [],
                'amount': float(donation_payment.amount),
                'currency': donation_payment.currency,
                'expires_at': donation_payment.expires_at.isoformat() if donation_payment.expires_at else None
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': f'Failed to create donation payment: {str(e)}'
            }
    
    def mark_as_paid(self, payment_method=None):
        """Mark donation payment as paid and create actual donation record"""
        try:
            from app.models.donation import Donation
            import uuid
            
            # Update payment status
            self.status = 'paid'
            self.payment_date = datetime.utcnow()
            if payment_method:
                self.payment_method = payment_method
            
            # Generate unique donation ID
            donation_id = f"don_{uuid.uuid4().hex[:12]}"
            
            # Create donation record
            donation = Donation(
                user_id=self.streamer_user_id,
                donor_name=self.donor_name,
                amount=float(self.amount),
                message=self.message,
                platform=self.donor_platform,
                donor_platform_id=self.donor_user_id,
                donation_id=donation_id,
                donation_payment_id=self.id,
                is_test=False,
                created_at=datetime.utcnow(),
                processed_at=datetime.utcnow()
            )
            
            db.session.add(donation)
            db.session.commit()
            
            # Trigger real-time alert to streamer
            self._send_donation_alert(donation)
            
            # Update donation goal if active
            self._update_donation_goal(donation)
            
            # Add time to marathon if active
            self._update_marathon_time(donation)
            
            return True
            
        except Exception as e:
            db.session.rollback()
            from flask import current_app
            current_app.logger.error(f"Failed to mark donation payment as paid: {str(e)}")
            return False
    
    def _send_donation_alert(self, donation):
        """Send real-time donation alert to streamer"""
        try:
            from app.extensions import socketio
            from app.models.donation_alert_settings import DonationAlertSettings
            from app.models.alert_configuration import AlertConfiguration
            from app.models.user import User
            from flask import current_app
            
            # Get user to check subscription tier
            streamer = User.query.get(self.streamer_user_id)
            
            # Check if user has advanced tier
            subscription = streamer.get_current_subscription()
            has_advanced_tier = (subscription and 
                                subscription.feature_tier and 
                                subscription.feature_tier.value == 'advanced')
            
            if has_advanced_tier:
                # Use new alert configuration system
                settings = AlertConfiguration.get_config_for_amount(self.streamer_user_id, donation.amount)
                if not settings:
                    # Fallback to any configuration if none match the amount
                    configs = AlertConfiguration.get_user_configs(self.streamer_user_id)
                    settings = configs[0] if configs else None
                
                if not settings:
                    current_app.logger.warning(f"No alert configuration found for user {self.streamer_user_id}")
                    return
            else:
                # Use legacy settings for basic tier
                settings = DonationAlertSettings.get_or_create_for_user(self.streamer_user_id)
            
            # Check if donation meets minimum amount for alert (0 = no minimum)
            if settings.minimum_amount > 0 and donation.amount < settings.minimum_amount:
                current_app.logger.info(f"Donation {donation.amount}₮ below minimum alert threshold {settings.minimum_amount}₮ - no alert sent")
                return
            
            # Generate TTS audio if enabled and amount meets threshold
            tts_audio_url = None
            if (settings.tts_enabled and 
                donation.amount >= settings.tts_minimum_amount and 
                donation.message):  # Only if there's a message
                
                # Use only the donation message for TTS
                tts_text = donation.message.strip()
                
                # Generate TTS audio with usage limits checking
                from app.routes.main import generate_tts_audio
                tts_audio_url = generate_tts_audio(
                    self.streamer_user_id,
                    tts_text,
                    settings.tts_voice,
                    settings.tts_speed,
                    settings.tts_pitch,
                    request_type='donation'
                )
                
                if not tts_audio_url:
                    current_app.logger.warning(f"TTS generation failed for donation {donation.id} - possibly hit usage limits")
            
            # Get donor avatar and platform info if user is authenticated
            donator_avatar = None
            if self.donor_user_id:
                # User is authenticated, get their profile picture
                from app.models.user import User
                donor_user = User.query.get(self.donor_user_id)
                if donor_user:
                    donator_avatar = donor_user.get_profile_picture()
                    # Ensure avatar is not empty string or None
                    if not donator_avatar or donator_avatar.strip() == '':
                        donator_avatar = None
            
            # Prepare alert data
            alert_data = {
                'id': donation.id,
                'donor_name': donation.donor_name,
                'donator_name': donation.donor_name,  # For overlay compatibility
                'amount': donation.amount,
                'message': donation.message,
                'platform': donation.platform,
                'created_at': donation.created_at.isoformat(),
                'is_test': False,
                'tts_audio_url': tts_audio_url,
                'donator_avatar': donator_avatar,  # Will be None if no avatar available
                'is_guest': self.donor_user_id is None,  # True for guest users
                'has_avatar': donator_avatar is not None  # True only if avatar exists
            }
            
            # Add tab configuration info for advanced tier
            if has_advanced_tier and hasattr(settings, 'tab_number'):
                alert_data['tab_number'] = settings.tab_number
                alert_data['config_id'] = settings.id
            else:
                alert_data['tab_number'] = 1  # Default tab for basic tier
            
            # Send to streamer's room for overlay alerts
            room = f"user_{self.streamer_user_id}"
            socketio.emit('donation_alert', alert_data, room=room)
            
            # Send to donation feed room for public donation page updates
            donation_feed_room = f"donation_feed_{self.streamer_user_id}"
            socketio.emit('new_donation', alert_data, room=donation_feed_room)
            
            current_app.logger.info(f"Donation alert sent to streamer {self.streamer_user_id}: {donation.amount} MNT from {donation.donor_name}")
            if tts_audio_url:
                current_app.logger.info(f"TTS audio generated for donation: {tts_audio_url}")
            else:
                current_app.logger.info(f"No TTS generated - TTS enabled: {settings.tts_enabled}, Amount: {donation.amount}₮, TTS minimum: {settings.tts_minimum_amount}₮")
            
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Failed to send donation alert: {str(e)}")
    
    def _update_donation_goal(self, donation):
        """Update donation goal with new donation amount"""
        try:
            from app.models.donation_goal import DonationGoal
            
            # Get active goal for streamer
            goal = DonationGoal.query.filter_by(
                user_id=self.streamer_user_id,
                is_active=True
            ).first()
            
            if goal:
                # Add donation amount to goal
                goal.add_donation(donation.amount)
                
                from flask import current_app
                current_app.logger.info(f"Updated donation goal {goal.id} with {donation.amount}₮ - new total: {goal.get_total_amount()}₮")
            else:
                from flask import current_app
                current_app.logger.info(f"No active donation goal found for streamer {self.streamer_user_id}")
                
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Failed to update donation goal: {str(e)}")
    
    def _update_marathon_time(self, donation):
        """Add time to marathon based on donation amount - only if marathon is running"""
        try:
            from app.models.marathon import Marathon
            
            logger.info(f"DONATION: Starting marathon time update for donation {donation.id}")
            logger.info(f"DONATION: Streamer: {self.streamer_user_id}, Amount: {donation.amount}₮, Donor: {donation.donor_name}")
            
            # Get marathon for streamer
            marathon = Marathon.query.filter_by(user_id=self.streamer_user_id).first()
            
            if marathon:
                logger.info(f"DONATION: Found marathon {marathon.id} for streamer {self.streamer_user_id}")
                
                # Check if marathon is currently running (started and not paused)
                is_running = marathon.started_at is not None and not marathon.is_paused
                logger.info(f"DONATION: Marathon running status - started: {marathon.started_at is not None}, paused: {marathon.is_paused}, is_running: {is_running}")
                
                if not is_running:
                    logger.info(f"DONATION: Marathon not running for streamer {self.streamer_user_id} - donation time not added")
                    return
                
                # Add donation amount to accumulated donations
                logger.info(f"DONATION: Adding {donation.amount}₮ to accumulated donations")
                if marathon.add_donation_amount(donation.amount):
                    logger.info(f"DONATION: Successfully added {donation.amount}₮ to marathon donations total")
                else:
                    logger.warning(f"DONATION: Failed to add donation amount to marathon")
                
                # Calculate minutes to add based on donation amount and marathon price
                minutes_to_add = marathon.calculate_minutes_from_donation(donation.amount)
                logger.info(f"DONATION: Calculated {minutes_to_add} minutes to add (price: {marathon.minute_price}₮/min)")
                
                if minutes_to_add > 0:
                    logger.info(f"DONATION: Adding {minutes_to_add} minutes to marathon")
                    # Add time to marathon
                    marathon.add_time_minutes(minutes_to_add, source='donation')
                    
                    logger.info(f"DONATION: Successfully added {minutes_to_add} minutes to running marathon for {donation.amount}₮ donation from {donation.donor_name}")
                else:
                    logger.info(f"DONATION: Donation amount {donation.amount}₮ too small to add time (marathon price: {marathon.minute_price}₮/min)")
            else:
                logger.warning(f"DONATION: No marathon found for streamer {self.streamer_user_id}")
                
        except Exception as e:
            logger.error(f"DONATION: Failed to update marathon time: {str(e)}")
            import traceback
            logger.error(f"DONATION: Traceback: {traceback.format_exc()}")
    
    def mark_as_failed(self, reason=None):
        """Mark donation payment as failed"""
        self.status = 'failed'
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def mark_as_expired(self):
        """Mark donation payment as expired"""
        self.status = 'expired'
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def is_expired(self):
        """Check if donation payment has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def get_status_display(self):
        """Get human-readable status"""
        status_map = {
            'pending': 'Хүлээгдэж байна',
            'paid': 'Төлөгдсөн',
            'failed': 'Амжилтгүй',
            'expired': 'Хугацаа дууссан'
        }
        return status_map.get(self.status, self.status)