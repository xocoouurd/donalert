from flask import Blueprint, render_template, redirect, url_for, request, jsonify, abort, flash, current_app
from flask_login import current_user, login_required
from flask_socketio import emit, join_room, leave_room
from app.utils.quickpay_payment import create_subscription_invoice, check_subscription_payment_status
from app.models.subscription_payment import SubscriptionPayment
from app.models.subscription import Subscription
from app.extensions import db, socketio
import csv
import os
import json
import uuid
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from werkzeug.utils import secure_filename
import shutil
import re

main_bp = Blueprint('main', __name__)

# Simple rate limiting for marathon API
marathon_api_calls = defaultdict(list)

def marathon_rate_limit(max_calls=60, window_minutes=1):
    """Rate limiter for marathon API endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client identifier (IP or token)
            client_id = request.remote_addr
            token = request.get_json(silent=True)
            if token and isinstance(token, dict) and 'token' in token:
                client_id = f"token_{token['token']}"
            elif current_user.is_authenticated:
                client_id = f"user_{current_user.id}"
            
            now = datetime.utcnow()
            window_start = now - timedelta(minutes=window_minutes)
            
            # Clean old entries
            marathon_api_calls[client_id] = [
                call_time for call_time in marathon_api_calls[client_id]
                if call_time > window_start
            ]
            
            # Check rate limit
            if len(marathon_api_calls[client_id]) >= max_calls:
                current_app.logger.warning(f"Rate limit exceeded for {client_id}")
                return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429
            
            # Record this call
            marathon_api_calls[client_id].append(now)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def generate_tts_audio(user_id, text, voice, speed, pitch, request_type='donation'):
    """Generate TTS audio and return public URL"""
    try:
        from app.utils.chimege_tts import ChimegeTTS
        from app.utils.tts_limiter import TTSLimiter
        from app.models.user import User
        
        current_app.logger.info(f"TTS GENERATION: Starting for user {user_id}, text: '{text}'")
        
        # Get user object for tier checking
        user = User.query.get(user_id)
        
        # Check usage limits
        limiter = TTSLimiter(user)
        limit_check = limiter.check_limits(user_id, text, request_type)
        
        if not limit_check['allowed']:
            current_app.logger.warning(f"TTS GENERATION: Usage limit exceeded: {limit_check['reason']}")
            limiter.log_request(user_id, text, voice, request_type, success=False, error_message=limit_check['reason'])
            return None
        
        # Generate TTS
        tts = ChimegeTTS()
        normalized_text = tts.normalize_text(text)
        temp_audio_path = tts.synthesize_text(normalized_text, voice_id=voice, speed=speed, pitch=pitch)
        
        if not temp_audio_path:
            current_app.logger.error("TTS GENERATION: Synthesis failed")
            limiter.log_request(user_id, text, voice, request_type, success=False, error_message="Synthesis failed")
            return None
        
        # Move to public uploads folder with unique name
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
        tts_folder = os.path.join(upload_folder, 'tts')
        os.makedirs(tts_folder, exist_ok=True)
        
        # Generate unique filename
        unique_filename = f"tts_{uuid.uuid4().hex}.wav"
        public_audio_path = os.path.join(tts_folder, unique_filename)
        
        # Move file from temp to public location
        import shutil
        shutil.move(temp_audio_path, public_audio_path)
        
        # Generate public URL
        public_url = f"/static/uploads/tts/{unique_filename}"
        current_app.logger.info(f"TTS GENERATION: Success! Public URL: {public_url}")
        
        # Log successful request
        limiter.log_request(user_id, text, voice, request_type, success=True)
        
        # Schedule cleanup after 2 minutes (fallback in case overlay cleanup fails)
        import threading
        def delayed_cleanup():
            import time
            time.sleep(120)  # Wait 2 minutes
            try:
                if os.path.exists(public_audio_path):
                    os.remove(public_audio_path)
                    current_app.logger.info(f"TTS CLEANUP: Fallback cleanup completed: {public_audio_path}")
            except Exception as e:
                current_app.logger.error(f"TTS CLEANUP: Fallback cleanup failed: {str(e)}")
        
        cleanup_thread = threading.Thread(target=delayed_cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        return public_url
        
    except Exception as e:
        current_app.logger.error(f"TTS GENERATION: Exception: {str(e)}")
        return None

@main_bp.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('home.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# DEV: Tier Toggle Endpoint (Remove in production)
@main_bp.route('/dev')
@login_required
def dev_page():
    """Development tools and utilities page"""
    if not current_user.dev_access:
        from flask import abort
        abort(404)
    return render_template('dev.html')

@main_bp.route('/dev/simulate-donation', methods=['POST'])
@login_required
def simulate_donation():
    """Simulate a donation for testing all systems - uses REAL donation flow"""
    if not current_user.dev_access:
        from flask import abort
        abort(404)
    try:
        data = request.get_json()
        
        # Validate input
        amount = float(data.get('amount', 0))
        message = data.get('message', 'Туршилтын хандив')
        donator_name = data.get('donator_name', 'Туршилтын хэрэглэгч')
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        current_app.logger.info(f"DEV: Simulating donation via REAL donation flow for user {current_user.id}: {amount}₮")
        
        # Import required models
        from app.models.donation_payment import DonationPayment
        import uuid
        from datetime import datetime
        
        # Create a test DonationPayment record that mimics a real payment
        # This will go through the exact same flow as real donations
        test_payment = DonationPayment(
            streamer_user_id=current_user.id,
            donor_name=donator_name,
            donor_platform='dev_test',
            donor_user_id=None,  # Guest donation
            amount=amount,
            currency='MNT',
            message=message,
            type='alert',
            sound_effect_id=None,
            quickpay_invoice_id=f'test_{uuid.uuid4().hex[:12]}',
            status='paid',  # Mark as paid so mark_as_paid() works
            payment_date=datetime.utcnow(),
            payment_method='dev_test',
            expires_at=datetime.utcnow()
        )
        
        # Add to session but don't commit (keep it as test-only)
        db.session.add(test_payment)
        db.session.flush()  # Get the ID without committing to database
        
        current_app.logger.info(f"DEV: Created test payment record {test_payment.id}")
        
        # Now use the REAL donation flow - call mark_as_paid()
        # This will handle everything: donation creation, alerts, marathon, goal, leaderboard
        success = test_payment.mark_as_paid(payment_method='dev_test')
        
        if success:
            current_app.logger.info(f"DEV: Test donation processed successfully via real donation flow")
            
            # Keep the test payment record - it's clearly marked as 'dev_test'
            # This allows test donations to go through the exact same flow as real donations
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Test donation processed via real donation flow',
                'alert_triggered': True,
                'marathon_updated': True,
                'goal_updated': True,
                'leaderboard_updated': True
            })
        else:
            current_app.logger.error(f"DEV: Test donation processing failed")
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Test donation processing failed'}), 500
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"DEV: Donation simulation failed: {str(e)}")
        import traceback
        current_app.logger.error(f"DEV: Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/dev/toggle-tier', methods=['POST'])
@login_required
def toggle_tier():
    """Toggle user's subscription tier for development testing"""
    if not current_user.dev_access:
        from flask import abort
        abort(404)
    try:
        from app.models.subscription import SubscriptionTier
        
        # Get current subscription
        current_subscription = current_user.get_current_subscription()
        
        if not current_subscription:
            return jsonify({'success': False, 'error': 'No active subscription found'}), 400
        
        # Toggle between basic and advanced
        if current_subscription.feature_tier == SubscriptionTier.BASIC:
            new_tier = SubscriptionTier.ADVANCED
            new_tier_display = "Дэвшилтэт"
        else:
            new_tier = SubscriptionTier.BASIC  
            new_tier_display = "Үндсэн"
        
        # Update the subscription
        current_subscription.feature_tier = new_tier
        db.session.commit()
        
        current_app.logger.info(f"DEV: User {current_user.id} tier toggled to {new_tier.value}")
        
        return jsonify({
            'success': True,
            'new_tier': new_tier.value,
            'new_tier_display': new_tier_display,
            'message': f'Tier солигдлоо: {new_tier_display}'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling tier: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/sound-effects/list', methods=['GET'])
@login_required
def list_sound_effects():
    """Get list of available sound effects for dev testing"""
    try:
        from app.models.sound_effect import SoundEffect
        
        sounds = SoundEffect.query.filter_by(is_active=True).all()
        sound_list = []
        
        for sound in sounds:
            sound_list.append({
                'id': sound.id,
                'name': sound.name,
                'category': sound.category,
                'duration': float(sound.duration_seconds)
            })
        
        return jsonify({
            'success': True,
            'sounds': sound_list
        })
        
    except Exception as e:
        current_app.logger.error(f"Error listing sound effects: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/dev/simulate-sound-effect', methods=['POST'])
@login_required  
def simulate_sound_effect():
    """Simulate a sound effect for testing - uses REAL donation flow"""
    if not current_user.dev_access:
        from flask import abort
        abort(403)
    
    try:
        from app.models.sound_effect import SoundEffect
        from app.models.donation_payment import DonationPayment
        import uuid
        from datetime import datetime
        
        data = request.get_json()
        
        # Validate required fields
        amount = data.get('amount')
        sound_effect_id = data.get('sound_effect_id')
        donator_name = data.get('donator_name', 'Test User')
        
        if not amount or not sound_effect_id:
            return jsonify({'success': False, 'error': 'Amount and sound effect ID are required'}), 400
        
        # Get sound effect
        sound_effect = SoundEffect.query.get(sound_effect_id)
        if not sound_effect or not sound_effect.is_active:
            return jsonify({'success': False, 'error': 'Sound effect not found or inactive'}), 404
        
        current_app.logger.info(f"DEV: Simulating sound effect via REAL donation flow for user {current_user.id}: {amount}₮")
        
        # Create a test DonationPayment record for sound effect
        # This will go through the exact same flow as real sound effect donations
        test_payment = DonationPayment(
            streamer_user_id=current_user.id,
            donor_name=donator_name,
            donor_platform='dev_test',
            donor_user_id=None,  # Guest donation
            amount=amount,
            currency='MNT',
            message='',
            type='sound_effect',
            sound_effect_id=sound_effect_id,
            quickpay_invoice_id=f'test_{uuid.uuid4().hex[:12]}',
            status='paid',  # Mark as paid so mark_as_paid() works
            payment_date=datetime.utcnow(),
            payment_method='dev_test',
            expires_at=datetime.utcnow()
        )
        
        # Add to session but don't commit yet
        db.session.add(test_payment)
        db.session.flush()  # Get the ID without committing to database
        
        current_app.logger.info(f"DEV: Created test sound effect payment record {test_payment.id}")
        
        # Now use the REAL donation flow - call mark_as_paid()
        # This will handle everything: donation creation, sound effect, leaderboard
        success = test_payment.mark_as_paid(payment_method='dev_test')
        
        if success:
            current_app.logger.info(f"DEV: Test sound effect processed successfully via real donation flow")
            
            # Keep the test payment record - it's clearly marked as 'dev_test'
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Test sound effect processed via real donation flow: {sound_effect.name}',
                'sound_effect_triggered': True,
                'leaderboard_updated': True
            })
        else:
            current_app.logger.error(f"DEV: Test sound effect processing failed")
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Test sound effect processing failed'}), 500
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error simulating sound effect: {str(e)}")
        import traceback
        current_app.logger.error(f"DEV: Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/donation-alert')
@login_required
def donation_alert():
    from app.models.donation_alert_settings import DonationAlertSettings
    from app.models.alert_configuration import AlertConfiguration
    from app.models.user_asset import UserAsset
    
    # Check if user has advanced tier
    subscription = current_user.get_current_subscription()
    has_advanced_tier = (subscription and 
                        subscription.feature_tier and 
                        subscription.feature_tier.value == 'advanced')
    
    if has_advanced_tier:
        # For advanced tier, get all alert configurations
        alert_configs = AlertConfiguration.get_user_configs(current_user.id)
        
        # If no configurations exist, create default one
        if not alert_configs:
            default_config = AlertConfiguration.create_default_config(current_user.id, 1)
            db.session.add(default_config)
            db.session.commit()
            alert_configs = [default_config]
        
        # Use first config as default for template compatibility
        settings = alert_configs[0]
    else:
        # For basic tier, use legacy settings
        settings = DonationAlertSettings.get_or_create_for_user(current_user.id)
    
    # Ensure user has an overlay token
    overlay_token = current_user.get_overlay_token()
    
    # Get user's assets
    user_gifs = UserAsset.get_user_assets(current_user.id, 'gif')
    user_sounds = UserAsset.get_user_assets(current_user.id, 'sound')
    
    # Get default assets
    default_gifs = get_default_assets('gifs')
    default_sounds = get_default_assets('sounds')
    
    template_vars = {
        'settings': settings,
        'user_gifs': user_gifs,
        'user_sounds': user_sounds,
        'default_gifs': default_gifs,
        'default_sounds': default_sounds,
        'overlay_token': overlay_token
    }
    
    # For advanced tier, also pass alert configurations
    if has_advanced_tier:
        template_vars['alert_configurations'] = [config.to_dict() for config in alert_configs]
    
    return render_template('donation_alert.html', **template_vars)

@main_bp.route('/donation-goal')
@login_required
def donation_goal():
    from app.models.donation_goal import DonationGoal
    
    # Get or create goal for user
    goal = DonationGoal.get_or_create_for_user(current_user.id)
    
    # Ensure user has an overlay token
    overlay_token = current_user.get_overlay_token()
    
    return render_template('donation_goal.html', 
                         goal=goal,
                         overlay_token=overlay_token)

@main_bp.route('/donation-goal/settings', methods=['POST'])
@login_required
def update_donation_goal_settings():
    try:
        from app.models.donation_goal import DonationGoal
        
        # Get or create goal for user
        goal = DonationGoal.get_or_create_for_user(current_user.id)
        
        # Override total amount if provided (highest priority)
        override_amount = request.form.get('override_amount')
        if override_amount:
            new_total = float(override_amount)
            goal.override_total_amount(new_total)
            return jsonify({'success': True, 'new_total': goal.get_total_amount()})
        
        # Manual adjustment if provided (priority over other updates)
        manual_adjustment = request.form.get('manual_adjustment')
        if manual_adjustment:
            adjustment_amount = float(manual_adjustment)
            goal.add_manual_adjustment(adjustment_amount)
            # Return early for manual adjustments to avoid updating other fields
            return jsonify({'success': True, 'new_total': goal.get_total_amount()})
        
        # Update goal settings (only if not a manual adjustment)
        goal.title = request.form.get('title', goal.title)
        if request.form.get('goal_amount'):
            goal.goal_amount = float(request.form.get('goal_amount'))
        goal.is_active = request.form.get('is_active') == 'on'
        
        # Title styling
        goal.title_font_size = int(request.form.get('title_font_size', goal.title_font_size))
        goal.title_font_weight = int(request.form.get('title_font_weight', goal.title_font_weight))
        goal.title_color = request.form.get('title_color', goal.title_color)
        
        # Progress bar styling
        goal.progress_height = int(request.form.get('progress_height', goal.progress_height))
        goal.progress_text_size = int(request.form.get('progress_text_size', goal.progress_text_size))
        goal.progress_font_weight = int(request.form.get('progress_font_weight', goal.progress_font_weight))
        goal.progress_font_color = request.form.get('progress_font_color', goal.progress_font_color)
        goal.progress_color = request.form.get('progress_color', goal.progress_color)
        goal.progress_background_color = request.form.get('progress_background_color', goal.progress_background_color)
        goal.progress_animation = request.form.get('progress_animation', goal.progress_animation)
        
        db.session.commit()
        
        # Send real-time update
        goal._send_goal_update()
        
        return jsonify({'success': True})
        
    except Exception as e:
        current_app.logger.error(f"Error updating donation goal settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/donation-goal/reset', methods=['POST'])
@login_required
def reset_donation_goal():
    try:
        from app.models.donation_goal import DonationGoal
        
        # Get goal for user
        goal = DonationGoal.get_or_create_for_user(current_user.id)
        goal.reset_goal()
        
        return jsonify({'success': True})
        
    except Exception as e:
        current_app.logger.error(f"Error resetting donation goal: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/goal-overlay/<overlay_token>')
def goal_overlay(overlay_token):
    from app.models.user import User
    from app.models.donation_goal import DonationGoal
    
    # Find user by overlay token
    user = User.query.filter_by(overlay_token=overlay_token).first()
    if not user:
        abort(404)
    
    # Get active goal
    goal = DonationGoal.get_or_create_for_user(user.id)
    
    return render_template('goal_overlay.html', 
                         user=user,
                         goal=goal)

@main_bp.route('/subscription/purchase', methods=['POST'])
@login_required
def purchase_subscription():
    """Create subscription payment invoice"""
    try:
        data = request.get_json()
        
        # Validate request data - support both old and new API formats
        tier = data.get('tier')  # Legacy: 'basic', 'advanced'
        months = data.get('months', 1)  # Legacy: number of months
        
        # New format (optional for now)
        feature_tier = data.get('feature_tier', tier)  # 'basic', 'advanced'
        billing_cycle = data.get('billing_cycle')  # 'monthly', 'quarterly', etc.
        
        # Convert legacy months to billing cycle if not provided
        if not billing_cycle:
            if months == 1:
                billing_cycle = 'monthly'
            elif months == 3:
                billing_cycle = 'quarterly'
            elif months == 6:
                billing_cycle = 'biannual'
            elif months == 12:
                billing_cycle = 'annual'
            else:
                billing_cycle = 'monthly'  # Default fallback
        
        # Validate feature tier
        if not feature_tier or feature_tier not in ['basic', 'advanced']:
            return jsonify({'error': 'Invalid subscription tier'}), 400
        
        # Validate billing cycle
        if billing_cycle not in ['monthly', 'quarterly', 'biannual', 'annual']:
            return jsonify({'error': 'Invalid billing cycle'}), 400
        
        # Create QuickPay invoice using legacy method for now
        invoice_result = create_subscription_invoice(current_user.id, feature_tier, months)
        
        if not invoice_result.get('success'):
            return jsonify({'error': invoice_result.get('error', 'Failed to create invoice')}), 500
        
        # Check if we should use new tier change logic
        use_tier_change_logic = data.get('use_tier_change_logic', False)
        
        # Create payment record with tier change metadata
        payment = SubscriptionPayment.create_payment_record(
            user_id=current_user.id,
            tier=tier,
            months=months,
            amount=invoice_result.get('amount'),
            invoice_data=invoice_result
        )
        
        # Store tier change intent in payment metadata
        if use_tier_change_logic:
            metadata = payment.get_metadata()
            metadata['use_tier_change_logic'] = True
            metadata['target_feature_tier'] = feature_tier
            metadata['target_billing_cycle'] = billing_cycle
            payment.set_metadata(metadata)
            db.session.commit()
        
        # Return payment info
        return jsonify({
            'success': True,
            'payment_id': payment.id,
            'payment_reference': payment.payment_reference,
            'invoice_id': invoice_result.get('invoice_id'),
            'qr_code': invoice_result.get('qr_code'),
            'qr_image': invoice_result.get('qr_image'),
            'amount': invoice_result.get('amount'),
            'currency': invoice_result.get('currency'),
            'description': invoice_result.get('description'),
            'app_links': invoice_result.get('app_links', []),
            'payment_url': invoice_result.get('payment_url'),
            'expires_at': payment.expires_at.isoformat() if payment.expires_at else None
        })
        
    except Exception as e:
        return jsonify({'error': f'Payment creation failed: {str(e)}'}), 500

@main_bp.route('/subscription/cancel-scheduled-change', methods=['POST'])
@login_required
def cancel_scheduled_change():
    """Cancel a scheduled tier change"""
    try:
        current_subscription = current_user.get_current_subscription()
        
        if not current_subscription:
            return jsonify({'error': 'Идэвхтэй багц олдсонгүй'}), 404
        
        if not current_subscription.is_pending_downgrade():
            return jsonify({'error': 'Төлөвлөсөн өөрчлөлт байхгүй'}), 400
        
        # Cancel the scheduled change
        current_subscription.cancel_scheduled_change()
        
        # Also remove any pending subscription records
        from app.models.subscription import SubscriptionStatus
        pending_subscriptions = Subscription.query.filter_by(
            user_id=current_user.id,
            status=SubscriptionStatus.PENDING
        ).all()
        
        for pending_sub in pending_subscriptions:
            db.session.delete(pending_sub)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Төлөвлөсөн өөрчлөлт амжилттай цуцлагдлаа'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Алдаа гарлаа: {str(e)}'}), 500

@main_bp.route('/admin/scheduled-changes', methods=['GET'])
@login_required
def admin_scheduled_changes():
    """Admin page to view and manage scheduled tier changes"""
    if not current_user.is_admin:
        abort(403)
    
    from app.models.subscription import SubscriptionStatus
    from datetime import datetime
    
    # Get all scheduled changes
    current_time = datetime.utcnow()
    scheduled_changes = Subscription.query.filter(
        Subscription.scheduled_change_date.isnot(None),
        Subscription.status == SubscriptionStatus.ACTIVE
    ).order_by(Subscription.scheduled_change_date.asc()).all()
    
    # Categorize changes
    overdue_changes = [s for s in scheduled_changes if s.scheduled_change_date < current_time]
    upcoming_changes = [s for s in scheduled_changes if s.scheduled_change_date >= current_time]
    
    return render_template('admin/scheduled_changes.html', 
                         overdue_changes=overdue_changes,
                         upcoming_changes=upcoming_changes,
                         current_time=current_time)

@main_bp.route('/admin/process-scheduled-changes', methods=['POST'])
@login_required  
def admin_process_scheduled_changes():
    """Admin endpoint to manually trigger scheduled change processing"""
    if not current_user.is_admin:
        abort(403)
    
    try:
        changes_processed = Subscription.process_scheduled_changes()
        
        return jsonify({
            'success': True,
            'message': f'Амжилттай {changes_processed} өөрчлөлт боловсруулсан',
            'changes_processed': changes_processed
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Алдаа гарлаа: {str(e)}'
        }), 500

@main_bp.route('/subscription/payment/<int:payment_id>/status')
@login_required
def check_payment_status(payment_id):
    """Check payment status"""
    try:
        # Get payment record
        payment = SubscriptionPayment.query.filter_by(
            id=payment_id,
            user_id=current_user.id
        ).first()
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Check if payment is already processed
        if payment.status != 'pending':
            return jsonify({
                'success': True,
                'status': payment.status,
                'payment_reference': payment.payment_reference,
                'paid_at': payment.paid_at.isoformat() if payment.paid_at else None
            })
        
        # Check if payment is expired
        if payment.is_expired():
            payment.mark_as_expired()
            return jsonify({
                'success': True,
                'status': 'expired',
                'payment_reference': payment.payment_reference
            })
        
        # Query QuickPay for current status
        if payment.quickpay_invoice_id:
            quickpay_result = check_subscription_payment_status(payment.quickpay_invoice_id)
            
            if quickpay_result.get('success'):
                payment_data = quickpay_result.get('data', {})
                quickpay_status = payment_data.get('invoice_status', '').upper()
                
                # Update payment status based on QuickPay response
                if quickpay_status == 'PAID':
                    payment.mark_as_paid(payment_data)
                    
                    # Activate subscription using appropriate logic
                    metadata = payment.get_metadata()
                    if metadata.get('use_tier_change_logic'):
                        # Use new tier change logic
                        from app.models.subscription import SubscriptionTier, BillingCycle
                        
                        # Convert strings to enums
                        target_tier_str = metadata.get('target_feature_tier', payment.tier)
                        billing_cycle_str = metadata.get('target_billing_cycle', 'monthly')
                        
                        target_tier = SubscriptionTier.BASIC if target_tier_str == 'basic' else SubscriptionTier.ADVANCED
                        billing_cycle_map = {
                            'monthly': BillingCycle.MONTHLY,
                            'quarterly': BillingCycle.QUARTERLY,
                            'biannual': BillingCycle.BIANNUAL,
                            'annual': BillingCycle.ANNUAL
                        }
                        billing_cycle = billing_cycle_map.get(billing_cycle_str, BillingCycle.MONTHLY)
                        
                        subscription = Subscription.handle_tier_change(
                            user_id=current_user.id,
                            target_tier=target_tier,
                            billing_cycle=billing_cycle,
                            payment_id=payment.id
                        )
                    else:
                        # Use legacy logic
                        subscription = Subscription.create_or_extend_subscription(
                            user_id=current_user.id,
                            tier=payment.tier,
                            months=payment.months,
                            payment_id=payment.id
                        )
                    
                    return jsonify({
                        'success': True,
                        'status': 'paid',
                        'payment_reference': payment.payment_reference,
                        'paid_at': payment.paid_at.isoformat(),
                        'subscription_id': subscription.id if subscription else None
                    })
                elif quickpay_status in ['FAILED', 'CANCELLED']:
                    payment.mark_as_failed(f"QuickPay status: {quickpay_status}")
                    return jsonify({
                        'success': True,
                        'status': 'failed',
                        'payment_reference': payment.payment_reference
                    })
        
        # Return current status
        return jsonify({
            'success': True,
            'status': payment.status,
            'payment_reference': payment.payment_reference,
            'expires_at': payment.expires_at.isoformat() if payment.expires_at else None
        })
        
    except Exception as e:
        return jsonify({'error': f'Status check failed: {str(e)}'}), 500

@main_bp.route('/subscription/callback')
def subscription_callback():
    """Handle QuickPay payment callback"""
    try:
        # Get webhook token from query parameters
        webhook_token = request.args.get('token')
        
        if not webhook_token:
            abort(400)
        
        # Get payment by webhook token
        payment = SubscriptionPayment.get_by_webhook_token(webhook_token)
        
        if not payment:
            abort(404)
        
        # Parse callback data
        callback_data = request.get_json() or {}
        
        # Log callback for debugging
        from flask import current_app
        current_app.logger.info(f"QuickPay callback received for payment {payment.id}: {callback_data}")
        
        # Check payment status
        payment_status = callback_data.get('invoice_status', callback_data.get('status', '')).upper()
        
        if payment_status == 'PAID':
            # Mark payment as paid
            payment.mark_as_paid(callback_data)
            
            # Activate/extend subscription
            subscription = Subscription.create_or_extend_subscription(
                user_id=payment.user_id,
                tier=payment.tier,
                months=payment.months,
                payment_id=payment.id
            )
            
            current_app.logger.info(f"Subscription activated for user {payment.user_id}, subscription ID: {subscription.id if subscription else None}")
            
        elif payment_status in ['FAILED', 'CANCELLED']:
            payment.mark_as_failed(f"Callback status: {payment_status}")
            current_app.logger.info(f"Payment {payment.id} marked as failed: {payment_status}")
        
        return jsonify({'success': True, 'message': 'Callback processed'})
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Subscription callback error: {str(e)}")
        return jsonify({'error': 'Callback processing failed'}), 500

def get_bank_codes():
    """Get available bank codes from CSV file"""
    try:
        bank_codes = []
        csv_path = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'bank_codes.csv')
        
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Skip rows 1 and 21 (Bank of Mongolia and Test bank)
                # Also skip: Инвэскор ББСБ, Кредит банк, Мобифинанс, Төрийн сан
                excluded_banks = ['1', '21', '8', '16', '17', '20']  # Row numbers to exclude
                if row['№'] not in excluded_banks:
                    bank_codes.append({
                        'code': row['bank code'],
                        'name': row['Монгол'],
                        'english': row['English']
                    })
        
        # Sort banks - priority banks first (4,5,3,11,13,18), then others
        priority_codes = ['050000', '150000', '040000', '320000', '340000', '390000']  # 4,5,3,11,13,18
        
        priority_banks = []
        other_banks = []
        
        for bank in bank_codes:
            if bank['code'] in priority_codes:
                priority_banks.append(bank)
            else:
                other_banks.append(bank)
        
        # Sort priority banks by their position in priority_codes
        priority_banks.sort(key=lambda x: priority_codes.index(x['code']))
        
        # Sort other banks alphabetically
        other_banks.sort(key=lambda x: x['name'])
        
        return priority_banks + other_banks
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error loading bank codes: {str(e)}")
        return []

def load_bank_logos():
    """Load bank logos from JSON file"""
    try:
        logo_file = os.path.join(os.path.dirname(__file__), '..', 'static', 'data', 'bank_logos.json')
        if os.path.exists(logo_file):
            with open(logo_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        current_app.logger.warning(f"Failed to load bank logos: {str(e)}")
        return {}

@main_bp.route('/bank-account', methods=['GET', 'POST'])
@login_required
def bank_account():
    """Manage user's bank account information"""
    if request.method == 'POST':
        try:
            # Get form data
            bank_code = request.form.get('bank_code')
            bank_name = request.form.get('bank_name')
            account_name = request.form.get('account_name')
            iban = request.form.get('iban')
            
            # Validate required fields
            if not all([bank_code, bank_name, account_name, iban]):
                flash('Бүх талбарыг бөглөнө үү.', 'error')
                return redirect(url_for('main.bank_account'))
            
            # Validate IBAN format (MN + 18 digits)
            if not iban.startswith('MN') or len(iban) != 20 or not iban[2:].isdigit():
                flash('IBAN дугаар буруу байна. MN + 18 тоо байх ёстой.', 'error')
                return redirect(url_for('main.bank_account'))
            
            # Extract account number from IBAN (last 10 digits)
            account_number = iban[10:]  # Skip MN + 8 bank/branch code digits
            
            # Update user's bank account
            current_user.set_bank_account(
                account_name=account_name,
                account_number=account_number,
                bank_iban=iban,
                bank_code=bank_code,
                bank_name=bank_name
            )
            
            db.session.commit()
            flash('Банкны мэдээлэл амжилттай хадгалагдлаа.', 'success')
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Алдаа гарлаа: {str(e)}', 'error')
            return redirect(url_for('main.bank_account'))
    
    # GET request - show form
    bank_codes = get_bank_codes()
    bank_logos = load_bank_logos()
    
    # Add logos to bank codes data
    for bank in bank_codes:
        bank['logo'] = bank_logos.get(bank['code'], '')
    
    return render_template('bank_account.html', bank_codes=bank_codes)

@main_bp.route('/bank-account/delete', methods=['POST'])
@login_required
def delete_bank_account():
    """Delete user's bank account information"""
    try:
        current_user.clear_bank_account()
        db.session.commit()
        flash('Банкны мэдээлэл устгагдлаа.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Алдаа гарлаа: {str(e)}', 'error')
    
    return redirect(url_for('main.dashboard'))

def get_default_assets(asset_type):
    """Get list of default assets (gifs or sounds)"""
    try:
        asset_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'default', asset_type)
        if not os.path.exists(asset_dir):
            return []
        
        assets = []
        for filename in os.listdir(asset_dir):
            if filename.lower().endswith(('.gif', '.png', '.jpg', '.jpeg')) if asset_type == 'gifs' else filename.lower().endswith(('.mp3', '.wav', '.ogg')):
                assets.append({
                    'filename': filename,
                    'display_name': os.path.splitext(filename)[0].replace('-', ' ').replace('_', ' ').title(),
                    'url': f"/static/assets/default/{asset_type}/{filename}",
                    'is_default': True
                })
        
        return sorted(assets, key=lambda x: x['display_name'])
    except Exception as e:
        current_app.logger.warning(f"Failed to load default {asset_type}: {str(e)}")
        return []

@main_bp.route('/donation-alert/settings', methods=['POST'])
@login_required
def update_alert_settings():
    """Update donation alert settings"""
    try:
        from app.models.donation_alert_settings import DonationAlertSettings
        from app.extensions import socketio
        
        data = request.get_json()
        current_app.logger.info(f"SETTINGS UPDATE: Received data: {data}")
        
        settings = DonationAlertSettings.get_or_create_for_user(current_user.id)
        current_app.logger.info(f"SETTINGS UPDATE: Current settings before update: {settings.to_dict()}")
        
        # Update settings with provided data
        settings.update_settings(**data)
        current_app.logger.info(f"SETTINGS UPDATE: Settings updated successfully")
        
        # Emit settings update to user's overlay
        socketio.emit('settings_updated', settings.to_dict(), room=f'user_{current_user.id}')
        
        return jsonify({'success': True, 'message': 'Settings updated successfully'})
        
    except Exception as e:
        current_app.logger.error(f"SETTINGS UPDATE: Error updating settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/donation-alert/upload-asset', methods=['POST'])
@login_required
def upload_alert_asset():
    """Upload asset for donation alerts"""
    try:
        from app.models.user_asset import UserAsset
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        asset_type = request.form.get('asset_type')
        
        if not file.filename:
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if asset_type not in ['gif', 'sound']:
            return jsonify({'success': False, 'error': 'Invalid asset type'}), 400
        
        # Validate file size
        file_content = file.read()
        max_size = 10 * 1024 * 1024 if asset_type == 'gif' else 5 * 1024 * 1024  # 10MB for gifs, 5MB for sounds
        
        if len(file_content) > max_size:
            return jsonify({'success': False, 'error': f'File too large. Maximum {max_size // 1024 // 1024}MB allowed'}), 400
        
        # Validate file type
        allowed_types = {
            'gif': ['image/gif', 'image/png', 'image/jpeg'],
            'sound': ['audio/mpeg', 'audio/wav', 'audio/ogg']
        }
        
        if file.content_type not in allowed_types[asset_type]:
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400
        
        # Create asset
        asset = UserAsset.create_asset(
            user_id=current_user.id,
            asset_type=asset_type,
            original_filename=file.filename,
            file_content=file_content,
            mime_type=file.content_type
        )
        
        return jsonify({
            'success': True, 
            'message': 'Asset uploaded successfully',
            'asset': asset.to_dict()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/donation-alert/delete-asset/<int:asset_id>', methods=['DELETE'])
@login_required
def delete_alert_asset(asset_id):
    """Delete user's asset"""
    try:
        from app.models.user_asset import UserAsset
        
        # Get asset and verify ownership
        asset = UserAsset.query.filter_by(id=asset_id, user_id=current_user.id).first()
        
        if not asset:
            return jsonify({'success': False, 'error': 'Asset not found'}), 404
        
        # Delete asset
        if asset.delete_asset():
            return jsonify({'success': True, 'message': 'Asset deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete asset'}), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# New API endpoints for multi-tab alert system

@main_bp.route('/donation-alert/configurations', methods=['GET'])
@login_required
def get_alert_configurations():
    """Get all alert configurations for the current user"""
    try:
        from app.models.alert_configuration import AlertConfiguration
        
        # Check if user has advanced tier
        subscription = current_user.get_current_subscription()
        has_advanced_tier = (subscription and 
                            subscription.feature_tier and 
                            subscription.feature_tier.value == 'advanced')
        
        if not has_advanced_tier:
            return jsonify({'success': False, 'error': 'Advanced tier required'}), 403
        
        configs = AlertConfiguration.get_user_configs(current_user.id)
        return jsonify({
            'success': True,
            'configurations': [config.to_dict() for config in configs]
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting alert configurations: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/donation-alert/configurations/<int:tab_number>', methods=['GET'])
@login_required
def get_alert_configuration(tab_number):
    """Get specific alert configuration by tab number"""
    try:
        from app.models.alert_configuration import AlertConfiguration
        
        config = AlertConfiguration.query.filter_by(
            user_id=current_user.id,
            tab_number=tab_number,
            is_active=True
        ).first()
        
        if not config:
            return jsonify({'success': False, 'error': 'Configuration not found'}), 404
        
        return jsonify({
            'success': True,
            'configuration': config.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting alert configuration: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/donation-alert/configurations/<int:tab_number>', methods=['POST'])
@login_required
def update_alert_configuration(tab_number):
    """Update or create alert configuration for specific tab"""
    try:
        from app.models.alert_configuration import AlertConfiguration
        from app.extensions import socketio
        
        # Check if user has advanced tier
        subscription = current_user.get_current_subscription()
        has_advanced_tier = (subscription and 
                            subscription.feature_tier and 
                            subscription.feature_tier.value == 'advanced')
        
        if not has_advanced_tier:
            return jsonify({'success': False, 'error': 'Advanced tier required'}), 403
        
        data = request.get_json()
        current_app.logger.info(f"SETTINGS UPDATE: Tab {tab_number} - Received data: {data}")
        
        # Validate minimum_amount for duplicates and provide suggestions
        if 'minimum_amount' in data:
            min_amount = data['minimum_amount']
            duplicate_config = AlertConfiguration.query.filter_by(
                user_id=current_user.id,
                is_active=True
            ).filter(
                AlertConfiguration.tab_number != tab_number,
                AlertConfiguration.minimum_amount == min_amount
            ).first()
            
            if duplicate_config:
                suggested_amount = AlertConfiguration.find_next_available_amount(
                    current_user.id, min_amount, exclude_tab_number=tab_number
                )
                return jsonify({
                    'success': False, 
                    'error': f'₮{min_amount} дүнг Алерт {duplicate_config.tab_number}-д ашигласан байна.',
                    'suggestion': float(suggested_amount),
                    'suggestion_message': f'Санал болгох: ₮{suggested_amount}'
                }), 400
        
        # Get or create configuration (check for ANY existing config, not just active ones)
        config = AlertConfiguration.query.filter_by(
            user_id=current_user.id,
            tab_number=tab_number
        ).first()
        
        if not config:
            config = AlertConfiguration.create_default_config(current_user.id, tab_number)
            db.session.add(config)
        else:
            # If config exists but was inactive, reactivate it
            config.is_active = True
        
        # Update configuration
        config.update_from_dict(data)
        db.session.commit()
        
        current_app.logger.info(f"SETTINGS UPDATE: Tab {tab_number} - Settings updated successfully")
        
        # Emit settings update to user's overlay
        socketio.emit('settings_updated', {
            'tab_number': tab_number,
            'config': config.to_dict()
        }, room=f'user_{current_user.id}')
        
        return jsonify({'success': True, 'message': 'Configuration updated successfully'})
        
    except Exception as e:
        current_app.logger.error(f"SETTINGS UPDATE: Error updating tab {tab_number}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/donation-alert/configurations/<int:tab_number>', methods=['DELETE'])
@login_required
def delete_alert_configuration(tab_number):
    """Delete alert configuration for specific tab"""
    try:
        from app.models.alert_configuration import AlertConfiguration
        
        # Check if user has advanced tier
        subscription = current_user.get_current_subscription()
        has_advanced_tier = (subscription and 
                            subscription.feature_tier and 
                            subscription.feature_tier.value == 'advanced')
        
        if not has_advanced_tier:
            return jsonify({'success': False, 'error': 'Advanced tier required'}), 403
        
        # Cannot delete tab 1
        if tab_number == 1:
            return jsonify({'success': False, 'error': 'Cannot delete default tab'}), 400
        
        config = AlertConfiguration.query.filter_by(
            user_id=current_user.id,
            tab_number=tab_number,
            is_active=True
        ).first()
        
        if not config:
            return jsonify({'success': False, 'error': 'Configuration not found'}), 404
        
        # Soft delete by setting is_active to False
        config.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Configuration deleted successfully'})
        
    except Exception as e:
        current_app.logger.error(f"Error deleting alert configuration: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/donation-alert/configurations/<int:tab_number>/duplicate', methods=['POST'])
@login_required
def duplicate_alert_configuration(tab_number):
    """Duplicate alert configuration to a new tab"""
    try:
        from app.models.alert_configuration import AlertConfiguration
        
        # Check if user has advanced tier
        subscription = current_user.get_current_subscription()
        has_advanced_tier = (subscription and 
                            subscription.feature_tier and 
                            subscription.feature_tier.value == 'advanced')
        
        if not has_advanced_tier:
            return jsonify({'success': False, 'error': 'Advanced tier required'}), 403
        
        data = request.get_json()
        new_tab_number = data.get('new_tab_number')
        
        if not new_tab_number:
            return jsonify({'success': False, 'error': 'New tab number required'}), 400
        
        # Check if new tab number already exists
        existing = AlertConfiguration.query.filter_by(
            user_id=current_user.id,
            tab_number=new_tab_number,
            is_active=True
        ).first()
        
        if existing:
            return jsonify({'success': False, 'error': 'Tab number already exists'}), 400
        
        # Get source configuration
        source_config = AlertConfiguration.query.filter_by(
            user_id=current_user.id,
            tab_number=tab_number,
            is_active=True
        ).first()
        
        if not source_config:
            return jsonify({'success': False, 'error': 'Source configuration not found'}), 404
        
        # Duplicate configuration
        new_config = source_config.duplicate_to_tab(new_tab_number)
        db.session.add(new_config)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Configuration duplicated successfully',
            'configuration': new_config.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error duplicating alert configuration: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/overlay/<token>')
def overlay(token):
    """Donation alert overlay page for OBS"""
    try:
        from app.models.user import User
        from app.models.donation_alert_settings import DonationAlertSettings
        from app.models.alert_configuration import AlertConfiguration
        
        # Get user by overlay token
        user = User.query.filter_by(overlay_token=token).first()
        if not user:
            current_app.logger.warning(f"Invalid overlay token attempted: {token}")
            abort(404)
        
        # Check if user has advanced tier
        subscription = user.get_current_subscription()
        has_advanced_tier = (subscription and 
                            subscription.feature_tier and 
                            subscription.feature_tier.value == 'advanced')
        
        if has_advanced_tier:
            # Get all alert configurations for advanced tier
            configs = AlertConfiguration.get_user_configs(user.id)
            # Use first config as default settings for template compatibility
            settings = configs[0] if configs else AlertConfiguration.create_default_config(user.id, 1)
            if not configs:
                db.session.add(settings)
                db.session.commit()
            
            return render_template('overlay.html', user=user, settings=settings, 
                                 alert_configurations=[config.to_dict() for config in configs], has_advanced_tier=True)
        else:
            # Use legacy settings for basic tier
            settings = DonationAlertSettings.get_or_create_for_user(user.id)
            return render_template('overlay.html', user=user, settings=settings, 
                                 has_advanced_tier=False)
        
    except Exception as e:
        current_app.logger.error(f"Error loading overlay for token {token}: {str(e)}")
        abort(404)

@main_bp.route('/donate/<username>')
def donate_page(username):
    """Public donation page for viewers to donate to a streamer"""
    try:
        from app.models.user import User
        from app.models.platform_connection import PlatformConnection
        from app.models.donation import Donation
        from app.models.user_sound_settings import UserSoundSettings
        from app.models.sound_effect import SoundEffect
        
        # Get user by username (from any platform connection)
        platform_connection = PlatformConnection.query.filter_by(platform_username=username).first()
        
        if not platform_connection:
            # Try to find by actual username field if it exists
            user = User.query.filter_by(username=username).first()
            if not user:
                current_app.logger.warning(f"User not found for donation page: {username}")
                abort(404)
        else:
            user = platform_connection.user
        
        # Get user's connected platforms for display
        connected_platforms = PlatformConnection.query.filter_by(user_id=user.id).all()
        
        # Get recent donations (last 10)
        recent_donations = Donation.query.filter_by(user_id=user.id, is_test=False)\
            .order_by(Donation.created_at.desc())\
            .limit(10)\
            .all()
        
        # Check streamer's subscription tier
        subscription = user.get_current_subscription()
        has_advanced_tier = (subscription and 
                            subscription.feature_tier and 
                            subscription.feature_tier.value == 'advanced')
        
        # Get sound effects settings and available sounds
        sound_settings = UserSoundSettings.query.filter_by(user_id=user.id).first()
        sound_effects_enabled = sound_settings and sound_settings.is_enabled if sound_settings else False
        sound_effect_price = float(sound_settings.price_per_sound) if sound_settings else 1000.0
        
        # Only allow sound effects if streamer has advanced tier AND has enabled them
        sound_effects_available = has_advanced_tier and sound_effects_enabled
        
        # Get available sound effects if available
        available_sounds = []
        sound_categories = []
        if sound_effects_available:
            available_sounds = SoundEffect.query.filter_by(is_active=True)\
                .order_by(SoundEffect.category, SoundEffect.name)\
                .all()
            
            # Get unique categories for filtering
            sound_categories = db.session.query(SoundEffect.category)\
                .filter_by(is_active=True)\
                .distinct()\
                .all()
            sound_categories = [cat[0] for cat in sound_categories if cat[0]]
        
        return render_template('donate.html', 
                             streamer=user, 
                             connected_platforms=connected_platforms,
                             recent_donations=recent_donations,
                             username=username,
                             sound_effects_enabled=sound_effects_enabled,
                             sound_effects_available=sound_effects_available,
                             has_advanced_tier=has_advanced_tier,
                             sound_effect_price=sound_effect_price,
                             available_sounds=available_sounds,
                             sound_categories=sound_categories)
        
    except Exception as e:
        current_app.logger.error(f"Error loading donation page for {username}: {str(e)}")
        abort(404)

@main_bp.route('/donate/<username>/submit', methods=['POST'])
def process_donation(username):
    """Process donation submission - create payment invoice"""
    try:
        from app.models.user import User
        from app.models.platform_connection import PlatformConnection
        from app.models.donation_payment import DonationPayment
        from flask_login import current_user
        
        # Get user by username
        platform_connection = PlatformConnection.query.filter_by(platform_username=username).first()
        
        if not platform_connection:
            user = User.query.filter_by(username=username).first()
            if not user:
                return jsonify({'success': False, 'error': 'Streamer not found'}), 404
        else:
            user = platform_connection.user
        
        # Check if streamer has bank account configured
        if not user.bank_iban or not user.bank_account_name:
            return jsonify({
                'success': False, 
                'error': 'Streamer has not configured bank account for donations'
            }), 400
        
        # Get donation data
        data = request.get_json()
        donor_name = data.get('donor_name', 'Anonymous')
        amount = float(data.get('amount', 0))
        message = data.get('message', '')
        
        # Determine donor info
        donor_platform = 'guest'
        donor_user_id = None
        
        if current_user.is_authenticated:
            donor_name = current_user.get_display_name()
            donor_platform = current_user.get_primary_platform() or 'authenticated'
            donor_user_id = current_user.id
        
        # Validate donation amount
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid donation amount'}), 400
        
        # Create donation payment and QPay invoice
        payment_result = DonationPayment.create_donation_payment(
            streamer_user_id=user.id,
            donor_name=donor_name,
            amount=amount,
            message=message,
            donor_platform=donor_platform,
            donor_user_id=donor_user_id
        )
        
        if not payment_result.get('success'):
            return jsonify({
                'success': False, 
                'error': payment_result.get('error', 'Failed to create payment')
            }), 500
        
        current_app.logger.info(f"Donation payment created for user {user.id}: {amount} MNT from {donor_name}")
        
        return jsonify({
            'success': True,
            'message': 'Payment created successfully',
            'payment_data': {
                'donation_payment_id': payment_result['donation_payment_id'],
                'invoice_id': payment_result['invoice_id'],
                'qr_code': payment_result['qr_code'],
                'qr_image': payment_result['qr_image'],
                'payment_url': payment_result['payment_url'],
                'app_links': payment_result['app_links'],
                'amount': payment_result['amount'],
                'currency': payment_result['currency'],
                'expires_at': payment_result['expires_at']
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error processing donation for {username}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to process donation'}), 500

@main_bp.route('/donate/<username>/sound-effect', methods=['POST'])
def process_sound_effect_purchase(username):
    """Process sound effect purchase - create payment invoice"""
    try:
        from app.models.user import User
        from app.models.platform_connection import PlatformConnection
        from app.models.donation_payment import DonationPayment
        from app.models.user_sound_settings import UserSoundSettings
        from app.models.sound_effect import SoundEffect
        from flask_login import current_user
        
        # Get user by username
        platform_connection = PlatformConnection.query.filter_by(platform_username=username).first()
        
        if not platform_connection:
            user = User.query.filter_by(username=username).first()
            if not user:
                return jsonify({'success': False, 'error': 'Streamer not found'}), 404
        else:
            user = platform_connection.user
        
        # Check if streamer has bank account configured
        if not user.bank_iban or not user.bank_account_name:
            return jsonify({
                'success': False, 
                'error': 'Streamer has not configured bank account for sound effects'
            }), 400
        
        # Check if sound effects are enabled for this streamer
        sound_settings = UserSoundSettings.query.filter_by(user_id=user.id).first()
        if not sound_settings or not sound_settings.is_enabled:
            return jsonify({
                'success': False, 
                'error': 'Sound effects are not enabled for this streamer'
            }), 400
        
        # Get sound effect purchase data
        data = request.get_json()
        donor_name = data.get('donor_name', 'Anonymous')
        sound_effect_id = data.get('sound_effect_id')
        
        if not sound_effect_id:
            return jsonify({'success': False, 'error': 'Sound effect not specified'}), 400
        
        # Validate sound effect exists and is active
        sound_effect = SoundEffect.query.filter_by(id=sound_effect_id, is_active=True).first()
        if not sound_effect:
            return jsonify({'success': False, 'error': 'Sound effect not found or inactive'}), 400
        
        # Use streamer's configured price
        amount = float(sound_settings.price_per_sound)
        
        # Determine donor info
        donor_platform = 'guest'
        donor_user_id = None
        
        if current_user.is_authenticated:
            donor_name = current_user.get_display_name()
            donor_platform = current_user.get_primary_platform() or 'authenticated'
            donor_user_id = current_user.id
        
        # Create sound effect payment and QPay invoice
        payment_result = DonationPayment.create_donation_payment(
            streamer_user_id=user.id,
            donor_name=donor_name,
            amount=amount,
            message='',  # Sound effects don't have messages
            donor_platform=donor_platform,
            donor_user_id=donor_user_id,
            payment_type='sound_effect',
            sound_effect_id=sound_effect_id
        )
        
        if not payment_result.get('success'):
            return jsonify({
                'success': False, 
                'error': payment_result.get('error', 'Failed to create payment')
            }), 500
        
        current_app.logger.info(f"Sound effect payment created for user {user.id}: {sound_effect.name} ({amount} MNT) from {donor_name}")
        
        return jsonify({
            'success': True,
            'message': 'Sound effect payment created successfully',
            'payment_data': {
                'donation_payment_id': payment_result['donation_payment_id'],
                'invoice_id': payment_result['invoice_id'],
                'qr_code': payment_result['qr_code'],
                'qr_image': payment_result['qr_image'],
                'payment_url': payment_result['payment_url'],
                'app_links': payment_result['app_links'],
                'amount': payment_result['amount'],
                'currency': payment_result['currency'],
                'expires_at': payment_result['expires_at'],
                'sound_effect_name': sound_effect.name
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error processing sound effect purchase for {username}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to process sound effect purchase'}), 500

@main_bp.route('/donation/callback', methods=['GET', 'POST'])
def donation_callback():
    """Handle QPay donation payment callback"""
    try:
        # Get webhook token from query parameters
        webhook_token = request.args.get('token')
        
        if not webhook_token:
            current_app.logger.error("Donation callback: No token provided")
            abort(400)
        
        # Get payment by webhook token
        from app.models.donation_payment import DonationPayment
        payment = DonationPayment.query.filter_by(webhook_token=webhook_token).first()
        
        if not payment:
            current_app.logger.error(f"Donation callback: Payment not found for token {webhook_token}")
            abort(404)
        
        # Parse callback data from different sources
        callback_data = {}
        
        if request.method == 'POST':
            # Try to get JSON data
            try:
                callback_data = request.get_json() or {}
            except Exception:
                # If JSON parsing fails, try form data
                callback_data = request.form.to_dict()
        else:
            # GET request - get data from query parameters
            callback_data = request.args.to_dict()
        
        # Log callback for debugging
        current_app.logger.info(f"QPay donation callback received for payment {payment.id}")
        current_app.logger.info(f"Method: {request.method}")
        current_app.logger.info(f"Headers: {dict(request.headers)}")
        current_app.logger.info(f"Callback data: {callback_data}")
        
        # Check payment status from various possible fields
        payment_status = (
            callback_data.get('invoice_status', '') or
            callback_data.get('status', '') or
            callback_data.get('payment_status', '') or
            callback_data.get('state', '')
        ).upper()
        
        current_app.logger.info(f"Payment status extracted: {payment_status}")
        
        # If no status in callback, check payment status via QPay API
        if not payment_status:
            current_app.logger.info("No payment status in callback, checking via QPay API")
            
            if payment.quickpay_invoice_id:
                from app.utils.quickpay_payment import quickpay_client
                
                try:
                    # Check payment status via QPay API
                    status_result = quickpay_client.check_payment_status(payment.quickpay_invoice_id)
                    current_app.logger.info(f"QPay API status check result: {status_result}")
                    
                    if status_result.get('success'):
                        api_data = status_result.get('data', {})
                        payment_status = api_data.get('invoice_status', api_data.get('status', '')).upper()
                        current_app.logger.info(f"Payment status from QPay API: {payment_status}")
                        
                        # Update callback_data with API response
                        callback_data.update(api_data)
                    else:
                        current_app.logger.error(f"Failed to check payment status via QPay API: {status_result}")
                        
                except Exception as api_error:
                    current_app.logger.error(f"Error checking payment status via QPay API: {str(api_error)}")
        
        # Process payment based on status
        if payment_status == 'PAID' or payment_status == 'SUCCESS':
            # Mark payment as paid and create donation record
            success = payment.mark_as_paid(callback_data.get('payment_method', 'QPay'))
            
            if success:
                current_app.logger.info(f"Donation payment {payment.id} marked as paid and donation created")
                
                # Emit real-time leaderboard update
                try:
                    from app.models.donor_leaderboard import DonorLeaderboard
                    from app.models.donor_leaderboard_settings import DonorLeaderboardSettings
                    
                    # Get streamer's leaderboard settings
                    settings = DonorLeaderboardSettings.query.filter_by(user_id=payment.streamer_user_id).first()
                    if settings and settings.is_enabled:
                        # Get updated top donors
                        top_donors = DonorLeaderboard.get_top_donors(payment.streamer_user_id, limit=settings.positions_count)
                        
                        # Emit leaderboard update
                        socketio.emit('leaderboard_updated', {
                            'settings': settings.to_dict(),
                            'top_donors': [donor.to_dict() for donor in top_donors],
                            'enabled': settings.is_enabled
                        }, room=f'leaderboard_{payment.streamer_user_id}')
                        
                        current_app.logger.info(f"Emitted leaderboard update for user {payment.streamer_user_id}")
                        
                except Exception as leaderboard_error:
                    current_app.logger.error(f"Error updating leaderboard after donation: {str(leaderboard_error)}")
                    
            else:
                current_app.logger.error(f"Failed to mark donation payment {payment.id} as paid")
            
        elif payment_status in ['FAILED', 'CANCELLED', 'CANCEL', 'ERROR']:
            payment.mark_as_failed(f"Callback status: {payment_status}")
            current_app.logger.info(f"Donation payment {payment.id} marked as failed: {payment_status}")
        else:
            current_app.logger.info(f"Payment status '{payment_status}' not recognized as final status - keeping as pending")
        
        return jsonify({'success': True, 'message': 'Callback processed'})
        
    except Exception as e:
        current_app.logger.error(f"Donation callback error: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Callback processing failed'}), 500

@main_bp.route('/donation/payment/<int:payment_id>/status')
def check_donation_payment_status(payment_id):
    """Check donation payment status"""
    try:
        from app.models.donation_payment import DonationPayment
        
        # Get payment record
        payment = DonationPayment.query.get(payment_id)
        
        if not payment:
            return jsonify({'success': False, 'error': 'Payment not found'}), 404
        
        # Check if payment is expired
        if payment.is_expired() and payment.status == 'pending':
            payment.mark_as_expired()
        
        # Return current status
        return jsonify({
            'success': True,
            'status': payment.status,
            'payment_id': payment.id,
            'amount': float(payment.amount),
            'currency': payment.currency,
            'donor_name': payment.donor_name,
            'message': payment.message,
            'created_at': payment.created_at.isoformat(),
            'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
            'expires_at': payment.expires_at.isoformat() if payment.expires_at else None
        })
        
    except Exception as e:
        current_app.logger.error(f"Donation payment status check error: {str(e)}")
        return jsonify({'success': False, 'error': 'Status check failed'}), 500

@main_bp.route('/donations')
@login_required
def donations_history():
    """View donation history for the current user"""
    try:
        from app.models.donation import Donation
        from app.models.platform_connection import PlatformConnection
        
        # Ensure donations table exists
        try:
            db.create_all()
        except Exception as table_error:
            current_app.logger.warning(f"Table creation warning: {str(table_error)}")
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Validate per_page
        if per_page not in [20, 50, 100]:
            per_page = 20
        
        # Get donations with pagination
        donations = Donation.get_user_donations(
            user_id=current_user.id,
            page=page,
            per_page=per_page,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Get donation statistics
        stats = Donation.get_user_donation_stats(current_user.id)
        
        # Get user's primary platform for donation URL
        primary_platform = PlatformConnection.query.filter_by(
            user_id=current_user.id,
            is_primary=True
        ).first()
        
        donation_url = None
        if primary_platform:
            donation_url = url_for('main.donate_page', username=primary_platform.platform_username, _external=True)
        
        # Build query string for pagination links
        from urllib.parse import urlencode
        query_params = {}
        if search:
            query_params['search'] = search
        if sort_by != 'created_at':
            query_params['sort_by'] = sort_by
        if sort_order != 'desc':
            query_params['sort_order'] = sort_order
        if per_page != 20:
            query_params['per_page'] = per_page
        
        query_string = urlencode(query_params)
        
        return render_template('donations_history.html',
                             donations=donations,
                             stats=stats,
                             donation_url=donation_url,
                             search=search,
                             sort_by=sort_by,
                             sort_order=sort_order,
                             per_page=per_page,
                             query_string=query_string)
        
    except Exception as e:
        current_app.logger.error(f"Error loading donations history: {str(e)}")
        flash('Хандивын түүх ачаалахад алдаа гарлаа.', 'error')
        return redirect(url_for('main.dashboard'))

@main_bp.route('/api/donations/history')
@login_required
def donations_history_api():
    """AJAX API endpoint for donation history table"""
    try:
        from app.models.donation import Donation
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Validate per_page
        if per_page not in [20, 50, 100]:
            per_page = 20
        
        # Get donations with pagination
        donations = Donation.get_user_donations(
            user_id=current_user.id,
            page=page,
            per_page=per_page,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Convert donations to JSON-serializable format
        donations_data = []
        for donation in donations.items:
            donations_data.append({
                'id': donation.id,
                'donor_name': donation.donor_name,
                'amount': float(donation.amount),
                'message': donation.message,
                'platform': donation.platform,
                'created_at': donation.created_at.strftime('%Y-%m-%d %H:%M'),
                'created_at_display': {
                    'date': donation.created_at.strftime('%Y-%m-%d'),
                    'time': donation.created_at.strftime('%H:%M')
                }
            })
        
        return jsonify({
            'success': True,
            'donations': donations_data,
            'pagination': {
                'page': donations.page,
                'pages': donations.pages,
                'total': donations.total,
                'per_page': donations.per_page,
                'has_prev': donations.has_prev,
                'has_next': donations.has_next,
                'prev_num': donations.prev_num,
                'next_num': donations.next_num
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error loading donations history API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/donations/analytics')
@login_required
def donations_analytics():
    """Get donation analytics data for charts"""
    try:
        from app.models.donation import Donation
        from app.models.donation_payment import DonationPayment
        from datetime import datetime, timedelta
        from sqlalchemy import func, extract, text
        
        # Get date range from query parameters
        days = request.args.get('days', 30, type=int)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        current_app.logger.info(f"Analytics request for user {current_user.id}, days: {days}")
        
        # Check if Donation table exists and has data
        try:
            donation_count = db.session.query(func.count(Donation.id)).filter(
                Donation.user_id == current_user.id
            ).scalar()
            current_app.logger.info(f"Total donations for user: {donation_count}")
        except Exception as e:
            current_app.logger.error(f"Error accessing Donation table: {str(e)}")
            # Return empty data structure if table doesn't exist or has issues
            return jsonify({
                'success': True,
                'data': {
                    'revenue_timeline': [],
                    'hourly_pattern': [],
                    'weekly_pattern': [],
                    'platform_breakdown': [],
                    'top_donors': [],
                    'amount_distribution': [
                        {'range': '0-1K', 'count': 0},
                        {'range': '1K-5K', 'count': 0},
                        {'range': '5K-10K', 'count': 0},
                        {'range': '10K-25K', 'count': 0},
                        {'range': '25K-50K', 'count': 0},
                        {'range': '50K-100K', 'count': 0},
                        {'range': '100K+', 'count': 0}
                    ],
                    'payment_status': []
                },
                'period': f'{days} өдөр',
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            })
        
        # Revenue over time (daily) - Use DATE function for MySQL compatibility
        try:
            daily_revenue = db.session.query(
                func.date(Donation.created_at).label('date'),
                func.sum(Donation.amount).label('total_amount'),
                func.count(Donation.id).label('count')
            ).filter(
                Donation.user_id == current_user.id,
                Donation.created_at >= start_date,
                Donation.created_at <= end_date
            ).group_by(func.date(Donation.created_at)).order_by(func.date(Donation.created_at)).all()
        except Exception as e:
            current_app.logger.error(f"Error in daily revenue query: {str(e)}")
            daily_revenue = []
        
        # Donations by hour of day - Use HOUR function for MySQL
        try:
            hourly_donations = db.session.query(
                func.hour(Donation.created_at).label('hour'),
                func.count(Donation.id).label('count'),
                func.sum(Donation.amount).label('total_amount')
            ).filter(
                Donation.user_id == current_user.id,
                Donation.created_at >= start_date
            ).group_by(func.hour(Donation.created_at)).order_by(func.hour(Donation.created_at)).all()
        except Exception as e:
            current_app.logger.error(f"Error in hourly donations query: {str(e)}")
            hourly_donations = []
        
        # Donations by day of week - Use DAYOFWEEK function for MySQL
        try:
            daily_donations = db.session.query(
                func.dayofweek(Donation.created_at).label('day_of_week'),
                func.count(Donation.id).label('count'),
                func.sum(Donation.amount).label('total_amount')
            ).filter(
                Donation.user_id == current_user.id,
                Donation.created_at >= start_date
            ).group_by(func.dayofweek(Donation.created_at)).order_by(func.dayofweek(Donation.created_at)).all()
        except Exception as e:
            current_app.logger.error(f"Error in daily donations query: {str(e)}")
            daily_donations = []
        
        # Platform breakdown
        try:
            platform_stats = db.session.query(
                Donation.platform,
                func.count(Donation.id).label('count'),
                func.sum(Donation.amount).label('total_amount')
            ).filter(
                Donation.user_id == current_user.id,
                Donation.created_at >= start_date
            ).group_by(Donation.platform).all()
        except Exception as e:
            current_app.logger.error(f"Error in platform stats query: {str(e)}")
            platform_stats = []
        
        # Top donors
        try:
            top_donors = db.session.query(
                Donation.donor_name,
                func.count(Donation.id).label('donation_count'),
                func.sum(Donation.amount).label('total_amount')
            ).filter(
                Donation.user_id == current_user.id,
                Donation.created_at >= start_date
            ).group_by(Donation.donor_name).order_by(func.sum(Donation.amount).desc()).limit(10).all()
        except Exception as e:
            current_app.logger.error(f"Error in top donors query: {str(e)}")
            top_donors = []
        
        # Donation amount distribution (histogram)
        amount_ranges = [
            (0, 1000, '0-1K'),
            (1000, 5000, '1K-5K'),
            (5000, 10000, '5K-10K'),
            (10000, 25000, '10K-25K'),
            (25000, 50000, '25K-50K'),
            (50000, 100000, '50K-100K'),
            (100000, 999999999, '100K+')
        ]
        
        amount_distribution = []
        for min_amount, max_amount, label in amount_ranges:
            try:
                count = db.session.query(func.count(Donation.id)).filter(
                    Donation.user_id == current_user.id,
                    Donation.amount >= min_amount,
                    Donation.amount < max_amount,
                    Donation.created_at >= start_date
                ).scalar()
                amount_distribution.append({
                    'range': label,
                    'count': count or 0
                })
            except Exception as e:
                current_app.logger.error(f"Error in amount distribution query for {label}: {str(e)}")
                amount_distribution.append({
                    'range': label,
                    'count': 0
                })
        
        # Payment status breakdown (from DonationPayment)
        try:
            payment_status = db.session.query(
                DonationPayment.status,
                func.count(DonationPayment.id).label('count')
            ).filter(
                DonationPayment.streamer_user_id == current_user.id,
                DonationPayment.created_at >= start_date
            ).group_by(DonationPayment.status).all()
        except Exception as e:
            current_app.logger.error(f"Error in payment status query: {str(e)}")
            payment_status = []
        
        # Format data for frontend
        analytics_data = {
            'revenue_timeline': [
                {
                    'date': item.date.isoformat() if hasattr(item.date, 'isoformat') else str(item.date),
                    'amount': float(item.total_amount or 0),
                    'count': item.count
                } for item in daily_revenue
            ],
            'hourly_pattern': [
                {
                    'hour': int(item.hour),
                    'count': item.count,
                    'amount': float(item.total_amount or 0)
                } for item in hourly_donations
            ],
            'weekly_pattern': [
                {
                    'day': int(item.day_of_week) - 1,  # MySQL DAYOFWEEK starts from 1 (Sunday), adjust to 0-6
                    'day_name': ['Ням', 'Даваа', 'Мягмар', 'Лхагва', 'Пүрэв', 'Баасан', 'Бямба'][int(item.day_of_week) - 1],
                    'count': item.count,
                    'amount': float(item.total_amount or 0)
                } for item in daily_donations
            ],
            'platform_breakdown': [
                {
                    'platform': item.platform or 'guest',
                    'count': item.count,
                    'amount': float(item.total_amount or 0)
                } for item in platform_stats
            ],
            'top_donors': [
                {
                    'name': item.donor_name,
                    'count': item.donation_count,
                    'amount': float(item.total_amount)
                } for item in top_donors
            ],
            'amount_distribution': amount_distribution,
            'payment_status': [
                {
                    'status': item.status,
                    'count': item.count
                } for item in payment_status
            ]
        }
        
        current_app.logger.info(f"Analytics data prepared successfully")
        
        return jsonify({
            'success': True,
            'data': analytics_data,
            'period': f'{days} өдөр',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting donation analytics: {str(e)}")
        import traceback
        current_app.logger.error(f"Analytics error traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/donations/summary')
@login_required  
def donations_summary():
    """Get donation summary statistics"""
    try:
        from app.models.donation import Donation
        from app.models.donation_payment import DonationPayment
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # Get date range
        days = request.args.get('days', 30, type=int)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        current_app.logger.info(f"Summary request for user {current_user.id}, days: {days}")
        
        # Check if tables exist
        try:
            # Current period stats
            current_stats = db.session.query(
                func.count(Donation.id).label('total_donations'),
                func.sum(Donation.amount).label('total_amount'),
                func.avg(Donation.amount).label('average_amount'),
                func.max(Donation.amount).label('max_amount')
            ).filter(
                Donation.user_id == current_user.id,
                Donation.created_at >= start_date
            ).first()
            
            # Previous period for comparison
            prev_start = start_date - timedelta(days=days)
            prev_stats = db.session.query(
                func.count(Donation.id).label('total_donations'),
                func.sum(Donation.amount).label('total_amount')
            ).filter(
                Donation.user_id == current_user.id,
                Donation.created_at >= prev_start,
                Donation.created_at < start_date
            ).first()
            
        except Exception as e:
            current_app.logger.error(f"Error accessing Donation table for summary: {str(e)}")
            # Return default values if table access fails
            return jsonify({
                'success': True,
                'summary': {
                    'total_donations': 0,
                    'total_amount': 0.0,
                    'average_amount': 0.0,
                    'max_amount': 0.0,
                    'donation_growth': 0.0,
                    'revenue_growth': 0.0,
                    'conversion_rate': 0.0,
                    'total_payment_attempts': 0,
                    'successful_payments': 0,
                    'period_days': days
                }
            })
        
        # Calculate growth percentages
        donation_growth = 0
        revenue_growth = 0
        
        if prev_stats and prev_stats.total_donations and prev_stats.total_donations > 0:
            donation_growth = ((current_stats.total_donations - prev_stats.total_donations) / prev_stats.total_donations) * 100
        
        if prev_stats and prev_stats.total_amount and prev_stats.total_amount > 0:
            revenue_growth = ((float(current_stats.total_amount or 0) - float(prev_stats.total_amount or 0)) / float(prev_stats.total_amount)) * 100
        
        # Payment conversion rate
        try:
            total_payment_attempts = db.session.query(func.count(DonationPayment.id)).filter(
                DonationPayment.streamer_user_id == current_user.id,
                DonationPayment.created_at >= start_date
            ).scalar()
            
            successful_payments = db.session.query(func.count(DonationPayment.id)).filter(
                DonationPayment.streamer_user_id == current_user.id,
                DonationPayment.status == 'paid',
                DonationPayment.created_at >= start_date
            ).scalar()
        except Exception as e:
            current_app.logger.error(f"Error accessing DonationPayment table: {str(e)}")
            total_payment_attempts = 0
            successful_payments = 0
        
        conversion_rate = 0
        if total_payment_attempts and total_payment_attempts > 0:
            conversion_rate = (successful_payments / total_payment_attempts) * 100
        
        return jsonify({
            'success': True,
            'summary': {
                'total_donations': current_stats.total_donations or 0,
                'total_amount': float(current_stats.total_amount or 0),
                'average_amount': float(current_stats.average_amount or 0),
                'max_amount': float(current_stats.max_amount or 0),
                'donation_growth': round(donation_growth, 1),
                'revenue_growth': round(revenue_growth, 1),
                'conversion_rate': round(conversion_rate, 1),
                'total_payment_attempts': total_payment_attempts or 0,
                'successful_payments': successful_payments or 0,
                'period_days': days
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting donation summary: {str(e)}")
        import traceback
        current_app.logger.error(f"Summary error traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# SocketIO Event Handlers
from app.extensions import socketio
from flask_socketio import emit, join_room, leave_room


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")


@socketio.on('join')
def handle_join(data):
    """Handle client joining a room"""
    room = data.get('room')
    if room:
        join_room(room)
        current_app.logger.info(f"SOCKET: Client {request.sid} joined room: {room}")
        # Send acknowledgment back to client
        emit('room_joined', {'room': room, 'status': 'success'})

@socketio.on('join_donation_room')
def handle_join_donation_room(data):
    """Handle client joining a donation feed room"""
    streamer_id = data.get('streamer_id')
    room_type = data.get('room_type', 'donation_feed')
    
    if streamer_id and room_type == 'donation_feed':
        room = f"donation_feed_{streamer_id}"
        join_room(room)
        current_app.logger.info(f"SOCKET: Client {request.sid} joined donation feed room: {room}")
        # Send acknowledgment back to client
        emit('room_joined', {'room': room, 'status': 'success', 'type': 'donation_feed'})

@socketio.on('join_goal_room')
def handle_join_goal_room(data):
    """Handle client joining a goal overlay room"""
    streamer_id = data.get('streamer_id')
    room_type = data.get('room_type', 'goal_overlay')
    
    if streamer_id and room_type == 'goal_overlay':
        room = f"goal_overlay_{streamer_id}"
        join_room(room)
        current_app.logger.info(f"SOCKET: Client {request.sid} joined goal overlay room: {room}")
        # Send acknowledgment back to client
        emit('room_joined', {'room': room, 'status': 'success', 'type': 'goal_overlay'})


@socketio.on('test_alert')
def handle_test_alert(data):
    """Handle test alert emission from settings page"""
    current_app.logger.info(f"SOCKET: Received test alert: {data}")
    
    # Get user ID from the data payload instead of Flask-Login context
    user_id = data.get('user_id')
    if not user_id:
        current_app.logger.error("SOCKET: No user_id provided in test alert data")
        return
    
    user_room = f"user_{user_id}"
    current_app.logger.info(f"SOCKET: Emitting test alert to room: {user_room}")
    current_app.logger.info(f"SOCKET: Test alert data includes message: '{data.get('message', 'NO MESSAGE')}'")
    
    # Test alerts don't include TTS - only visual/audio alerts
    current_app.logger.info("SOCKET: Test alert - TTS disabled for tests")
    
    # Emit to the user's overlay room
    current_app.logger.info(f"SOCKET: About to emit data to overlay: {data}")
    emit('test_alert', data, room=user_room)
    current_app.logger.info("SOCKET: Test alert emitted successfully")


@socketio.on('donation_alert')
def handle_donation_alert(data):
    """Handle real donation alert emission (with TTS support)"""
    current_app.logger.info(f"SOCKET: Received real donation alert: {data}")
    
    # Get user ID from the data payload
    user_id = data.get('user_id')
    if not user_id:
        current_app.logger.error("SOCKET: No user_id provided in donation alert data")
        return
    
    user_room = f"user_{user_id}"
    current_app.logger.info(f"SOCKET: Emitting donation alert to room: {user_room}")
    
    # Get user's TTS settings for real donations
    from app.models.donation_alert_settings import DonationAlertSettings
    settings = DonationAlertSettings.get_or_create_for_user(user_id)
    
    # Generate TTS audio if enabled and conditions are met (only for real donations)
    tts_audio_url = None
    if (settings.tts_enabled and 
        data.get('amount', 0) >= settings.tts_minimum_amount and 
        data.get('message')):
        
        current_app.logger.info("SOCKET: Generating TTS audio for real donation")
        tts_audio_url = generate_tts_audio(
            user_id,
            data.get('message'),
            settings.tts_voice,
            settings.tts_speed,
            settings.tts_pitch,
            'donation'
        )
        
        if tts_audio_url:
            current_app.logger.info(f"SOCKET: TTS audio generated: {tts_audio_url}")
            data['tts_audio_url'] = tts_audio_url
        else:
            current_app.logger.warning("SOCKET: TTS audio generation failed")
    
    # Emit to the user's overlay room
    current_app.logger.info(f"SOCKET: About to emit donation data to overlay: {data}")
    emit('donation_alert', data, room=user_room)
    current_app.logger.info("SOCKET: Real donation alert emitted successfully")


# Marathon Routes
@main_bp.route('/marathon')
@login_required
def marathon():
    """Marathon settings page"""
    from app.models.marathon import Marathon
    
    # Get or create marathon settings for user
    marathon = Marathon.get_or_create_for_user(current_user.id)
    
    # Update current remaining time if marathon is running
    if marathon.started_at and not marathon.is_paused:
        marathon.get_current_remaining_time()
    
    return render_template('marathon.html', marathon=marathon)

@main_bp.route('/marathon', methods=['POST'])
@login_required
def update_marathon_settings():
    """Update marathon settings"""
    try:
        from app.models.marathon import Marathon
        
        # Get or create marathon settings for user
        marathon = Marathon.get_or_create_for_user(current_user.id)
        current_app.logger.info(f"MARATHON SAVE: User {current_user.id}, Marathon ID {marathon.id}, Current remaining_time: {marathon.remaining_time_minutes}:{marathon.remaining_time_seconds}")
        
        # Update current remaining time if marathon is running (to ensure accurate time before saving)
        if marathon.started_at and not marathon.is_paused:
            marathon.get_current_remaining_time()
            current_app.logger.info(f"MARATHON SAVE: After time update, remaining_time: {marathon.remaining_time_minutes}:{marathon.remaining_time_seconds}")
        
        # Update basic settings
        if request.form.get('minute_price'):
            marathon.minute_price = float(request.form.get('minute_price'))
        
        # Update initial time if provided
        initial_days = int(request.form.get('initial_days', 0))
        initial_hours = int(request.form.get('initial_hours', 0))
        initial_minutes = int(request.form.get('initial_minutes', 0))
        
        # Calculate new total time
        new_total_minutes = (initial_days * 24 * 60) + (initial_hours * 60) + initial_minutes
        
        # Only update initial time if it actually changed and marathon is not running
        if (not marathon.started_at or marathon.is_paused) and new_total_minutes != marathon.initial_time_minutes:
            marathon.set_initial_time(initial_days, initial_hours, initial_minutes, auto_commit=False)
        
        # Update timer font settings
        marathon.timer_font_size = int(request.form.get('timer_font_size', marathon.timer_font_size))
        marathon.timer_font_weight = int(request.form.get('timer_font_weight', marathon.timer_font_weight))
        marathon.timer_font_color = request.form.get('timer_font_color', marathon.timer_font_color)
        marathon.timer_animation = request.form.get('timer_animation', marathon.timer_animation)
        
        # Update notification font settings
        marathon.notification_font_size = int(request.form.get('notification_font_size', marathon.notification_font_size))
        marathon.notification_font_weight = int(request.form.get('notification_font_weight', marathon.notification_font_weight))
        marathon.notification_font_color = request.form.get('notification_font_color', marathon.notification_font_color)
        
        db.session.commit()
        current_app.logger.info(f"MARATHON SAVE: Final remaining_time before WebSocket: {marathon.remaining_time_minutes}:{marathon.remaining_time_seconds}")
        
        # Send real-time update
        marathon._send_marathon_update()
        
        return jsonify({
            'success': True,
            'marathon': marathon.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error updating marathon settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/marathon-overlay/<token>')
def marathon_overlay(token):
    """Marathon overlay page for streamers using secure token"""
    from app.models.marathon import Marathon
    
    # Find marathon by token
    marathon = Marathon.get_by_overlay_token(token)
    if not marathon:
        abort(404)
    
    return render_template('marathon_overlay.html', marathon=marathon)

@main_bp.route('/api/marathon/data')
@marathon_rate_limit(max_calls=120, window_minutes=1)
def marathon_data():
    """Get marathon data for current user or by token"""
    try:
        from app.models.marathon import Marathon
        
        # Check if token is provided (for overlay)
        token = request.args.get('token')
        if token:
            marathon = Marathon.get_by_overlay_token(token)
            if not marathon:
                return jsonify({'success': False, 'error': 'Invalid token'}), 404
        else:
            # Use current user if authenticated
            if current_user.is_authenticated:
                marathon = Marathon.get_or_create_for_user(current_user.id)
            else:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Update current remaining time if marathon is running
        if marathon.started_at and not marathon.is_paused:
            marathon.get_current_remaining_time()
        
        return jsonify({
            'success': True,
            'marathon': marathon.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting marathon data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/marathon/update-countdown', methods=['POST'])
@marathon_rate_limit(max_calls=30, window_minutes=1)
def update_marathon_countdown():
    """Update marathon countdown state (minutes and seconds)"""
    try:
        from app.models.marathon import Marathon
        
        data = request.get_json()
        token = data.get('token')
        minutes = data.get('minutes', 0)
        seconds = data.get('seconds', 0)
        
        # Check if token is provided (for overlay) or use authenticated user
        if token:
            marathon = Marathon.get_by_overlay_token(token)
            if not marathon:
                return jsonify({'success': False, 'error': 'Invalid token'}), 404
        elif current_user.is_authenticated:
            marathon = Marathon.get_or_create_for_user(current_user.id)
        else:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Update countdown state
        marathon.update_countdown_state(minutes, seconds)
        
        return jsonify({
            'success': True,
            'marathon': marathon.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error updating marathon countdown: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/marathon/adjust-time', methods=['POST'])
@login_required
def adjust_marathon_time():
    """Manually adjust marathon time"""
    try:
        from app.models.marathon import Marathon
        
        data = request.get_json()
        minutes = data.get('minutes', 0)
        
        if not minutes:
            return jsonify({'success': False, 'error': 'No minutes specified'}), 400
        
        # Get marathon settings
        marathon = Marathon.get_or_create_for_user(current_user.id)
        
        # Add time (positive or negative)
        marathon.add_time_minutes(minutes, source='manual')
        
        return jsonify({
            'success': True,
            'marathon': marathon.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error adjusting marathon time: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/marathon/start', methods=['POST'])
@login_required
def start_marathon():
    """Start marathon countdown"""
    try:
        from app.models.marathon import Marathon
        
        # Get marathon settings
        marathon = Marathon.get_or_create_for_user(current_user.id)
        
        # Start countdown
        marathon.start_countdown()
        
        return jsonify({
            'success': True,
            'marathon': marathon.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error starting marathon: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/marathon/request-save-state', methods=['POST'])
@login_required
def request_save_state():
    """Request overlay to save its current countdown state"""
    try:
        from app.extensions import socketio
        
        # Send save state request to overlay room
        marathon_room = f"marathon_overlay_{current_user.id}"
        current_app.logger.info(f"SAVE STATE: Sending request to room {marathon_room}")
        socketio.emit('request_save_state', {'user_id': current_user.id}, room=marathon_room)
        
        return jsonify({'success': True})
        
    except Exception as e:
        current_app.logger.error(f"Error requesting save state: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/marathon/pause', methods=['POST'])
@login_required
def pause_marathon():
    """Pause marathon countdown"""
    try:
        from app.models.marathon import Marathon
        
        # Get marathon settings
        marathon = Marathon.get_or_create_for_user(current_user.id)
        
        # Get current time state from client if provided (for compatibility)
        data = request.get_json() or {}
        current_minutes = data.get('current_minutes')
        current_seconds = data.get('current_seconds')
        
        # Update marathon state with client's current time before pausing (if provided)
        if current_minutes is not None and current_seconds is not None:
            marathon.remaining_time_minutes = max(0, int(current_minutes))
            marathon.remaining_time_seconds = max(0, min(59, int(current_seconds)))
            current_app.logger.info(f"PAUSE: Updated marathon time from client - minutes: {marathon.remaining_time_minutes}, seconds: {marathon.remaining_time_seconds}")
        else:
            current_app.logger.info(f"PAUSE: Using existing marathon time - minutes: {marathon.remaining_time_minutes}, seconds: {marathon.remaining_time_seconds}")
        
        # Pause countdown
        marathon.pause_countdown()
        
        return jsonify({
            'success': True,
            'marathon': marathon.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error pausing marathon: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/marathon/reset', methods=['POST'])
@login_required
def reset_marathon():
    """Reset marathon to initial state"""
    try:
        from app.models.marathon import Marathon
        
        # Get marathon settings
        marathon = Marathon.get_or_create_for_user(current_user.id)
        
        # Reset marathon
        marathon.reset_marathon()
        
        return jsonify({
            'success': True,
            'marathon': marathon.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error resetting marathon: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/marathon/auto-reset', methods=['POST'])
@marathon_rate_limit(max_calls=10, window_minutes=1)
def auto_reset_marathon():
    """Auto-reset marathon when timer reaches 0 (token-based for overlay)"""
    try:
        from app.models.marathon import Marathon
        
        data = request.get_json()
        if not data or 'token' not in data:
            return jsonify({'success': False, 'error': 'Token required'}), 400
        
        token = data['token']
        
        # Get marathon by token
        marathon = Marathon.get_by_overlay_token(token)
        if not marathon:
            return jsonify({'success': False, 'error': 'Invalid token'}), 404
        
        current_app.logger.info(f"AUTO-RESET API: Marathon {marathon.id} auto-reset triggered by overlay")
        current_app.logger.info(f"AUTO-RESET API: Marathon state before reset - running: {marathon.started_at is not None and not marathon.is_paused}")
        
        # Auto-reset marathon with initial time set to 0
        marathon.auto_reset_marathon()
        
        current_app.logger.info(f"AUTO-RESET API: Marathon {marathon.id} auto-reset completed - now inactive")
        
        return jsonify({
            'success': True,
            'marathon': marathon.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error auto-resetting marathon: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/marathon/set-initial-time', methods=['POST'])
@login_required
def set_marathon_initial_time():
    """Set marathon initial time"""
    try:
        from app.models.marathon import Marathon
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        days = int(data.get('days', 0))
        hours = int(data.get('hours', 0))
        minutes = int(data.get('minutes', 0))
        
        # Validate input
        if days < 0 or hours < 0 or minutes < 0:
            return jsonify({'success': False, 'error': 'Time values cannot be negative'}), 400
        
        if hours > 23 or minutes > 59:
            return jsonify({'success': False, 'error': 'Invalid time format'}), 400
        
        # Get marathon settings
        marathon = Marathon.get_or_create_for_user(current_user.id)
        
        # Set initial time
        marathon.set_initial_time(days, hours, minutes)
        
        current_app.logger.info(f"MARATHON: Set initial time for user {current_user.id}: {days}d {hours}h {minutes}m")
        
        return jsonify({
            'success': True,
            'marathon': marathon.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error setting marathon initial time: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Marathon SocketIO handlers
# Sound Effects Routes
@main_bp.route('/sound-effects')
@login_required
def sound_effects_settings():
    """Sound Effects settings page - Advanced tier only"""
    from app.models.user_sound_settings import UserSoundSettings
    from app.models.sound_effect import SoundEffect
    
    # Check if user has advanced tier subscription
    subscription = current_user.get_current_subscription()
    has_advanced_tier = (subscription and 
                        subscription.feature_tier and 
                        subscription.feature_tier.value == 'advanced')
    
    if not has_advanced_tier:
        flash('Дууны эффект нь дэвшилтэт тарифын онцлог юм', 'warning')
        return redirect(url_for('main.index'))
    
    # Get or create sound settings for user
    settings = UserSoundSettings.get_or_create_for_user(current_user.id)
    
    # Get available sound effects
    sound_effects = SoundEffect.query.filter_by(is_active=True).order_by(SoundEffect.name).all()
    
    # Ensure user has an overlay token
    overlay_token = current_user.get_overlay_token()
    
    return render_template('sound_effects.html', 
                         settings=settings,
                         sound_effects=sound_effects,
                         overlay_token=overlay_token)

@main_bp.route('/sound-effects/settings', methods=['POST'])
@login_required
def update_sound_effects_settings():
    """Update sound effects settings"""
    try:
        from app.models.user_sound_settings import UserSoundSettings
        
        # Check if user has advanced tier subscription
        subscription = current_user.get_current_subscription()
        has_advanced_tier = (subscription and 
                            subscription.feature_tier and 
                            subscription.feature_tier.value == 'advanced')
        
        if not has_advanced_tier:
            return jsonify({'success': False, 'error': 'Дэвшилтэт тариф шаардлагатай'}), 403
        
        # Get or create sound settings for user
        settings = UserSoundSettings.get_or_create_for_user(current_user.id)
        
        # Update settings
        is_enabled = request.form.get('is_enabled') == 'on'
        price_per_sound = None
        volume_level = None
        
        # Update price if provided and valid
        if request.form.get('price_per_sound'):
            price = float(request.form.get('price_per_sound'))
            if price >= 100:  # Minimum 100 MNT
                price_per_sound = price
            else:
                return jsonify({'success': False, 'error': 'Хамгийн бага үнэ 100₮'}), 400
        
        # Update volume level if provided and valid
        if request.form.get('volume_level'):
            volume = int(request.form.get('volume_level'))
            if 0 <= volume <= 100:
                volume_level = volume
            else:
                return jsonify({'success': False, 'error': 'Дууны түвшин 0-100% хооронд байна'}), 400
        
        # Apply updates using the model method
        settings.update_settings(
            is_enabled=is_enabled,
            price_per_sound=price_per_sound,
            volume_level=volume_level
        )
        
        current_app.logger.info(f"Sound effects settings updated for user {current_user.id}")
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating sound effects settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/sound-effects/test', methods=['POST'])
@login_required  
def test_random_sound():
    """Send random sound effect to overlay for testing"""
    try:
        from app.models.sound_effect import SoundEffect
        from app.models.user_sound_settings import UserSoundSettings
        import random
        
        # Check if user has advanced tier subscription
        subscription = current_user.get_current_subscription()
        has_advanced_tier = (subscription and 
                            subscription.feature_tier and 
                            subscription.feature_tier.value == 'advanced')
        
        if not has_advanced_tier:
            return jsonify({'success': False, 'error': 'Дэвшилтэт тариф шаардлагатай'}), 403
        
        # Check if sound effects are enabled
        settings = UserSoundSettings.get_or_create_for_user(current_user.id)
        if not settings.is_enabled:
            return jsonify({'success': False, 'error': 'Дууны эффектүүд идэвхгүй байна'}), 400
        
        # Get random sound effect
        sound_effects = SoundEffect.query.filter_by(is_active=True).all()
        if not sound_effects:
            return jsonify({'success': False, 'error': 'Дууны эффект олдсонгүй'}), 404
        
        # Select random sound from first 5 (as per plan)
        available_sounds = sound_effects[:5] if len(sound_effects) > 5 else sound_effects
        random_sound = random.choice(available_sounds)
        
        # Get user's sound settings for volume level
        from app.models.user_sound_settings import UserSoundSettings
        try:
            user_settings = UserSoundSettings.get_or_create_for_user(current_user.id)
            volume_level = user_settings.volume_level if user_settings.volume_level is not None else 70
        except Exception as e:
            current_app.logger.warning(f"Test sound: Failed to get volume settings for user {current_user.id}, using default: {str(e)}")
            volume_level = 70
        
        # Prepare test sound data
        test_sound_data = {
            'type': 'sound_effect_test',
            'id': f'test_{uuid.uuid4().hex[:8]}',
            'sound_effect_id': random_sound.id,
            'sound_filename': random_sound.filename,
            'sound_name': random_sound.name,
            'duration_seconds': float(random_sound.duration_seconds),
            'donor_name': 'Тест',
            'amount': 0,
            'created_at': datetime.utcnow().isoformat(),
            'file_url': random_sound.get_file_url(),
            'volume_level': volume_level,
            'is_test': True
        }
        
        # Send to overlay
        room = f"user_{current_user.id}"
        socketio.emit('sound_effect_alert', test_sound_data, room=room)
        
        current_app.logger.info(f"Test sound effect sent: {random_sound.name}")
        return jsonify({
            'success': True, 
            'sound_name': random_sound.name,
            'message': f'Тестийн дуу илгээгдлээ: {random_sound.name}'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error testing sound effect: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/sound-effects/preview/<int:sound_id>')
def preview_sound(sound_id):
    """Serve sound file for preview (with basic rate limiting)"""
    try:
        from app.models.sound_effect import SoundEffect
        
        sound = SoundEffect.query.get_or_404(sound_id)
        if not sound.is_active:
            abort(404)
        
        # Return the file URL for frontend to use
        return jsonify({
            'success': True,
            'file_url': sound.get_file_url(),
            'name': sound.name,
            'duration': float(sound.duration_seconds)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error previewing sound: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@socketio.on('join_marathon_room')
def handle_join_marathon_room(data):
    """Handle client joining a marathon overlay room"""
    streamer_id = data.get('streamer_id')
    room_type = data.get('room_type', 'marathon_overlay')
    
    if streamer_id and room_type == 'marathon_overlay':
        room = f"marathon_overlay_{streamer_id}"
        join_room(room)
        current_app.logger.info(f"SOCKET: Client {request.sid} joined marathon overlay room: {room}")
        # Send acknowledgment back to client
        emit('room_joined', {'room': room, 'status': 'success', 'type': 'marathon_overlay'})

@socketio.on('join_leaderboard_room')
def handle_join_leaderboard_room(data):
    """Handle client joining a leaderboard overlay room"""
    user_id = data.get('user_id')
    
    if user_id:
        room = f"leaderboard_{user_id}"
        join_room(room)
        current_app.logger.info(f"SOCKET: Client {request.sid} joined leaderboard room: {room}")
        # Send acknowledgment back to client
        emit('room_joined', {'room': room, 'status': 'success', 'type': 'leaderboard'})


# ================================
# SOUND EFFECTS MANAGEMENT ROUTES
# ================================

@main_bp.route('/api/admin/sound-effects', methods=['GET'])
@login_required
def admin_list_sound_effects():
    """Get all sound effects for admin management"""
    try:
        from app.models.sound_effect import SoundEffect
        
        # Only allow dev access for now
        if not hasattr(current_user, 'dev_access') or not current_user.dev_access:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        sounds = SoundEffect.query.order_by(SoundEffect.name).all()
        return jsonify({
            'success': True,
            'sounds': [sound.to_dict() for sound in sounds]
        })
        
    except Exception as e:
        current_app.logger.error(f"Error listing sound effects: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/admin/sound-effects', methods=['POST'])
@login_required
def admin_add_sound_effect():
    """Add new sound effect"""
    try:
        from app.models.sound_effect import SoundEffect
        import mutagen
        from mutagen.wave import WAVE
        from mutagen.mp3 import MP3
        
        # Only allow dev access for now
        if not hasattr(current_user, 'dev_access') or not current_user.dev_access:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Check if file was uploaded
        if 'audio_file' not in request.files:
            return jsonify({'success': False, 'error': 'No audio file provided'}), 400
        
        file = request.files['audio_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Get form data
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        
        if not name:
            return jsonify({'success': False, 'error': 'Name is required'}), 400
        
        # Check file extension
        allowed_extensions = {'.wav', '.mp3', '.ogg'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'error': 'Only WAV, MP3, and OGG files are allowed'}), 400
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        
        # Save file temporarily to analyze it
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
        temp_path = os.path.join(upload_folder, 'temp', unique_filename)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        file.save(temp_path)
        
        try:
            # Get duration and file size
            audio_file = mutagen.File(temp_path)
            if audio_file is None:
                raise ValueError("Invalid audio file")
            
            duration_seconds = audio_file.info.length
            
            # Normalize audio to -20 dBFS
            normalized_path = normalize_audio(temp_path, target_dbfs=-20.0)
            file_size = os.path.getsize(normalized_path)
            
            # Move to permanent location
            assets_folder = os.path.join('app', 'static', 'assets', 'sound_effects')
            os.makedirs(assets_folder, exist_ok=True)
            final_path = os.path.join(assets_folder, unique_filename)
            shutil.move(normalized_path, final_path)
            
            # Clean up temp file if it still exists
            if os.path.exists(temp_path) and temp_path != normalized_path:
                os.remove(temp_path)
            
            # Create database record
            sound_effect = SoundEffect(
                name=name,
                filename=unique_filename,
                duration_seconds=duration_seconds,
                file_size=file_size,
                category=category or None,
                is_active=True
            )
            
            db.session.add(sound_effect)
            db.session.commit()
            
            current_app.logger.info(f"Sound effect added: {name} ({unique_filename})")
            return jsonify({
                'success': True,
                'sound': sound_effect.to_dict(),
                'message': f'Sound effect "{name}" added successfully'
            })
            
        except Exception as e:
            # Clean up file if database operation fails
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e
            
    except Exception as e:
        current_app.logger.error(f"Error adding sound effect: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/admin/sound-effects/<int:sound_id>', methods=['PUT'])
@login_required
def admin_update_sound_effect(sound_id):
    """Update existing sound effect"""
    try:
        from app.models.sound_effect import SoundEffect
        
        # Only allow dev access for now
        if not hasattr(current_user, 'dev_access') or not current_user.dev_access:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        sound = SoundEffect.query.get_or_404(sound_id)
        data = request.get_json()
        
        # Update fields
        if 'name' in data:
            sound.name = data['name'].strip()
        if 'category' in data:
            sound.category = data['category'].strip() or None
        if 'is_active' in data:
            sound.is_active = bool(data['is_active'])
        
        sound.updated_at = datetime.utcnow()
        db.session.commit()
        
        current_app.logger.info(f"Sound effect updated: {sound.name} (ID: {sound_id})")
        return jsonify({
            'success': True,
            'sound': sound.to_dict(),
            'message': f'Sound effect "{sound.name}" updated successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error updating sound effect: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/admin/sound-effects/<int:sound_id>', methods=['DELETE'])
@login_required
def admin_delete_sound_effect(sound_id):
    """Delete sound effect"""
    try:
        from app.models.sound_effect import SoundEffect
        from app.models.sound_effect_donation import SoundEffectDonation
        
        # Only allow dev access for now
        if not hasattr(current_user, 'dev_access') or not current_user.dev_access:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        sound = SoundEffect.query.get_or_404(sound_id)
        sound_name = sound.name
        filename = sound.filename
        
        # Check if there are any donations using this sound effect
        donation_count = SoundEffectDonation.query.filter_by(sound_effect_id=sound_id).count()
        
        if donation_count > 0:
            # Delete related donation records first
            SoundEffectDonation.query.filter_by(sound_effect_id=sound_id).delete()
            current_app.logger.info(f"Deleted {donation_count} related donation records for sound effect: {sound_name}")
        
        # Delete file from filesystem
        file_path = os.path.join('app', 'static', 'assets', 'sound_effects', filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            current_app.logger.info(f"Deleted audio file: {file_path}")
        
        # Delete sound effect from database
        db.session.delete(sound)
        db.session.commit()
        
        if donation_count > 0:
            current_app.logger.info(f"Sound effect force deleted (removed {donation_count} donation records): {sound_name} (ID: {sound_id})")
            return jsonify({
                'success': True,
                'message': f'Sound effect "{sound_name}" deleted successfully (removed {donation_count} related donation records)',
                'deleted': True
            })
        else:
            current_app.logger.info(f"Sound effect deleted: {sound_name} (ID: {sound_id})")
            return jsonify({
                'success': True,
                'message': f'Sound effect "{sound_name}" deleted successfully',
                'deleted': True
            })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting sound effect: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def normalize_audio(input_path, target_dbfs=-20.0):
    """Normalize audio file to target dBFS level"""
    try:
        from pydub import AudioSegment
        
        current_app.logger.info(f"Starting normalization for: {input_path}")
        
        # Load audio file
        audio = AudioSegment.from_file(input_path)
        original_dbfs = audio.dBFS
        
        # Calculate the change needed to reach target dBFS
        change_in_dbfs = target_dbfs - original_dbfs
        
        # Apply normalization
        normalized_audio = audio + change_in_dbfs
        final_dbfs = normalized_audio.dBFS
        
        # Generate output path
        base_name, ext = os.path.splitext(input_path)
        output_path = f"{base_name}_normalized{ext}"
        
        # Export normalized audio
        normalized_audio.export(output_path, format=ext[1:])  # Remove dot from extension
        
        current_app.logger.info(f"✅ Audio normalized successfully: {original_dbfs:.1f} dBFS -> {final_dbfs:.1f} dBFS (target: {target_dbfs} dBFS)")
        return output_path
        
    except Exception as e:
        current_app.logger.error(f"❌ Error normalizing audio: {str(e)}")
        # Return original path if normalization fails
        return input_path

def clean_filename_for_name(filename):
    """Convert filename to clean sound name"""
    # Remove extension
    name_without_ext = re.sub(r'\.[^.]+$', '', filename)
    
    # Replace underscores, dashes, and dots with spaces
    cleaned = re.sub(r'[_\-\.]+', ' ', name_without_ext)
    
    # Remove multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Capitalize first letter of each word
    cleaned = ' '.join(word.capitalize() for word in cleaned.split())
    
    return cleaned.strip()

@main_bp.route('/api/admin/sound-effects/mass-upload', methods=['POST'])
@login_required
def admin_mass_upload_sound_effects():
    """Mass upload multiple sound effects"""
    try:
        from app.models.sound_effect import SoundEffect
        import mutagen
        
        # Only allow dev access for now
        if not hasattr(current_user, 'dev_access') or not current_user.dev_access:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Get form data
        category = request.form.get('category', '').strip()
        if not category:
            return jsonify({'success': False, 'error': 'Category is required'}), 400
        
        # Check if files were uploaded
        if 'audio_files' not in request.files:
            return jsonify({'success': False, 'error': 'No audio files provided'}), 400
        
        files = request.files.getlist('audio_files')
        if not files or len(files) == 0:
            return jsonify({'success': False, 'error': 'No files selected'}), 400
        
        # Process each file
        successful_uploads = 0
        failed_uploads = 0
        errors = []
        total_files = len(files)
        
        allowed_extensions = {'.wav', '.mp3', '.ogg'}
        
        for i, file in enumerate(files):
            try:
                if file.filename == '':
                    errors.append(f"File {i+1}: Empty filename")
                    failed_uploads += 1
                    continue
                
                # Check file extension
                file_ext = os.path.splitext(file.filename)[1].lower()
                if file_ext not in allowed_extensions:
                    errors.append(f"{file.filename}: Invalid format (only WAV, MP3, OGG allowed)")
                    failed_uploads += 1
                    continue
                
                # Generate clean name from filename
                sound_name = clean_filename_for_name(file.filename)
                
                # Generate unique filename
                unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                
                # Save file temporarily
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
                temp_path = os.path.join(upload_folder, 'temp', unique_filename)
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                file.save(temp_path)
                
                try:
                    # Get duration
                    audio_file = mutagen.File(temp_path)
                    if audio_file is None:
                        raise ValueError("Invalid audio file")
                    
                    duration_seconds = audio_file.info.length
                    
                    # Normalize audio to -20 dBFS
                    normalized_path = normalize_audio(temp_path, target_dbfs=-20.0)
                    file_size = os.path.getsize(normalized_path)
                    
                    # Move to permanent location
                    assets_folder = os.path.join('app', 'static', 'assets', 'sound_effects')
                    os.makedirs(assets_folder, exist_ok=True)
                    final_path = os.path.join(assets_folder, unique_filename)
                    shutil.move(normalized_path, final_path)
                    
                    # Clean up temp files
                    if os.path.exists(temp_path) and temp_path != normalized_path:
                        os.remove(temp_path)
                    if os.path.exists(normalized_path) and normalized_path != final_path:
                        os.remove(normalized_path)
                    
                    # Create database record
                    sound_effect = SoundEffect(
                        name=sound_name,
                        filename=unique_filename,
                        duration_seconds=duration_seconds,
                        file_size=file_size,
                        category=category,
                        is_active=True
                    )
                    
                    db.session.add(sound_effect)
                    successful_uploads += 1
                    current_app.logger.info(f"Mass upload: Added {sound_name} from {file.filename}")
                    
                except Exception as e:
                    # Clean up files on error
                    for cleanup_path in [temp_path, normalized_path if 'normalized_path' in locals() else None]:
                        if cleanup_path and os.path.exists(cleanup_path):
                            os.remove(cleanup_path)
                    
                    errors.append(f"{file.filename}: Processing error - {str(e)}")
                    failed_uploads += 1
                    current_app.logger.error(f"Error processing {file.filename}: {str(e)}")
                    
            except Exception as e:
                errors.append(f"{file.filename}: Upload error - {str(e)}")
                failed_uploads += 1
                current_app.logger.error(f"Error uploading {file.filename}: {str(e)}")
        
        # Commit all successful uploads
        if successful_uploads > 0:
            db.session.commit()
        
        current_app.logger.info(f"Mass upload completed: {successful_uploads}/{total_files} successful")
        
        return jsonify({
            'success': True,
            'results': {
                'successful': successful_uploads,
                'failed': failed_uploads,
                'total': total_files
            },
            'errors': errors if errors else None,
            'message': f'Mass upload completed: {successful_uploads}/{total_files} files processed successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in mass upload: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/admin/sound-effects/clear-all', methods=['DELETE'])
@login_required
def admin_clear_all_sound_effects():
    """Delete all sound effects"""
    try:
        from app.models.sound_effect import SoundEffect
        from app.models.sound_effect_donation import SoundEffectDonation
        
        # Only allow dev access for now
        if not hasattr(current_user, 'dev_access') or not current_user.dev_access:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Get all sound effects
        all_sounds = SoundEffect.query.all()
        total_count = len(all_sounds)
        
        if total_count == 0:
            return jsonify({
                'success': True,
                'deleted_count': 0,
                'message': 'No sound effects to delete'
            })
        
        # Delete all related donation records first
        deleted_donations = SoundEffectDonation.query.count()
        if deleted_donations > 0:
            SoundEffectDonation.query.delete()
            current_app.logger.info(f"Deleted {deleted_donations} sound effect donation records")
        
        # Delete all audio files from filesystem
        assets_folder = os.path.join('app', 'static', 'assets', 'sound_effects')
        deleted_files = 0
        
        for sound in all_sounds:
            file_path = os.path.join(assets_folder, sound.filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    deleted_files += 1
                except Exception as e:
                    current_app.logger.warning(f"Could not delete file {file_path}: {str(e)}")
        
        # Delete all sound effects from database
        SoundEffect.query.delete()
        db.session.commit()
        
        current_app.logger.info(f"Cleared all sound effects: {total_count} sounds, {deleted_donations} donations, {deleted_files} files")
        
        return jsonify({
            'success': True,
            'deleted_count': total_count,
            'deleted_donations': deleted_donations,
            'deleted_files': deleted_files,
            'message': f'Successfully deleted {total_count} sound effects and {deleted_donations} related donation records'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error clearing all sound effects: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/donor-leaderboard')
@login_required
def donor_leaderboard_settings():
    """Donor leaderboard settings page"""
    try:
        from app.models.donor_leaderboard import DonorLeaderboard
        from app.models.donor_leaderboard_settings import DonorLeaderboardSettings
        
        # Get or create settings for user
        settings = DonorLeaderboardSettings.get_or_create_for_user(current_user.id)
        
        # Get current leaderboard data
        top_donors = DonorLeaderboard.get_top_donors(current_user.id, limit=10)
        
        # Generate secure overlay URL
        overlay_url = url_for('main.leaderboard_overlay', token=settings.overlay_token, _external=True)
        
        return render_template('donor_leaderboard.html',
                             settings=settings,
                             top_donors=[donor.to_dict() for donor in top_donors],
                             overlay_url=overlay_url)
                             
    except Exception as e:
        current_app.logger.error(f"Error loading donor leaderboard settings: {str(e)}")
        flash('Хандивчдын жагсаалт ачаалахад алдаа гарлаа', 'error')
        return redirect(url_for('main.dashboard'))

@main_bp.route('/donor-leaderboard/update', methods=['POST'])
@login_required
def update_donor_leaderboard_settings():
    """Update donor leaderboard settings"""
    try:
        from app.models.donor_leaderboard_settings import DonorLeaderboardSettings
        
        # Get or create settings
        settings = DonorLeaderboardSettings.get_or_create_for_user(current_user.id)
        
        # Get form data
        is_enabled = request.form.get('is_enabled') == 'on'
        positions_count = request.form.get('positions_count', 3, type=int)
        show_amounts = request.form.get('show_amounts') == 'on'
        show_donation_counts = request.form.get('show_donation_counts') == 'on'
        
        # Update settings
        settings.update_settings(
            is_enabled=is_enabled,
            positions_count=positions_count,
            show_amounts=show_amounts,
            show_donation_counts=show_donation_counts
        )
        
        # Handle styling updates if provided
        if request.form.get('throne_height'):
            throne_styling = settings.get_throne_styling()
            throne_styling['height'] = int(request.form.get('throne_height', 50))
            throne_styling['width'] = int(request.form.get('throne_width', 100))
            settings.set_throne_styling(throne_styling)
        
        if request.form.get('podium_height'):
            podium_styling = settings.get_podium_styling()
            podium_styling['height'] = int(request.form.get('podium_height', 45))
            podium_styling['width'] = int(request.form.get('podium_width', 100))
            settings.set_podium_styling(podium_styling)
        
        if request.form.get('standard_background_color'):
            standard_styling = settings.get_standard_styling()
            standard_styling['background_color'] = request.form.get('standard_background_color')
            standard_styling['height'] = int(request.form.get('standard_height', 40))
            standard_styling['width'] = int(request.form.get('standard_width', 100))
            settings.set_standard_styling(standard_styling)
        
        # Handle font settings if provided
        if request.form.get('names_font_size'):
            global_styling = settings.get_global_styling()
            global_styling['names_font'] = {
                'size': int(request.form.get('names_font_size', 16)),
                'color': request.form.get('names_font_color', '#FFFFFF'),
                'weight': request.form.get('names_font_weight', '600'),
                'italic': request.form.get('names_italic') == 'on'
            }
            global_styling['amounts_font'] = {
                'size': int(request.form.get('amounts_font_size', 14)),
                'color': request.form.get('amounts_font_color', '#FFD700'),
                'weight': request.form.get('amounts_font_weight', '500'),
                'italic': request.form.get('amounts_italic') == 'on'
            }
            global_styling['positions_font'] = {
                'size': int(request.form.get('positions_font_size', 18)),
                'color': request.form.get('positions_font_color', '#FFFFFF'),
                'weight': request.form.get('positions_font_weight', '700'),
                'italic': request.form.get('positions_italic') == 'on'
            }
            settings.set_global_styling(global_styling)
        
        db.session.commit()
        
        # Emit real-time update to overlay
        from app.models.donor_leaderboard import DonorLeaderboard
        top_donors = DonorLeaderboard.get_top_donors(current_user.id, limit=settings.positions_count)
        
        socketio.emit('leaderboard_updated', {
            'settings': settings.to_dict(),
            'top_donors': [donor.to_dict() for donor in top_donors],
            'enabled': settings.is_enabled
        }, room=f'leaderboard_{current_user.id}')
        
        current_app.logger.info(f"Updated donor leaderboard settings for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Тохиргоо амжилттай хадгалагдлаа',
            'settings': settings.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating donor leaderboard settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/donor-leaderboard/refresh', methods=['POST'])
@login_required
def refresh_leaderboard_data():
    """Force recalculation of leaderboard data"""
    try:
        current_app.logger.info(f"Manual leaderboard refresh requested by user {current_user.id}")
        
        # For now, just return current data
        # In the future, this could trigger a background recalculation
        from app.models.donor_leaderboard import DonorLeaderboard
        
        top_donors = DonorLeaderboard.get_top_donors(current_user.id, limit=10)
        total_donors = DonorLeaderboard.query.filter_by(user_id=current_user.id).count()
        
        return jsonify({
            'success': True,
            'message': 'Мэдээлэл шинэчлэгдлээ',
            'total_donors': total_donors,
            'top_donors': [donor.to_dict() for donor in top_donors]
        })
        
    except Exception as e:
        current_app.logger.error(f"Error refreshing leaderboard data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/leaderboard-overlay/<token>')
def leaderboard_overlay(token):
    """Public leaderboard overlay page for OBS integration"""
    try:
        from app.models.user import User
        from app.models.donor_leaderboard import DonorLeaderboard
        from app.models.donor_leaderboard_settings import DonorLeaderboardSettings
        
        # Get settings by token
        settings = DonorLeaderboardSettings.query.filter_by(overlay_token=token).first()
        if not settings:
            abort(404)
        
        # Get user from settings
        user = settings.user
        
        # If leaderboard is disabled, show empty page
        if not settings.is_enabled:
            return render_template('leaderboard_overlay.html',
                                 user=user,
                                 settings=settings,
                                 top_donors=[],
                                 enabled=False)
        
        # Get top donors based on position count
        top_donors = DonorLeaderboard.get_top_donors(user.id, limit=settings.positions_count)
        
        return render_template('leaderboard_overlay.html',
                             user=user,
                             settings=settings,
                             top_donors=[donor.to_dict() for donor in top_donors],
                             enabled=True)
                             
    except Exception as e:
        current_app.logger.error(f"Error loading leaderboard overlay for token {token}: {str(e)}")
        abort(500)

