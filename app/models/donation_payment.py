from datetime import datetime
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from app.extensions import db, socketio
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
    
    # Sound effect integration
    type = db.Column(db.Enum('alert', 'sound_effect', name='payment_type'), default='alert')
    sound_effect_id = db.Column(db.Integer, db.ForeignKey('sound_effects.id'), nullable=True)
    
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
    sound_effect = db.relationship('SoundEffect', backref='payment_records')
    
    def __repr__(self):
        return f'<DonationPayment {self.id}: {self.donor_name} -> {self.streamer.username} ({self.amount} {self.currency})>'
    
    @classmethod
    def create_donation_payment(cls, streamer_user_id, donor_name, amount, message="", donor_platform="guest", donor_user_id=None, payment_type="alert", sound_effect_id=None):
        """
        Create a new donation payment and QPay invoice
        
        Args:
            streamer_user_id: ID of the streamer receiving the donation
            donor_name: Name of the donor
            amount: Donation amount in MNT
            message: Optional donation message
            donor_platform: Platform of the donor ('guest', 'twitch', 'youtube', 'kick')
            donor_user_id: ID of the donor if authenticated
            payment_type: Type of payment ('alert' or 'sound_effect')
            sound_effect_id: ID of sound effect if payment_type is 'sound_effect'
            
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
                type=payment_type,
                sound_effect_id=sound_effect_id,
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
            from flask import current_app
            
            current_app.logger.info(f"REAL DONATION: Starting mark_as_paid for {self.amount}₮ from {self.donor_name} to streamer {self.streamer_user_id}")
            
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
                type=getattr(self, 'type', 'alert'),
                sound_effect_id=getattr(self, 'sound_effect_id', None),
                is_test=False,
                created_at=datetime.utcnow(),
                processed_at=datetime.utcnow()
            )
            
            db.session.add(donation)
            db.session.commit()
            current_app.logger.info(f"REAL DONATION: Created donation record {donation.id} with donation_id {donation_id}")
            
            # Route based on donation type
            if getattr(self, 'type', 'alert') == 'sound_effect':
                current_app.logger.info(f"REAL DONATION: Sending sound effect for donation {donation.id}")
                self._send_sound_effect(donation)
            else:
                current_app.logger.info(f"REAL DONATION: Sending donation alert for donation {donation.id}")
                self._send_donation_alert(donation)
            
            # Update donation goal if active
            current_app.logger.info(f"REAL DONATION: Updating donation goal for donation {donation.id}")
            self._update_donation_goal(donation)
            
            # Add time to marathon if active
            current_app.logger.info(f"REAL DONATION: Updating marathon for donation {donation.id}")
            self._update_marathon_time(donation)
            
            # Update donor leaderboard
            current_app.logger.info(f"REAL DONATION: Updating donor leaderboard for donation {donation.id}")
            self._update_donor_leaderboard(donation)
            
            current_app.logger.info(f"REAL DONATION: Successfully processed donation {donation.id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            from flask import current_app
            current_app.logger.error(f"REAL DONATION: Failed to mark donation payment as paid: {str(e)}")
            import traceback
            current_app.logger.error(f"REAL DONATION: Traceback: {traceback.format_exc()}")
            return False
    
    def _send_donation_alert(self, donation):
        """Send real-time donation alert to streamer"""
        try:
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
            # Debug each TTS condition separately
            has_message = bool(donation.message and donation.message.strip())
            amount_meets_threshold = donation.amount >= settings.tts_minimum_amount
            
            current_app.logger.info(f"TTS CHECK: Tab {getattr(settings, 'tab_number', 'legacy')}")
            current_app.logger.info(f"  - TTS enabled: {settings.tts_enabled}")
            current_app.logger.info(f"  - Amount {donation.amount}₮ >= TTS minimum {settings.tts_minimum_amount}₮: {amount_meets_threshold}")
            current_app.logger.info(f"  - Has message: {has_message} (message: '{donation.message}')")
            current_app.logger.info(f"  - All conditions met: {settings.tts_enabled and amount_meets_threshold and has_message}")
            
            if (settings.tts_enabled and amount_meets_threshold and has_message):
                
                # Use only the donation message for TTS
                tts_text = donation.message.strip()
                
                current_app.logger.info(f"TTS GENERATION: Tab {getattr(settings, 'tab_number', 'legacy')}, Text: '{tts_text}', Voice: {settings.tts_voice}, Speed: {settings.tts_speed}, Pitch: {settings.tts_pitch}")
                
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
                
                if tts_audio_url:
                    current_app.logger.info(f"TTS SUCCESS: Tab {getattr(settings, 'tab_number', 'legacy')}, Generated: {tts_audio_url}")
                else:
                    current_app.logger.warning(f"TTS FAILED: Tab {getattr(settings, 'tab_number', 'legacy')}, No audio URL returned")
                
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
            current_app.logger.info(f"SOCKET: Emitting donation_alert to room '{room}' with data: {alert_data['donor_name']} - {alert_data['amount']}")
            
            # Try multiple emission approaches to ensure delivery
            try:
                socketio.emit('donation_alert', alert_data, room=room)
                current_app.logger.info(f"SOCKET: donation_alert emitted successfully to room '{room}'")
                
                # Also emit to all connected clients as a backup
                socketio.emit('donation_alert_global', alert_data, broadcast=True)
                current_app.logger.info(f"SOCKET: donation_alert_global broadcasted as backup")
                
            except Exception as e:
                current_app.logger.error(f"SOCKET: Failed to emit donation_alert: {str(e)}")
            
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
    
    def _send_sound_effect(self, donation):
        """Send sound effect to overlay queue"""
        try:
            from app.extensions import socketio
            from flask import current_app
            
            current_app.logger.info(f"SOUND EFFECT: Processing sound effect donation {donation.id}")
            
            # Get sound effect details
            if not self.sound_effect_id:
                current_app.logger.warning(f"SOUND EFFECT: No sound effect ID for donation {donation.id}")
                return
            
            from app.models.sound_effect import SoundEffect
            sound_effect = SoundEffect.query.get(self.sound_effect_id)
            if not sound_effect:
                current_app.logger.warning(f"SOUND EFFECT: Sound effect {self.sound_effect_id} not found")
                return
            
            # Create sound effect donation record for analytics
            from app.models.sound_effect_donation import SoundEffectDonation
            sound_donation = SoundEffectDonation(
                sound_effect_id=self.sound_effect_id,
                streamer_user_id=self.streamer_user_id,
                donor_name=self.donor_name,
                donor_user_id=self.donor_user_id,
                amount=self.amount,
                donation_payment_id=self.id
            )
            db.session.add(sound_donation)
            db.session.commit()
            
            # Get user's sound settings for volume level
            from app.models.user_sound_settings import UserSoundSettings
            try:
                user_settings = UserSoundSettings.get_or_create_for_user(self.streamer_user_id)
                volume_level = user_settings.volume_level if user_settings.volume_level is not None else 70
            except Exception as e:
                current_app.logger.warning(f"SOUND EFFECT: Failed to get volume settings for user {self.streamer_user_id}, using default: {str(e)}")
                volume_level = 70
            
            # Prepare sound effect data for overlay
            sound_data = {
                'type': 'sound_effect',
                'id': donation.id,
                'sound_effect_id': sound_effect.id,
                'sound_filename': sound_effect.filename,
                'sound_name': sound_effect.name,
                'duration_seconds': float(sound_effect.duration_seconds),
                'donor_name': donation.donor_name,
                'amount': donation.amount,
                'created_at': donation.created_at.isoformat(),
                'file_url': sound_effect.get_file_url(),
                'volume_level': volume_level
            }
            
            # Send to streamer's room for overlay playback
            room = f"user_{self.streamer_user_id}"
            socketio.emit('sound_effect_alert', sound_data, room=room)
            
            current_app.logger.info(f"SOUND EFFECT: Sent sound effect {sound_effect.name} to streamer {self.streamer_user_id}")
            
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"SOUND EFFECT: Failed to send sound effect: {str(e)}")
    
    def _update_donation_goal(self, donation):
        """Update donation goal with new donation amount"""
        try:
            from app.models.donation_goal import DonationGoal
            from flask import current_app
            
            current_app.logger.info(f"GOAL UPDATE: Starting goal update for streamer {self.streamer_user_id}, donation {donation.amount}₮")
            
            # Get active goal for streamer
            goal = DonationGoal.query.filter_by(
                user_id=self.streamer_user_id,
                is_active=True
            ).first()
            
            if goal:
                current_app.logger.info(f"GOAL UPDATE: Found active goal {goal.id}, current amount: {goal.get_total_amount()}₮, target: {goal.goal_amount}₮")
                
                # Add donation amount to goal
                goal.add_donation(donation.amount)
                
                current_app.logger.info(f"GOAL UPDATE: Successfully updated goal {goal.id} with {donation.amount}₮ - new total: {goal.get_total_amount()}₮")
            else:
                current_app.logger.info(f"GOAL UPDATE: No active donation goal found for streamer {self.streamer_user_id}")
                
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"GOAL UPDATE: Failed to update donation goal: {str(e)}")
            import traceback
            current_app.logger.error(f"GOAL UPDATE: Traceback: {traceback.format_exc()}")
    
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
    
    def _update_donor_leaderboard(self, donation):
        """Update donor leaderboard with new donation"""
        try:
            from app.models.donor_leaderboard import DonorLeaderboard
            from app.models.donor_leaderboard_settings import DonorLeaderboardSettings
            
            current_app.logger.info(f"LEADERBOARD: Starting leaderboard update for donation {donation.id}")
            current_app.logger.info(f"LEADERBOARD: Streamer: {self.streamer_user_id}, Amount: {donation.amount}₮, Donor: {donation.donor_name}")
            
            # Get old position before update (for position change detection)
            old_entry = DonorLeaderboard.query.filter_by(
                user_id=self.streamer_user_id,
                donor_name=donation.donor_name
            ).first()
            
            old_position = None
            if old_entry:
                old_position = DonorLeaderboard.get_donor_position(
                    self.streamer_user_id, 
                    donation.donor_name
                )
                current_app.logger.info(f"LEADERBOARD: Donor {donation.donor_name} current position: {old_position}")
            else:
                current_app.logger.info(f"LEADERBOARD: New donor {donation.donor_name} joining leaderboard")
            
            # Update leaderboard entry
            updated_entry = DonorLeaderboard.update_donor_entry(self.streamer_user_id, donation)
            
            if updated_entry:
                # Get new position after update
                new_position = DonorLeaderboard.get_donor_position(
                    self.streamer_user_id,
                    donation.donor_name
                )
                
                current_app.logger.info(f"LEADERBOARD: Donor {donation.donor_name} new position: {new_position}")
                
                # Check if leaderboard is enabled and emit real-time update
                settings = DonorLeaderboardSettings.query.filter_by(user_id=self.streamer_user_id).first()
                if settings and settings.is_enabled:
                    current_app.logger.info(f"LEADERBOARD: Emitting real-time update for streamer {self.streamer_user_id}")
                    
                    # Get updated top donors
                    top_donors = DonorLeaderboard.get_top_donors(self.streamer_user_id, limit=settings.positions_count)
                    
                    # Prepare position change data
                    position_change_data = None
                    if old_position and new_position and old_position != new_position:
                        position_change_data = {
                            'donor_name': donation.donor_name,
                            'old_position': old_position,
                            'new_position': new_position,
                            'is_throne_takeover': new_position == 1 and old_position != 1,
                            'amount_added': float(donation.amount)
                        }
                        current_app.logger.info(f"LEADERBOARD: Position change detected: {position_change_data}")
                    
                    # Emit leaderboard update
                    from app.extensions import socketio
                    socketio.emit('leaderboard_updated', {
                        'settings': settings.to_dict(),
                        'top_donors': [donor.to_dict() for donor in top_donors],
                        'enabled': settings.is_enabled,
                        'position_change': position_change_data
                    }, room=f'leaderboard_{self.streamer_user_id}')
                    
                    current_app.logger.info(f"LEADERBOARD: Successfully emitted leaderboard update for streamer {self.streamer_user_id}")
                else:
                    current_app.logger.info(f"LEADERBOARD: Leaderboard disabled for streamer {self.streamer_user_id} - no real-time update")
                
                current_app.logger.info(f"LEADERBOARD: Successfully updated leaderboard for donation {donation.id}")
            else:
                current_app.logger.warning(f"LEADERBOARD: Failed to update leaderboard entry for donation {donation.id}")
                
        except Exception as e:
            current_app.logger.error(f"LEADERBOARD: Failed to update donor leaderboard: {str(e)}")
            import traceback
            current_app.logger.error(f"LEADERBOARD: Traceback: {traceback.format_exc()}")
    
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