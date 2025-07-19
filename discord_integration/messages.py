"""
Discord Message Management
"""
import discord
from typing import Optional, Dict, List
from datetime import datetime
from .client import DiscordManager

class MessageManager:
    """Manage Discord messages"""
    
    def __init__(self, discord_manager: DiscordManager):
        self.discord = discord_manager
    
    async def send_message(self, channel_name: str, content: str, 
                          embed: Optional[Dict] = None) -> bool:
        """Send a message to a channel"""
        channel = await self.discord.get_channel(channel_name)
        if not channel:
            print(f"❌ Channel #{channel_name} not found")
            return False
            
        try:
            message_kwargs = {'content': content}
            
            if embed:
                discord_embed = self._create_embed(embed)
                message_kwargs['embed'] = discord_embed
                
            await channel.send(**message_kwargs)
            print(f"✅ Message sent to #{channel_name}")
            return True
            
        except discord.Forbidden as e:
            print(f"❌ Permission denied: Bot lacks 'Send Messages' permission - {e}")
            return False
        except discord.HTTPException as e:
            print(f"❌ Discord API error: Status {e.status}, Code {e.code} - {e.text}")
            return False
        except discord.InvalidArgument as e:
            print(f"❌ Invalid message content or embed: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error sending message: {type(e).__name__}: {e}")
            return False
    
    async def send_update(self, channel_name: str, title: str, 
                         description: str, color: str = "green") -> bool:
        """Send a formatted project update"""
        embed_data = {
            'title': title,
            'description': description,
            'color': self._get_color(color),
            'timestamp': datetime.utcnow().isoformat(),
            'footer': {'text': 'DonAlert Development'}
        }
        
        return await self.send_message(channel_name, "", embed=embed_data)
    
    async def send_release(self, channel_name: str, version: str, 
                          features: List[str], fixes: List[str] = None) -> bool:
        """Send a release announcement"""
        description = f"🚀 **Version {version} is now live!**\n\n"
        
        if features:
            description += "**✨ New Features:**\n"
            for feature in features:
                description += f"• {feature}\n"
            description += "\n"
            
        if fixes:
            description += "**🐛 Bug Fixes:**\n"
            for fix in fixes:
                description += f"• {fix}\n"
        
        embed_data = {
            'title': f"🎉 DonAlert v{version} Released",
            'description': description,
            'color': self._get_color("blue"),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return await self.send_message(channel_name, "", embed=embed_data)
    
    async def send_development_status(self, channel_name: str, 
                                    completed: List[str], 
                                    in_progress: List[str] = None,
                                    planned: List[str] = None) -> bool:
        """Send development status update"""
        description = ""
        
        if completed:
            description += "**✅ Completed:**\n"
            for item in completed:
                description += f"• {item}\n"
            description += "\n"
            
        if in_progress:
            description += "**🔄 In Progress:**\n"
            for item in in_progress:
                description += f"• {item}\n"
            description += "\n"
            
        if planned:
            description += "**📋 Planned:**\n"
            for item in planned:
                description += f"• {item}\n"
        
        embed_data = {
            'title': '📊 Development Status Update',
            'description': description,
            'color': self._get_color("orange"),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return await self.send_message(channel_name, "", embed=embed_data)
    
    def _create_embed(self, embed_data: Dict) -> discord.Embed:
        """Create Discord embed from data"""
        embed = discord.Embed(
            title=embed_data.get('title'),
            description=embed_data.get('description'),
            color=embed_data.get('color', 0x3498db)
        )
        
        if 'timestamp' in embed_data:
            embed.timestamp = datetime.fromisoformat(embed_data['timestamp'].replace('Z', '+00:00'))
            
        if 'footer' in embed_data:
            embed.set_footer(text=embed_data['footer']['text'])
            
        if 'fields' in embed_data:
            for field in embed_data['fields']:
                embed.add_field(
                    name=field['name'],
                    value=field['value'],
                    inline=field.get('inline', False)
                )
        
        return embed
    
    def _get_color(self, color_name: str) -> int:
        """Convert color name to Discord color int"""
        colors = {
            'red': 0xe74c3c,
            'green': 0x2ecc71,
            'blue': 0x3498db,
            'orange': 0xf39c12,
            'purple': 0x9b59b6,
            'gray': 0x95a5a6,
            'gold': 0xf1c40f
        }
        return colors.get(color_name.lower(), 0x3498db)