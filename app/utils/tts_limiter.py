from app.models.tts_usage import TTSUsage
from flask import request
import os

class TTSLimiter:
    """TTS usage limiter and rate controller"""
    
    # Default limits for basic tier users (can be overridden via environment variables)
    DEFAULT_DAILY_REQUESTS = 15
    DEFAULT_MONTHLY_REQUESTS = 450
    DEFAULT_TEST_DAILY_LIMIT = 3  # test requests per day
    
    # Advanced tier multiplier
    ADVANCED_TIER_MULTIPLIER = 3
    
    def __init__(self, user=None):
        # Get base limits from environment variables
        base_daily_requests = int(os.environ.get('TTS_DAILY_REQUESTS', self.DEFAULT_DAILY_REQUESTS))
        base_monthly_requests = int(os.environ.get('TTS_MONTHLY_REQUESTS', self.DEFAULT_MONTHLY_REQUESTS))
        
        # Check if user has advanced tier subscription
        is_advanced_user = False
        if user:
            try:
                subscription = user.get_current_subscription()
                is_advanced_user = (subscription and 
                                   subscription.feature_tier and 
                                   subscription.feature_tier.value == 'advanced')
            except Exception:
                # If subscription check fails, default to basic tier
                is_advanced_user = False
        
        # Apply multiplier for advanced tier users
        multiplier = self.ADVANCED_TIER_MULTIPLIER if is_advanced_user else 1
        
        self.daily_requests = base_daily_requests * multiplier
        self.monthly_requests = base_monthly_requests * multiplier
        
        # Test limits don't scale with tier
        self.test_daily_limit = int(os.environ.get('TTS_TEST_DAILY_LIMIT', self.DEFAULT_TEST_DAILY_LIMIT))
        
        # Store user tier for display purposes
        self.user_tier = 'advanced' if is_advanced_user else 'basic'
    
    def check_limits(self, user_id, text, request_type='donation'):
        """
        Check if user can make TTS request
        
        Returns:
            dict: {'allowed': bool, 'reason': str, 'usage_info': dict}
        """
        # Get current usage
        daily_requests = TTSUsage.get_user_usage_today(user_id)
        monthly_requests = TTSUsage.get_user_usage_this_month(user_id)
        usage_info = {
            'daily_requests': daily_requests,
            'monthly_requests': monthly_requests
        }
        
        # No character limits - Chimege only has request limits
        
        # Rate limiting removed for live streaming donations - streamers can get multiple donations rapidly
        
        # Special limits for test requests
        if request_type == 'test':
            if daily_requests >= self.test_daily_limit:
                return {
                    'allowed': False,
                    'reason': f'Daily test limit reached ({self.test_daily_limit} tests per day).',
                    'usage_info': usage_info
                }
        
        # Check daily limits
        if daily_requests >= self.daily_requests:
            return {
                'allowed': False,
                'reason': f'Daily request limit reached ({self.daily_requests} requests per day).',
                'usage_info': usage_info
            }
        
        
        # Check monthly limits
        if monthly_requests >= self.monthly_requests:
            return {
                'allowed': False,
                'reason': f'Monthly request limit reached ({self.monthly_requests} requests per month).',
                'usage_info': usage_info
            }
        
        
        return {
            'allowed': True,
            'reason': 'Request allowed',
            'usage_info': usage_info
        }
    
    def log_request(self, user_id, text, voice_id, request_type='donation', success=True, error_message=None):
        """Log TTS request"""
        ip_address = request.remote_addr if request else None
        return TTSUsage.log_usage(
            user_id=user_id,
            request_type=request_type,
            character_count=0,  # Character counting disabled - Chimege only limits requests
            voice_id=voice_id,
            success=success,
            error_message=error_message,
            ip_address=ip_address
        )
    
    def get_usage_summary(self, user_id):
        """Get user's current usage summary"""
        return {
            'daily': {
                'requests': TTSUsage.get_user_usage_today(user_id),
                'limit_requests': self.daily_requests
            },
            'monthly': {
                'requests': TTSUsage.get_user_usage_this_month(user_id),
                'limit_requests': self.monthly_requests
            },
            'tier': self.user_tier
        }