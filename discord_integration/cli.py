"""
Discord CLI Interface
Interactive command-line interface for Discord management
"""
import asyncio
from typing import List
from .client import DiscordManager
from .channels import ChannelManager  
from .messages import MessageManager
from .config import DiscordConfig

class DiscordCLI:
    """Command-line interface for Discord management"""
    
    def __init__(self):
        self.discord = DiscordManager()
        self.channels = ChannelManager(self.discord)
        self.messages = MessageManager(self.discord)
        self.connected = False
    
    async def start(self):
        """Start the Discord CLI"""
        print("🤖 Discord Management CLI")
        print("=" * 40)
        
        # Check configuration
        errors = DiscordConfig.validate()
        if errors:
            print("❌ Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return
        
        # Connect to Discord
        print("🔗 Connecting to Discord...")
        try:
            # Start connection in background
            connection_task = asyncio.create_task(self.discord.connect())
            
            # Wait for connection with timeout
            await asyncio.wait_for(asyncio.sleep(3), timeout=5)
            
            if self.discord.ready:
                self.connected = True
                print("✅ Connected successfully!")
                await self._show_server_info()
                await self._interactive_mode()
            else:
                print("❌ Connection failed or timed out")
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
        finally:
            await self.discord.disconnect()
    
    async def _show_server_info(self):
        """Show basic server information"""
        guilds = await self.discord.list_guilds()
        if guilds:
            print(f"\n🏠 Connected to {len(guilds)} server(s):")
            for guild in guilds:
                print(f"  • {guild['name']} ({guild['member_count']} members)")
        
        channels = await self.discord.list_channels()
        if channels:
            print(f"\n💬 Available channels:")
            for channel in channels[:10]:  # Show first 10
                category = f" [{channel['category']}]" if channel['category'] else ""
                print(f"  • #{channel['name']}{category}")
            if len(channels) > 10:
                print(f"  ... and {len(channels) - 10} more")
        print()
    
    async def _interactive_mode(self):
        """Interactive command mode"""
        print("🎮 Interactive Mode")
        print("Commands:")
        print("  help                           - Show this help")
        print("  list channels                  - List all channels")  
        print("  list guilds                    - List all servers")
        print("  create channel <name>          - Create new channel")
        print("  delete channel <name>          - Delete channel")
        print("  send <channel> <message>       - Send message")
        print("  update <channel> <title> <msg> - Send update")
        print("  release <channel> <version>    - Send release note")
        print("  quit                           - Exit")
        print()
        
        while self.connected:
            try:
                command = input("Discord> ").strip()
                await self._handle_command(command)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("\n👋 Disconnecting...")
    
    async def _handle_command(self, command: str):
        """Handle interactive commands"""
        parts = command.split()
        if not parts:
            return
            
        cmd = parts[0].lower()
        
        if cmd == 'quit':
            self.connected = False
            
        elif cmd == 'help':
            await self._show_help()
            
        elif cmd == 'list':
            if len(parts) > 1:
                if parts[1] == 'channels':
                    await self._list_channels()
                elif parts[1] == 'guilds':
                    await self._list_guilds()
                else:
                    print("❌ Usage: list [channels|guilds]")
            else:
                print("❌ Usage: list [channels|guilds]")
                
        elif cmd == 'create':
            if len(parts) >= 3 and parts[1] == 'channel':
                channel_name = parts[2]
                await self.channels.create_channel(channel_name)
            else:
                print("❌ Usage: create channel <name>")
                
        elif cmd == 'delete':
            if len(parts) >= 3 and parts[1] == 'channel':
                channel_name = parts[2]
                await self.channels.delete_channel(channel_name)
            else:
                print("❌ Usage: delete channel <name>")
                
        elif cmd == 'send':
            if len(parts) >= 3:
                channel_name = parts[1]
                message = ' '.join(parts[2:])
                await self.messages.send_message(channel_name, message)
            else:
                print("❌ Usage: send <channel> <message>")
                
        elif cmd == 'update':
            if len(parts) >= 4:
                channel_name = parts[1]
                title = parts[2]
                description = ' '.join(parts[3:])
                await self.messages.send_update(channel_name, title, description)
            else:
                print("❌ Usage: update <channel> <title> <description>")
                
        elif cmd == 'release':
            if len(parts) >= 3:
                channel_name = parts[1]
                version = parts[2]
                
                # Example features (you could make this interactive)
                features = ["Marathon system improvements", "UI enhancements"]
                await self.messages.send_release(channel_name, version, features)
            else:
                print("❌ Usage: release <channel> <version>")
                
        else:
            print(f"❌ Unknown command: {cmd}. Type 'help' for available commands.")
    
    async def _show_help(self):
        """Show detailed help"""
        print("\n📚 Discord Management Commands:")
        print("  list channels                  - Show all channels in current server")
        print("  list guilds                    - Show all servers bot is connected to")
        print("  create channel <name>          - Create a new text channel")
        print("  delete channel <name>          - Delete an existing channel")
        print("  send <channel> <message>       - Send a simple message")
        print("  update <channel> <title> <msg> - Send formatted development update")
        print("  release <channel> <version>    - Send release announcement")
        print("  help                           - Show this help message")
        print("  quit                           - Exit the CLI")
        print()
    
    async def _list_channels(self):
        """List all channels"""
        channels = await self.discord.list_channels()
        if channels:
            print("\n💬 Channels:")
            for channel in channels:
                category = f" [{channel['category']}]" if channel['category'] else ""
                topic = f" - {channel['topic']}" if channel['topic'] else ""
                print(f"  #{channel['name']}{category}{topic}")
        else:
            print("❌ No channels found")
        print()
    
    async def _list_guilds(self):
        """List all guilds"""
        guilds = await self.discord.list_guilds()
        if guilds:
            print("\n🏠 Servers:")
            for guild in guilds:
                print(f"  {guild['name']} (ID: {guild['id']}, {guild['member_count']} members)")
        else:
            print("❌ No servers found")
        print()

# Main function to run CLI
async def run_cli():
    """Run the Discord CLI"""
    cli = DiscordCLI()
    await cli.start()

if __name__ == "__main__":
    asyncio.run(run_cli())