from flask import current_app, url_for
from app.models.user import User
from app.models.platform_connection import PlatformConnection, PlatformType
from app.extensions import db
import requests
import secrets

def get_oauth_configs():
    """Get OAuth configurations with credentials from config"""
    return {
        'twitch': {
            'authorize_url': 'https://id.twitch.tv/oauth2/authorize',
            'token_url': 'https://id.twitch.tv/oauth2/token',
            'userinfo_url': 'https://api.twitch.tv/helix/users',
            'scopes': ['user:read:email'],
            'client_id': current_app.config['TWITCH_CLIENT_ID'],
            'client_secret': current_app.config['TWITCH_CLIENT_SECRET'],
        },
        'youtube': {
            'authorize_url': 'https://accounts.google.com/o/oauth2/v2/auth',
            'token_url': 'https://oauth2.googleapis.com/token',
            'userinfo_url': 'https://www.googleapis.com/oauth2/v2/userinfo',
            'scopes': ['openid', 'email', 'profile'],
            'client_id': current_app.config['YOUTUBE_CLIENT_ID'],
            'client_secret': current_app.config['YOUTUBE_CLIENT_SECRET'],
        },
        'kick': {
            'authorize_url': 'https://id.kick.com/oauth/authorize',
            'token_url': 'https://id.kick.com/oauth/token',
            'userinfo_url': 'https://api.kick.com/public/v1/users',  # Official API endpoint
            'scopes': ['user:read'],
            'client_id': current_app.config['KICK_CLIENT_ID'],
            'client_secret': current_app.config['KICK_CLIENT_SECRET'],
            'requires_pkce': True,  # Kick requires PKCE
        }
    }

def exchange_code_for_token(platform, code):
    """Exchange authorization code for access token"""
    from flask import session
    
    config = get_oauth_configs()[platform]
    
    data = {
        'client_id': config['client_id'],
        'client_secret': config['client_secret'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': f"https://{current_app.config['SERVER_NAME']}/oauth/callback/{platform}"
    }
    
    # Add PKCE code verifier for Kick
    if config.get('requires_pkce') and platform == 'kick':
        code_verifier = session.pop(f'oauth_code_verifier_{platform}', None)
        if code_verifier:
            data['code_verifier'] = code_verifier
            current_app.logger.info(f'Added PKCE code verifier for {platform}')
        else:
            current_app.logger.error(f'Missing PKCE code verifier for {platform}')
            raise ValueError('Missing PKCE code verifier for Kick OAuth')
    
    current_app.logger.info(f'Exchanging code for token - Platform: {platform}, URL: {config["token_url"]}')
    
    response = requests.post(config['token_url'], data=data, timeout=30)
    
    if response.status_code != 200:
        current_app.logger.error(f'Token exchange failed - Status: {response.status_code}, Response: {response.text}')
    
    response.raise_for_status()
    
    token_data = response.json()
    
    # Enhanced logging for Google/YouTube token exchange
    if platform == 'youtube':
        print("\n" + "="*80)
        print("GOOGLE OAUTH TOKEN EXCHANGE - TERMINAL LOG")
        print("="*80)
        print(f"Platform: {platform}")
        print(f"Token URL: {config['token_url']}")
        print(f"Response Status: {response.status_code}")
        print("\nTOKEN DATA:")
        print("-" * 40)
        import json
        # Don't log the actual tokens for security, just the structure
        safe_token_data = {k: ('***REDACTED***' if 'token' in k.lower() else v) for k, v in token_data.items()}
        print(json.dumps(safe_token_data, indent=2))
        print("-" * 40)
        print("="*80)
        print()
    
    # Enhanced logging for Kick token exchange
    if platform == 'kick':
        print("\n" + "="*80)
        print("KICK OAUTH TOKEN EXCHANGE - TERMINAL LOG")
        print("="*80)
        print(f"Platform: {platform}")
        print(f"Token URL: {config['token_url']}")
        print(f"Response Status: {response.status_code}")
        print("\nTOKEN DATA:")
        print("-" * 40)
        import json
        # Don't log the actual tokens for security, just the structure
        safe_token_data = {k: ('***REDACTED***' if 'token' in k.lower() else v) for k, v in token_data.items()}
        print(json.dumps(safe_token_data, indent=2))
        print("-" * 40)
        print("\nFULL TOKEN DATA (for debugging):")
        print(json.dumps(token_data, indent=2))
        print("-" * 40)
        print("="*80)
        print()
    
    return token_data

def get_platform_user_data(platform, access_token, token_data=None):
    """Get user data from platform API"""
    config = get_oauth_configs()[platform]
    
    # Special handling for Kick - use official API endpoint
    if platform == 'kick':
        print(f"\n[KICK DEBUG] Using official Kick API endpoint: {config['userinfo_url']}")
        # Don't try to decode the token, just proceed to the API call
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    if platform == 'twitch':
        headers['Client-Id'] = config['client_id']
    
    current_app.logger.info(f'Fetching user data from {platform} API: {config["userinfo_url"]}')
    
    response = requests.get(config['userinfo_url'], headers=headers, timeout=30)
    
    if response.status_code != 200:
        current_app.logger.error(f'User data fetch failed - Status: {response.status_code}, Response: {response.text}')
    
    response.raise_for_status()
    
    data = response.json()
    
    # Enhanced logging for Google/YouTube API response
    if platform == 'youtube':
        print("\n" + "="*80)
        print("GOOGLE OAUTH API RESPONSE - TERMINAL LOG")
        print("="*80)
        print(f"Platform: {platform}")
        print(f"API URL: {config['userinfo_url']}")
        print(f"Response Status: {response.status_code}")
        print("\nRAW RESPONSE DATA:")
        print("-" * 40)
        import json
        print(json.dumps(data, indent=2))
        print("-" * 40)
        print("AVAILABLE FIELDS:")
        for key, value in data.items():
            print(f"  {key}: {value}")
        print("\nPROFILE PICTURE:")
        if 'picture' in data:
            print(f"  Picture URL: {data['picture']}")
        else:
            print("  No picture field found")
        print("="*80)
        print()
    
    current_app.logger.info(f'Raw API response from {platform}: {data}')
    
    # Normalize user data across platforms
    if platform == 'twitch':
        user_info = data['data'][0]
        return {
            'user_id': user_info['id'],
            'username': user_info['login'],
            'display_name': user_info['display_name'],
            'email': user_info.get('email'),
            'platform_data': user_info
        }
    elif platform == 'youtube':
        # Google userinfo API returns basic profile information
        user_id = data.get('id')
        name = data.get('name', 'Google User')
        email = data.get('email')
        picture = data.get('picture')
        
        # Validate required fields
        if not user_id:
            current_app.logger.error(f'YouTube OAuth: Missing user ID in response: {data}')
            raise ValueError('Missing user ID from Google API response')
        
        if not email:
            current_app.logger.error(f'YouTube OAuth: Missing email in response: {data}')
            raise ValueError('Missing email from Google API response')
        
        return {
            'user_id': user_id,
            'username': name,
            'display_name': name,
            'email': email,
            'picture': picture,
            'verified_email': data.get('verified_email', False),
            'given_name': data.get('given_name'),
            'platform_data': data
        }
    elif platform == 'kick':
        # Kick API returns data in a 'data' array
        if 'data' in data and len(data['data']) > 0:
            user_info = data['data'][0]
            return {
                'user_id': str(user_info['user_id']),
                'username': user_info.get('name', 'Kick User'),
                'display_name': user_info.get('name', 'Kick User'),
                'email': user_info.get('email'),
                'picture': user_info.get('profile_picture'),
                'platform_data': user_info
            }
        else:
            # Fallback if no data found
            return {
                'user_id': str(data.get('id', 'unknown')),
                'username': data.get('username', 'Kick User'),
                'display_name': data.get('display_name', data.get('username', 'Kick User')),
                'email': data.get('email'),
                'platform_data': data
            }
    
    return {}

def save_platform_connection(platform, token_data, user_data, user):
    """Save or update platform connection"""
    platform_type = PlatformType[platform.upper()]
    
    # Check if connection already exists
    connection = user.get_platform_connection(platform_type)
    
    if connection:
        # Update existing connection
        connection.access_token = token_data['access_token']
        connection.refresh_token = token_data.get('refresh_token')
        connection.platform_username = user_data['username']
        connection.platform_email = user_data.get('email')
        connection.platform_data = user_data.get('platform_data', {})
        connection.updated_at = db.func.now()
        
        if 'expires_in' in token_data:
            connection.update_tokens(
                token_data['access_token'],
                token_data.get('refresh_token'),
                token_data['expires_in']
            )
    else:
        # Create new connection
        connection = PlatformConnection(
            user_id=user.id,
            platform_type=platform_type,
            platform_user_id=user_data['user_id'],
            platform_username=user_data['username'],
            platform_email=user_data.get('email'),
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            platform_data=user_data.get('platform_data', {})
        )
        
        if 'expires_in' in token_data:
            connection.update_tokens(
                token_data['access_token'],
                token_data.get('refresh_token'),
                token_data['expires_in']
            )
        
        db.session.add(connection)
    
    db.session.commit()

def handle_oauth_login_or_signup(platform, token_data, user_data):
    """Handle OAuth login or signup for users not currently logged in"""
    platform_type = PlatformType[platform.upper()]
    
    # First, check if a platform connection already exists
    existing_connection = PlatformConnection.query.filter_by(
        platform_type=platform_type,
        platform_user_id=user_data['user_id']
    ).first()
    
    if existing_connection:
        # User has used this platform before, log them in
        user = existing_connection.user
        
        # Update tokens
        existing_connection.access_token = token_data['access_token']
        existing_connection.refresh_token = token_data.get('refresh_token')
        if 'expires_in' in token_data:
            existing_connection.update_tokens(
                token_data['access_token'],
                token_data.get('refresh_token'),
                token_data['expires_in']
            )
        
        # Update profile data on each login to keep it fresh
        existing_connection.platform_username = user_data['username']
        existing_connection.platform_email = user_data.get('email')
        existing_connection.platform_data = user_data.get('platform_data', {})
        existing_connection.updated_at = db.func.now()
        
        # Update user's display name if they changed it
        if user_data.get('display_name') and user_data['display_name'] != user.display_name:
            current_app.logger.info(f'Updating display name for {user.username}: {user.display_name} -> {user_data["display_name"]}')
            user.display_name = user_data['display_name']
        
        db.session.commit()
        return user
    else:
        # Check if a user with this email already exists
        email = user_data.get('email')
        if email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                # User exists, link this platform to their existing account
                current_app.logger.info(f'Linking {platform} to existing user: {existing_user.username}')
                save_platform_connection(platform, token_data, user_data, existing_user)
                return existing_user
        
        # New user, create account
        # Generate username from platform username
        base_username = user_data['username']
        username = base_username
        counter = 1
        
        # Ensure username is unique
        while User.query.filter_by(username=username).first():
            username = f"{base_username}_{counter}"
            counter += 1
        
        # Create user
        email = user_data.get('email')
        if not email:
            # For platforms like Kick that don't provide email, generate a unique fallback
            if platform == 'kick':
                email = f"kick_{user_data['user_id']}@{current_app.config['SERVER_NAME']}.local"
                current_app.logger.info(f'Generated fallback email for Kick user: {email}')
            else:
                current_app.logger.error(f'OAuth signup failed: No email for {platform} user: {user_data}')
                raise ValueError(f'Email required for {platform} OAuth signup')
        
        # Validate required fields
        if not username:
            current_app.logger.error(f'OAuth signup failed: No username for {platform} user: {user_data}')
            raise ValueError(f'Username required for {platform} OAuth signup')
            
        user = User(
            username=username,
            email=email,
            display_name=user_data.get('display_name', username)
        )
        
        # Set a random password (they'll use OAuth to login)
        user.set_password(secrets.token_urlsafe(32))
        
        try:
            db.session.add(user)
            db.session.flush()  # Get user ID
            
            # Create free trial subscription for new user
            try:
                user.create_free_trial()
                current_app.logger.info(f'Created free trial for new user: {user.username}')
            except ValueError as e:
                # User already has a subscription or has used their trial
                current_app.logger.info(f'Free trial not created for {user.username}: {str(e)}')
            
            # Create platform connection
            connection = PlatformConnection(
                user_id=user.id,
                platform_type=platform_type,
                platform_user_id=user_data['user_id'],
                platform_username=user_data['username'],
                platform_email=user_data.get('email'),
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token'),
                platform_data=user_data.get('platform_data', {})
            )
            
            if 'expires_in' in token_data:
                connection.update_tokens(
                    token_data['access_token'],
                    token_data.get('refresh_token'),
                    token_data['expires_in']
                )
            
            db.session.add(connection)
            db.session.commit()
            
            return user
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            db.session.rollback()
            current_app.logger.error(f'Error creating OAuth user: {str(e)}\n{error_details}')
            return None