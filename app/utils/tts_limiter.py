from app.models.tts_usage import TTSUsage
from flask import request
import os

class TTSLimiter:
    """TTS usage limiter and rate controller"""
    
    # Default limits (can be overridden via environment variables)
    DEFAULT_DAILY_REQUESTS = 5
    DEFAULT_MONTHLY_REQUESTS = 150
    DEFAULT_DAILY_CHARACTERS = 750
    DEFAULT_MONTHLY_CHARACTERS = 22500
    DEFAULT_RATE_LIMIT_REQUESTS = 3  # requests per 5 minutes
    DEFAULT_TEST_DAILY_LIMIT = 3  # test requests per day
    DEFAULT_MAX_MESSAGE_LENGTH = 150  # characters
    
    def __init__(self):
        self.daily_requests = int(os.environ.get('TTS_DAILY_REQUESTS', self.DEFAULT_DAILY_REQUESTS))
        self.monthly_requests = int(os.environ.get('TTS_MONTHLY_REQUESTS', self.DEFAULT_MONTHLY_REQUESTS))
        self.daily_characters = int(os.environ.get('TTS_DAILY_CHARACTERS', self.DEFAULT_DAILY_CHARACTERS))
        self.monthly_characters = int(os.environ.get('TTS_MONTHLY_CHARACTERS', self.DEFAULT_MONTHLY_CHARACTERS))
        self.rate_limit_requests = int(os.environ.get('TTS_RATE_LIMIT_REQUESTS', self.DEFAULT_RATE_LIMIT_REQUESTS))
        self.test_daily_limit = int(os.environ.get('TTS_TEST_DAILY_LIMIT', self.DEFAULT_TEST_DAILY_LIMIT))
        self.max_message_length = int(os.environ.get('TTS_MAX_MESSAGE_LENGTH', self.DEFAULT_MAX_MESSAGE_LENGTH))
    
    def check_limits(self, user_id, text, request_type='donation'):
        """
        Check if user can make TTS request
        
        Returns:
            dict: {'allowed': bool, 'reason': str, 'usage_info': dict}
        """
        # Get current usage
        daily_requests = TTSUsage.get_user_usage_today(user_id)
        monthly_requests = TTSUsage.get_user_usage_this_month(user_id)
        daily_characters = TTSUsage.get_user_character_count_today(user_id)
        monthly_characters = TTSUsage.get_user_character_count_this_month(user_id)
        recent_requests = TTSUsage.get_recent_requests(user_id, minutes=5)
        
        usage_info = {
            'daily_requests': daily_requests,
            'monthly_requests': monthly_requests,
            'daily_characters': daily_characters,
            'monthly_characters': monthly_characters,
            'recent_requests': recent_requests
        }
        
        # Check text length
        if len(text) > self.max_message_length:
            return {
                'allowed': False,
                'reason': f'Message too long. Maximum {self.max_message_length} characters allowed.',
                'usage_info': usage_info
            }
        
        # Check rate limiting (10 requests per 5 minutes)
        if recent_requests >= self.rate_limit_requests:
            return {
                'allowed': False,
                'reason': 'Rate limit exceeded. Please wait a few minutes before trying again.',
                'usage_info': usage_info
            }
        
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
        
        if daily_characters + len(text) > self.daily_characters:
            return {
                'allowed': False,
                'reason': f'Daily character limit would be exceeded ({self.daily_characters} characters per day).',
                'usage_info': usage_info
            }
        
        # Check monthly limits
        if monthly_requests >= self.monthly_requests:
            return {
                'allowed': False,
                'reason': f'Monthly request limit reached ({self.monthly_requests} requests per month).',
                'usage_info': usage_info
            }
        
        if monthly_characters + len(text) > self.monthly_characters:
            return {
                'allowed': False,
                'reason': f'Monthly character limit would be exceeded ({self.monthly_characters} characters per month).',
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
            character_count=len(text),
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
                'characters': TTSUsage.get_user_character_count_today(user_id),
                'limit_requests': self.daily_requests,
                'limit_characters': self.daily_characters
            },
            'monthly': {
                'requests': TTSUsage.get_user_usage_this_month(user_id),
                'characters': TTSUsage.get_user_character_count_this_month(user_id),
                'limit_requests': self.monthly_requests,
                'limit_characters': self.monthly_characters
            },
            'recent': {
                'requests': TTSUsage.get_recent_requests(user_id, minutes=5),
                'limit_requests': self.rate_limit_requests
            }
        }