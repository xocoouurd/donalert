# Discord Bot Quick Reference

**For future Claude sessions - copy/paste these commands as needed**

## 🔌 Quick Connection Test
```bash
source venv/bin/activate && python -c "
from discord_integration.client import DiscordManager
import asyncio

async def test():
    discord = DiscordManager()
    task = asyncio.create_task(discord.connect())
    await asyncio.sleep(3)
    if discord.ready:
        print('✅ Bot connected - ready for commands!')
        await discord.disconnect()
    else:
        print('❌ Connection failed - check token')

asyncio.run(test())
"
```

## 🧪 Test Error Handling
```bash
source venv/bin/activate && python test_discord_errors.py
```

## 📢 Send Development Update
```bash
source venv/bin/activate && python -c "
import asyncio
from discord_integration.client import DiscordManager
from discord_integration.messages import MessageManager

async def update():
    discord = DiscordManager()
    messages = MessageManager(discord)
    await discord.connect()
    await asyncio.sleep(3)
    
    if discord.ready:
        await messages.send_update(
            '🚀・development-updates',
            'TITLE_HERE',
            'DESCRIPTION_HERE'
        )
        print('✅ Update sent!')
        await discord.disconnect()

asyncio.run(update())
"
```

## 🎉 Send Release Announcement  
```bash
source venv/bin/activate && python -c "
import asyncio
from discord_integration.client import DiscordManager
from discord_integration.messages import MessageManager

async def release():
    discord = DiscordManager()
    messages = MessageManager(discord)
    await discord.connect()
    await asyncio.sleep(3)
    
    if discord.ready:
        await messages.send_release(
            '📦・releases',
            'VERSION_HERE',
            ['Feature 1', 'Feature 2'],  # New features
            ['Bug fix 1', 'Bug fix 2']  # Bug fixes (optional)
        )
        print('✅ Release announced!')
        await discord.disconnect()

asyncio.run(release())
"
```

## 💬 Send Simple Message
```bash
source venv/bin/activate && python -c "
import asyncio
from discord_integration.client import DiscordManager
from discord_integration.messages import MessageManager

async def message():
    discord = DiscordManager()
    messages = MessageManager(discord)
    await discord.connect()
    await asyncio.sleep(3)
    
    if discord.ready:
        await messages.send_message(
            'CHANNEL_NAME_HERE',
            'MESSAGE_TEXT_HERE'
        )
        print('✅ Message sent!')
        await discord.disconnect()

asyncio.run(message())
"
```

## 🎮 Interactive CLI
```bash
source venv/bin/activate && python -m discord_integration.cli
```

## 📋 Channel Names Reference
- `👋・welcome`
- `📢・announcements` 
- `💬・general-chat`
- `🚀・development-updates`
- `💡・feature-requests`
- `🐛・bug-reports`
- `👨‍💻・code-reviews`
- `🔧・technical-discussion`
- `🗺️・roadmap`
- `📦・releases`
- `🧪・testing`
- `🚀・deployment`
- `🎨・showcase`
- `💭・feedback`
- `🆘・support`

## 🚨 If Bot Seems Disconnected
1. Check `.env` file has `DISCORD_BOT_TOKEN=...`
2. Run connection test above
3. If failed, verify token in Discord Developer Portal
4. Check bot is still in server

## 📝 Common Claude Commands
- "Send an update about the marathon system to development-updates"
- "Post a release announcement for version 2.1.0"  
- "Send a message to announcements about the new features"
- "Create a development status update"
- "Start the Discord CLI"