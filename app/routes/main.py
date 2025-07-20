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
import time
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

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
        
        current_app.logger.info(f"TTS GENERATION: Starting for user {user_id}, text: '{text}'")
        
        # Check usage limits
        limiter = TTSLimiter()
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

@main_bp.route('/donation-alert')
@login_required
def donation_alert():
    from app.models.donation_alert_settings import DonationAlertSettings
    from app.models.user_asset import UserAsset
    
    # Get or create settings for user
    settings = DonationAlertSettings.get_or_create_for_user(current_user.id)
    
    # Ensure user has an overlay token
    overlay_token = current_user.get_overlay_token()
    
    # Get user's assets
    user_gifs = UserAsset.get_user_assets(current_user.id, 'gif')
    user_sounds = UserAsset.get_user_assets(current_user.id, 'sound')
    
    # Get default assets
    default_gifs = get_default_assets('gifs')
    default_sounds = get_default_assets('sounds')
    
    return render_template('donation_alert.html', 
                         settings=settings,
                         user_gifs=user_gifs,
                         user_sounds=user_sounds,
                         default_gifs=default_gifs,
                         default_sounds=default_sounds,
                         overlay_token=overlay_token)

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
        
        # Create payment record
        payment = SubscriptionPayment.create_payment_record(
            user_id=current_user.id,
            tier=tier,
            months=months,
            amount=invoice_result.get('amount'),
            invoice_data=invoice_result
        )
        
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
                    
                    # Activate subscription
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

@main_bp.route('/overlay/<token>')
def overlay(token):
    """Donation alert overlay page for OBS"""
    try:
        from app.models.user import User
        from app.models.donation_alert_settings import DonationAlertSettings
        
        # Get user by overlay token
        user = User.query.filter_by(overlay_token=token).first()
        if not user:
            current_app.logger.warning(f"Invalid overlay token attempted: {token}")
            abort(404)
        
        settings = DonationAlertSettings.get_or_create_for_user(user.id)
        
        return render_template('overlay.html', user=user, settings=settings)
        
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
        
        return render_template('donate.html', 
                             streamer=user, 
                             connected_platforms=connected_platforms,
                             recent_donations=recent_donations,
                             username=username)
        
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


# Admin Testing Route for Real Donation Simulation
@main_bp.route('/admin/simulate-donations', methods=['POST'])
@login_required
def simulate_real_donations():
    """Create real donation payments and mark them as paid to test the full donation flow"""
    try:
        from app.models.donation_payment import DonationPayment
        
        # Only allow if user is authenticated
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
            
        # Get the number of donations to simulate (default 3)
        num_donations = request.json.get('count', 3)
        delay_seconds = float(request.json.get('delay', 1))
        
        if num_donations > 10:  # Safety limit
            return jsonify({'success': False, 'error': 'Maximum 10 donations allowed'}), 400
            
        # Sample donation data
        test_donations = [
            {
                'donor_name': 'Эхний донор',
                'amount': 1000,
                'message': 'Эхний queue donation туршилт!'
            },
            {
                'donor_name': 'Хоёрдах донор', 
                'amount': 2500,
                'message': 'Хоёрдах queue donation туршилт!'
            },
            {
                'donor_name': 'Гуравдах донор',
                'amount': 5000, 
                'message': 'Гуравдах queue donation туршилт!'
            },
            {
                'donor_name': 'Дөрөвдүгээр донор',
                'amount': 10000,
                'message': 'Дөрөвдүгээр queue donation туршилт!'
            },
            {
                'donor_name': 'Тавдугаар донор',
                'amount': 1500,
                'message': 'Тавдугаар queue donation туршилт!'
            }
        ]
        
        # Create and process donations
        payment_ids = []
        for i in range(min(num_donations, len(test_donations))):
            donation_data = test_donations[i]
            
            # Create donation payment (but skip the actual QPay API call)
            donation_payment = DonationPayment(
                streamer_user_id=current_user.id,
                donor_name=donation_data['donor_name'],
                donor_platform='guest',
                donor_user_id=None,
                amount=donation_data['amount'],
                currency='MNT',
                message=donation_data['message'],
                # Skip QPay fields for simulation
                quickpay_invoice_id=f"sim_{current_user.id}_{i}_{int(time.time())}",
                status='pending'
            )
            
            db.session.add(donation_payment)
            db.session.flush()  # Get the ID
            
            payment_ids.append(donation_payment.id)
            
            current_app.logger.info(f"Created simulated donation payment {donation_payment.id}: {donation_data['donor_name']} - {donation_data['amount']}₮")
        
        # Commit all payments first
        db.session.commit()
        
        # Mark the first payment as paid immediately
        if payment_ids:
            first_payment = DonationPayment.query.get(payment_ids[0])
            if first_payment:
                success = first_payment.mark_as_paid('SimulatedPayment')
                if success:
                    current_app.logger.info(f"✅ Simulated donation payment {payment_ids[0]} marked as paid immediately")
                else:
                    current_app.logger.error(f"❌ Failed to mark simulated donation payment {payment_ids[0]} as paid")
        
        # Schedule remaining payments to be marked as paid with delays using a background task
        if len(payment_ids) > 1:
            from threading import Thread
            
            # Capture the app instance for the background thread
            app = current_app._get_current_object()
            
            def process_remaining_payments():
                with app.app_context():
                    for i in range(1, len(payment_ids)):
                        payment_id = payment_ids[i]
                        delay = i * delay_seconds
                        current_app.logger.info(f"⏰ Processing payment {payment_id} after {delay}s delay")
                        
                        time.sleep(delay)
                        
                        try:
                            payment = DonationPayment.query.get(payment_id)
                            if payment and payment.status == 'pending':
                                success = payment.mark_as_paid('SimulatedPayment')
                                if success:
                                    current_app.logger.info(f"✅ Simulated donation payment {payment_id} marked as paid after {delay}s delay")
                                else:
                                    current_app.logger.error(f"❌ Failed to mark simulated donation payment {payment_id} as paid")
                            else:
                                current_app.logger.warning(f"⚠️ Payment {payment_id} not found or not pending")
                        except Exception as e:
                            current_app.logger.error(f"Error processing delayed payment {payment_id}: {str(e)}")
            
            # Start background thread for delayed payments
            thread = Thread(target=process_remaining_payments)
            thread.daemon = True
            thread.start()
            current_app.logger.info(f"🚀 Started background thread to process {len(payment_ids)-1} delayed payments")
        
        return jsonify({
            'success': True, 
            'message': f'{num_donations} real donation payments created and will be processed with {delay_seconds}s delays (rapid donation simulation)',
            'payment_ids': payment_ids
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error simulating donations: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# DEV: Tier Toggle Endpoint (Remove in production)
@main_bp.route('/dev/toggle-tier', methods=['POST'])
@login_required
def toggle_tier():
    """Toggle user's subscription tier for development testing"""
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


# Marathon SocketIO handlers
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

