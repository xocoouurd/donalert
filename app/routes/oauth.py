from flask import Blueprint, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, current_user, login_required
from urllib.parse import urlencode
import secrets
from app.models.user import User
from app.models.platform_connection import PlatformConnection, PlatformType
from app.utils.oauth_helpers import (
    get_oauth_configs, exchange_code_for_token, get_platform_user_data,
    save_platform_connection, handle_oauth_login_or_signup
)
from app.extensions import db

oauth_bp = Blueprint('oauth', __name__, url_prefix='/oauth')

@oauth_bp.route('/test-config')
def test_config():
    """Test route to verify OAuth configuration (remove in production)"""
    if not current_app.debug:
        return "Only available in debug mode", 403
    
    configs = get_oauth_configs()
    result = {}
    
    for platform, config in configs.items():
        result[platform] = {
            'client_id_set': bool(config['client_id']),
            'client_secret_set': bool(config['client_secret']),
            'client_id_preview': config['client_id'][:10] + '...' if config['client_id'] else 'NOT SET',
            'authorize_url': config['authorize_url'],
            'scopes': config['scopes']
        }
    
    return f"<pre>{str(result)}</pre>"

@oauth_bp.route('/debug-callback/<platform>')
def debug_callback(platform):
    """Debug route to see callback parameters"""
    if not current_app.debug:
        return "Only available in debug mode", 403
    
    return f"""
    <h3>OAuth Callback Debug for {platform}</h3>
    <p><strong>Query parameters:</strong></p>
    <pre>{dict(request.args)}</pre>
    <p><strong>All request data:</strong></p>
    <pre>
    URL: {request.url}
    Method: {request.method}
    Headers: {dict(request.headers)}
    </pre>
    """

@oauth_bp.route('/test-userinfo/<platform>')
def test_userinfo(platform):
    """Test route to make actual userinfo API call and see response"""
    if not current_app.debug:
        return "Only available in debug mode", 403
    
    # Get auth code from query params
    code = request.args.get('code')
    if not code:
        return f"""
        <h3>Google OAuth API Test for {platform.title()}</h3>
        <p>No authorization code provided.</p>
        <p><strong>Step 1:</strong> <a href="/oauth/connect/{platform}">Click here to authorize with {platform.title()}</a></p>
        <p><strong>Step 2:</strong> You'll be redirected back here with the results</p>
        """
    
    try:
        from app.utils.oauth_helpers import exchange_code_for_token, get_platform_user_data
        import requests
        
        # Exchange code for token
        token_data = exchange_code_for_token(platform, code)
        
        # Make direct API call to see raw response
        headers = {'Authorization': f'Bearer {token_data["access_token"]}'}
        raw_response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', headers=headers)
        raw_data = raw_response.json()
        
        # Get processed user data
        user_data = get_platform_user_data(platform, token_data['access_token'])
        
        return f"""
        <h3>Live {platform.title()} API Test Results</h3>
        
        <h4>Raw Google userinfo API Response:</h4>
        <pre>{raw_data}</pre>
        
        <h4>Available Fields:</h4>
        <ul>
        {''.join([f'<li><strong>{k}:</strong> {v}</li>' for k, v in raw_data.items()])}
        </ul>
        
        <h4>Token Data:</h4>
        <pre>{dict(token_data)}</pre>
        
        <h4>Processed User Data:</h4>
        <pre>{dict(user_data)}</pre>
        
        <h4>Profile Picture URL:</h4>
        <p>{raw_data.get('picture', 'No picture available')}</p>
        {f'<img src="{raw_data.get("picture")}" alt="Profile Picture" style="width: 100px; height: 100px; border-radius: 50%;">' if raw_data.get('picture') else ''}
        """
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"""
        <h3>Error Testing {platform.title()} API</h3>
        <p><strong>Error:</strong> {str(e)}</p>
        <pre>{error_details}</pre>
        """

@oauth_bp.route('/connect/<platform>')
def connect_platform(platform):
    """Initiate OAuth flow for a platform"""
    oauth_configs = get_oauth_configs()
    if platform not in oauth_configs:
        flash(f'Платформ {platform} дэмжигдэхгүй', 'error')
        return redirect(url_for('main.home'))
    
    config = oauth_configs[platform]
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    session[f'oauth_state_{platform}'] = state
    
    # Store the next URL for post-login redirect
    next_url = request.args.get('next')
    if next_url:
        session[f'oauth_next_{platform}'] = next_url
    
    # Build authorization URL with explicit redirect URI
    # Use test route if testing parameter is provided
    if request.args.get('test') == '1':
        redirect_uri = f"https://donalert.invictamotus.com/oauth/test-userinfo/{platform}"
    else:
        redirect_uri = f"https://donalert.invictamotus.com/oauth/callback/{platform}"
    
    params = {
        'client_id': config['client_id'],
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(config['scopes']),
        'state': state
    }
    
    # Add PKCE parameters for Kick
    if config.get('requires_pkce') and platform == 'kick':
        import base64
        import hashlib
        
        # Generate code verifier and challenge for PKCE
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        session[f'oauth_code_verifier_{platform}'] = code_verifier
        params['code_challenge'] = code_challenge
        params['code_challenge_method'] = 'S256'
        
        print(f"[OAUTH DEBUG] Added PKCE parameters for {platform}")
    
    # Add prompt=consent to force fresh OAuth flow even if already authorized
    if request.args.get('force') == '1':
        params['prompt'] = 'consent'
        print(f"[OAUTH DEBUG] Forcing fresh OAuth consent for {platform}")
    
    auth_url = f"{config['authorize_url']}?{urlencode(params)}"
    print(f"[OAUTH DEBUG] Redirecting to OAuth URL: {auth_url}")
    return redirect(auth_url)

@oauth_bp.route('/callback/<platform>')
def callback(platform):
    """Handle OAuth callback"""
    oauth_configs = get_oauth_configs()
    if platform not in oauth_configs:
        flash(f'Платформ {platform} дэмжигдэхгүй', 'error')
        return redirect(url_for('main.home'))
    
    # Verify state parameter
    state = request.args.get('state')
    expected_state = session.pop(f'oauth_state_{platform}', None)
    
    if not state or state != expected_state:
        flash('Хүчингүй OAuth төлөв. Дахин оролдоно уу.', 'error')
        return redirect(url_for('main.home'))
    
    # Check for authorization code
    code = request.args.get('code')
    if not code:
        error = request.args.get('error', 'Unknown error')
        flash(f'OAuth зөвшөөрөл амжилтгүй: {error}', 'error')
        return redirect(url_for('main.home'))
    
    # Exchange code for access token
    try:
        print(f"\n[OAUTH DEBUG] Starting token exchange for {platform}")
        token_data = exchange_code_for_token(platform, code)
        print(f"[OAUTH DEBUG] Token exchange successful for {platform}")
        
        print(f"[OAUTH DEBUG] Fetching user data for {platform}")
        user_data = get_platform_user_data(platform, token_data['access_token'], token_data)
        print(f"[OAUTH DEBUG] User data fetch successful for {platform}")
        
        if current_user.is_authenticated:
            # User is logged in, just connect the platform
            print(f"[OAUTH DEBUG] User already authenticated: {current_user.username}")
            print(f"[OAUTH DEBUG] Connecting {platform} to existing user account")
            
            # For platforms without email (like Kick), we can still link them
            if not user_data.get('email') and platform == 'kick':
                print(f"[OAUTH DEBUG] Kick platform has no email, linking to authenticated user")
                # Add user's email to user_data for consistent platform connection
                user_data['email'] = current_user.email
            
            save_platform_connection(platform, token_data, user_data, current_user)
            flash(f'{platform.title()}-д амжилттай холбогдлоо!', 'success')
        else:
            # User is not logged in, try to find existing user or create new one
            print(f"[OAUTH DEBUG] User not authenticated, attempting OAuth login/signup for {platform}")
            current_app.logger.info(f'Attempting OAuth login/signup for {platform} with user data: {user_data}')
            
            # Check if this is linking to an existing account or creating new one
            existing_user = None
            email = user_data.get('email')
            if email:
                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    print(f"[OAUTH DEBUG] Found existing user with email: {existing_user.username}")
                else:
                    print(f"[OAUTH DEBUG] No existing user found with email: {email}")
            
            user = handle_oauth_login_or_signup(platform, token_data, user_data)
            if user:
                login_user(user)
                user.update_last_login()
                
                if existing_user:
                    print(f"[OAUTH DEBUG] Successfully linked {platform} to existing user: {user.username}")
                    flash(f'{platform.title()}-ыг таны одоо байгаа бүртгэлтэй амжилттай холболоо!', 'success')
                    current_app.logger.info(f'Successfully linked {platform} to existing user: {user.username}')
                else:
                    print(f"[OAUTH DEBUG] Successfully created new user: {user.username}")
                    flash(f'{platform.title()}-ээр бүртгэл амжилттай үүсгэлээ!', 'success')
                    current_app.logger.info(f'Successfully created new user: {user.username}')
            else:
                print(f"[OAUTH DEBUG] Failed to create/login user for {platform}")
                flash(f'{platform.title()}-ээр бүртгэл үүсгэхэд алдаа гарлаа', 'error')
                current_app.logger.error(f'Failed to create/login user for {platform}')
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f'OAuth callback error for {platform}: {str(e)}\n{error_details}')
        flash(f'{platform.title()}-д холбогдохоод алдаа гарлаа. Алдаа: {str(e)}', 'error')
    
    # Check if there's a next URL to redirect to
    next_url = session.pop(f'oauth_next_{platform}', None)
    if next_url:
        return redirect(next_url)
    
    return redirect(url_for('main.dashboard'))

@oauth_bp.route('/disconnect/<platform>')
@login_required
def disconnect_platform(platform):
    """Disconnect a platform"""
    try:
        platform_type = PlatformType[platform.upper()]
        connection = current_user.get_platform_connection(platform_type)
        
        if connection:
            db.session.delete(connection)
            db.session.commit()
            flash(f'{platform.title()}-ээс салгалаа', 'success')
        else:
            flash(f'{platform.title()}-ийн холболт олдсонгүй', 'error')
            
    except KeyError:
        flash(f'Платформ {platform} дэмжигдэхгүй', 'error')
    except Exception as e:
        current_app.logger.error(f'Error disconnecting {platform}: {str(e)}')
        flash(f'{platform.title()}-ээс салгахад алдаа гарлаа', 'error')
        db.session.rollback()
    
    return redirect(url_for('main.dashboard'))

@oauth_bp.route('/set-primary/<platform>')
@login_required
def set_primary_platform(platform):
    """Set a platform as the primary platform"""
    try:
        success = current_user.set_primary_platform(platform)
        if success:
            flash(f'{platform.title()}-ийг үндсэн платформ болгож тохируулав', 'success')
        else:
            flash(f'{platform.title()}-ийн холболт олдсонгүй', 'error')
    except Exception as e:
        current_app.logger.error(f'Error setting primary platform {platform}: {str(e)}')
        flash(f'Үндсэн платформ тохируулахад алдаа гарлаа', 'error')
    
    return redirect(url_for('main.dashboard'))