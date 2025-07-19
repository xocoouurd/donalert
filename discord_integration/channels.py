"""
Discord Channel Management
"""
import discord
from typing import Optional, Dict, List
from .client import DiscordManager

class ChannelManager:
    """Manage Discord channels"""
    
    def __init__(self, discord_manager: DiscordManager):
        self.discord = discord_manager
    
    async def create_channel(self, name: str, category: Optional[str] = None, 
                           topic: Optional[str] = None) -> bool:
        """Create a new text channel"""
        guild = self.discord.get_guild()
        if not guild:
            print("❌ No guild found")
            return False
            
        try:
            # Get or create category
            category_obj = None
            if category:
                category_obj = await self._get_or_create_category(guild, category)
            
            # Create channel
            channel = await guild.create_text_channel(
                name=name,
                category=category_obj,
                topic=topic
            )
            
            print(f"✅ Created channel #{channel.name}")
            return True
            
        except discord.Forbidden as e:
            print(f"❌ Permission denied: Bot lacks 'Manage Channels' permission - {e}")
            return False
        except discord.HTTPException as e:
            print(f"❌ Discord API error: Status {e.status}, Code {e.code} - {e.text}")
            return False
        except ValueError as e:
            print(f"❌ Invalid channel name or parameters: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error creating channel: {type(e).__name__}: {e}")
            return False
    
    async def delete_channel(self, name: str) -> bool:
        """Delete a channel by name"""
        channel = await self.discord.get_channel(name)
        if not channel:
            print(f"❌ Channel #{name} not found")
            return False
            
        try:
            await channel.delete()
            print(f"✅ Deleted channel #{name}")
            return True
        except discord.Forbidden as e:
            print(f"❌ Permission denied: Bot lacks permission to delete channels - {e}")
            return False
        except discord.NotFound as e:
            print(f"❌ Channel not found or already deleted - {e}")
            return False
        except discord.HTTPException as e:
            print(f"❌ Discord API error: Status {e.status}, Code {e.code} - {e.text}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error deleting channel: {type(e).__name__}: {e}")
            return False
    
    async def edit_channel(self, name: str, new_name: Optional[str] = None,
                          topic: Optional[str] = None) -> bool:
        """Edit channel properties"""
        channel = await self.discord.get_channel(name)
        if not channel:
            print(f"❌ Channel #{name} not found")
            return False
            
        try:
            await channel.edit(
                name=new_name or channel.name,
                topic=topic
            )
            print(f"✅ Updated channel #{channel.name}")
            return True
        except discord.Forbidden as e:
            print(f"❌ Permission denied: Bot lacks permission to edit channels - {e}")
            return False
        except discord.NotFound as e:
            print(f"❌ Channel not found - {e}")
            return False
        except discord.HTTPException as e:
            print(f"❌ Discord API error: Status {e.status}, Code {e.code} - {e.text}")
            return False
        except ValueError as e:
            print(f"❌ Invalid channel parameters: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error editing channel: {type(e).__name__}: {e}")
            return False
    
    async def set_channel_permissions(self, channel_name: str, role_name: str,
                                    permissions: Dict[str, bool]) -> bool:
        """Set permissions for a role in a channel"""
        guild = self.discord.get_guild()
        if not guild:
            return False
            
        channel = await self.discord.get_channel(channel_name)
        if not channel:
            print(f"❌ Channel #{channel_name} not found")
            return False
            
        # Find role
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            print(f"❌ Role '{role_name}' not found")
            return False
            
        try:
            # Convert permissions dict to PermissionOverwrite
            overwrite = discord.PermissionOverwrite()
            for perm, value in permissions.items():
                setattr(overwrite, perm, value)
                
            await channel.set_permissions(role, overwrite=overwrite)
            print(f"✅ Set permissions for '{role_name}' in #{channel_name}")
            return True
            
        except discord.Forbidden as e:
            print(f"❌ Permission denied: Bot lacks 'Manage Roles' permission - {e}")
            return False
        except discord.NotFound as e:
            print(f"❌ Channel or role not found - {e}")
            return False
        except discord.HTTPException as e:
            print(f"❌ Discord API error: Status {e.status}, Code {e.code} - {e.text}")
            return False
        except ValueError as e:
            print(f"❌ Invalid permission parameters: {e}")
            return False
        except AttributeError as e:
            print(f"❌ Invalid permission name: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error setting permissions: {type(e).__name__}: {e}")
            return False
    
    async def _get_or_create_category(self, guild: discord.Guild, 
                                    category_name: str) -> discord.CategoryChannel:
        """Get existing category or create new one"""
        # Look for existing category
        for category in guild.categories:
            if category.name == category_name:
                return category
                
        # Create new category
        return await guild.create_category(category_name)
    
    async def list_categories(self) -> List[Dict]:
        """List all categories in the guild"""
        guild = self.discord.get_guild()
        if not guild:
            return []
            
        categories = []
        for category in guild.categories:
            categories.append({
                'id': category.id,
                'name': category.name,
                'channels': [ch.name for ch in category.channels]
            })
        return categories