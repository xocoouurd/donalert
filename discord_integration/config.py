"""
Discord Configuration Management
"""
import os
from dotenv import load_dotenv

load_dotenv()

class DiscordConfig:
    """Discord bot configuration"""
    
    # Bot credentials
    BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')
    
    # Server settings
    GUILD_ID = os.getenv('DISCORD_GUILD_ID')  # Your server ID
    
    # Default channels (can be created automatically)
    DEFAULT_CHANNELS = {
        'development': 'development-updates',
        'releases': 'releases',
        'bug_reports': 'bug-reports',
        'features': 'feature-announcements',
        'general': 'general-discussion'
    }
    
    # Channel categories
    CATEGORIES = {
        'project': 'DonAlert Project',
        'development': 'Development',
        'community': 'Community'
    }
    
    # Permissions for different roles
    ROLE_PERMISSIONS = {
        'developer': {
            'send_messages': True,
            'manage_messages': True,
            'embed_links': True,
            'attach_files': True
        },
        'contributor': {
            'send_messages': True,
            'embed_links': True,
            'attach_files': True
        },
        'user': {
            'send_messages': True,
            'read_messages': True
        }
    }
    
    @classmethod
    def is_configured(cls):
        """Check if minimum configuration is present"""
        return bool(cls.BOT_TOKEN)
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("DISCORD_BOT_TOKEN not set")
            
        return errors