"""
Discord Bot Client
"""
import discord
import asyncio
from typing import Optional, List, Dict, TYPE_CHECKING
from .config import DiscordConfig

if TYPE_CHECKING:
    from discord import Guild, TextChannel

class DiscordManager:
    """Main Discord bot manager"""
    
    def __init__(self):
        self.client = None
        self.ready = False
        
    async def connect(self) -> bool:
        """Connect to Discord"""
        if not DiscordConfig.is_configured():
            print("❌ Discord not configured. Set DISCORD_BOT_TOKEN in .env")
            return False
            
        intents = discord.Intents.default()
        # Don't use privileged intents for now
        intents.message_content = False
        intents.guilds = True
        
        self.client = discord.Client(intents=intents)
        
        @self.client.event
        async def on_ready():
            print(f"✅ Connected as {self.client.user}")
            self.ready = True
            
        try:
            await self.client.start(DiscordConfig.BOT_TOKEN)
        except discord.LoginFailure as e:
            print(f"❌ Discord login failed: Invalid bot token - {e}")
            return False
        except discord.HTTPException as e:
            print(f"❌ Discord HTTP error: Status {e.status}, Code {e.code} - {e.text}")
            return False
        except discord.ConnectionClosed as e:
            print(f"❌ Discord connection closed: Code {e.code}, Reason: {e.reason}")
            return False
        except asyncio.TimeoutError:
            print("❌ Discord connection timeout: Check internet connection")
            return False
        except Exception as e:
            print(f"❌ Unexpected Discord error: {type(e).__name__}: {e}")
            return False
            
        return True
    
    async def disconnect(self):
        """Disconnect from Discord"""
        if self.client:
            await self.client.close()
            self.ready = False
    
    def get_guild(self) -> Optional["Guild"]:
        """Get the configured guild"""
        if not self.ready:
            return None
            
        if DiscordConfig.GUILD_ID:
            return self.client.get_guild(int(DiscordConfig.GUILD_ID))
        else:
            # Return first guild if no specific one configured
            guilds = self.client.guilds
            return guilds[0] if guilds else None
    
    async def list_guilds(self) -> List[Dict]:
        """List all guilds the bot is in"""
        if not self.ready:
            return []
            
        guilds = []
        for guild in self.client.guilds:
            guilds.append({
                'id': guild.id,
                'name': guild.name,
                'member_count': guild.member_count
            })
        return guilds
    
    async def list_channels(self, guild_id: Optional[int] = None) -> List[Dict]:
        """List channels in a guild"""
        if not self.ready:
            return []
            
        guild = self.get_guild() if not guild_id else self.client.get_guild(guild_id)
        if not guild:
            return []
            
        channels = []
        for channel in guild.text_channels:
            channels.append({
                'id': channel.id,
                'name': channel.name,
                'category': channel.category.name if channel.category else None,
                'topic': channel.topic
            })
        return channels
    
    async def get_channel(self, channel_name: str) -> Optional["TextChannel"]:
        """Get channel by name"""
        guild = self.get_guild()
        if not guild:
            return None
            
        for channel in guild.text_channels:
            if channel.name == channel_name:
                return channel
        return None