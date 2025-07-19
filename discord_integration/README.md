# Discord Integration Module

This is a **modular Discord integration** for the DonAlert project - it's **NOT** a separate project.

## Structure

```
discord/
├── __init__.py         # Module initialization
├── config.py           # Configuration management
├── client.py           # Discord client wrapper  
├── channels.py         # Channel management
├── messages.py         # Message sending
├── cli.py              # Interactive CLI
└── README.md           # This file
```

## Integration with DonAlert

- ✅ **Same virtual environment** as the main Flask app
- ✅ **Same .env file** for configuration
- ✅ **Modular design** - doesn't clutter main project
- ✅ **Can import into Flask app** if needed later

## Usage

From the main project directory:

```bash
# Activate the same venv
source venv/bin/activate

# Install Discord.py in the existing venv
pip install discord.py

# Run the Discord CLI
python -m discord.cli
```

## Configuration

Add to your existing `.env` file:

```env
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here  # Optional
```

## Future Integration

This module can later be imported into your Flask app:

```python
# In your Flask app
from discord.messages import MessageManager
from discord.client import DiscordManager

# Send updates from your app
discord_manager = DiscordManager()
message_manager = MessageManager(discord_manager)
await message_manager.send_update("development", "New Feature", "Marathon system deployed!")
```

**This is just a clean, organized way to add Discord functionality to your existing project without cluttering the main codebase.**