# DonAlert Discord Server Documentation

This document provides complete documentation of the DonAlert Discord server structure, bot integration, and management capabilities.

## 📋 Table of Contents

1. [Server Overview](#server-overview)
2. [Channel Structure](#channel-structure)
3. [Bot Integration](#bot-integration)
4. [Management Commands](#management-commands)
5. [Future Sessions Setup](#future-sessions-setup)
6. [Troubleshooting](#troubleshooting)

---

## 🏠 Server Overview

**Server Name:** Donation Alert  
**Members:** 10  
**Bot:** DonAlert Bot#5802  
**Purpose:** Development and community hub for the DonAlert donation alert system

### Key Features
- Professional development workflow structure
- Automated bot integration for updates
- Multi-category organization
- Icon-based visual navigation
- Comprehensive welcome and documentation

---

## 📁 Channel Structure

### **📁 GENERAL Category**
| Channel | Purpose | Topic |
|---------|---------|-------|
| 👋・тавтай-морил | New member onboarding | Welcome new members and learn about DonAlert |
| 📢・мэдээллүүд | Important updates | Important project announcements and news |
| 💬・ерөнхий-чат | Community discussion | General discussion about DonAlert development |

### **📁 DEVELOPMENT Category**
| Channel | Purpose | Topic |
|---------|---------|-------|
| 🚀・хөгжүүлэлтийн-шинэчлэл | Progress tracking | Real-time development progress and feature updates |
| 💡・онцлог-хүсэлт | Enhancement ideas | Suggest new features and improvements for DonAlert |
| 🐛・алдааны-мэдээлэл | Issue tracking | Report bugs, issues, and technical problems |
| 👨‍💻・код-шүүмж | Code quality | Code review discussions and pull request reviews |
| 🔧・техникийн-хэлэлцүүлэг | Architecture talks | Technical architecture and implementation discussions |
| 🗺️・замын-зураг | Development planning | Planned feature additions and development roadmap for DonAlert |

### **📁 RELEASES Category**
| Channel | Purpose | Topic |
|---------|---------|-------|
| 📦・хувилбарууд | Version announcements | Version releases, changelogs, and deployment announcements |
| 🧪・туршилт | QA and beta | Beta testing, QA feedback, and test results |
| 🚀・нэвтрүүлэлт | Infrastructure | Deployment status, server updates, and infrastructure |

### **📁 COMMUNITY Category**
| Channel | Purpose | Topic |
|---------|---------|-------|
| 🎨・үзүүлэнг | User creations | Show off your DonAlert setups and customizations |
| 💭・санал-хүсэлт | User input | User feedback, suggestions, and improvement ideas |
| 🆘・тусламж | Help desk | Get help with using and configuring DonAlert |

### **📁 📢 Мэдээлэл Category** (Legacy - Protected Channels)
These channels remain from the original setup and cannot be deleted by the bot due to permissions:
- угтах
- мэдээ-мэдээлэл  
- системийн-шинэчлэл
- түгээмэл-асуултууд
- шинээр-нэмэгдэх-зүйлс

---

## 🤖 Bot Integration

### **Bot Details**
- **Name:** DonAlert Bot#5802
- **Token:** Stored in `.env` as `DISCORD_BOT_TOKEN`
- **Permissions:** Channel management, message sending, embed links
- **Location:** `/srv/www/donalert.invictamotus.com/discord_integration/`

### **Bot Capabilities**
- ✅ Create/delete channels
- ✅ Edit channel names and topics
- ✅ Send messages and embeds
- ✅ Manage categories
- ✅ Send formatted updates
- ✅ Post release announcements
- ✅ Interactive CLI management

### **Module Structure**
```
discord_integration/
├── __init__.py         # Module initialization
├── config.py           # Bot configuration and settings
├── client.py           # Discord client wrapper
├── channels.py         # Channel management functions
├── messages.py         # Message and embed management
├── cli.py              # Interactive command-line interface
├── SERVER_DOCUMENTATION.md  # This documentation
└── README.md           # Quick setup guide
```

---

## 🎮 Management Commands

### **Quick Commands for Future Sessions**

#### **Connection Test**
```bash
source venv/bin/activate && python -c "
from discord_integration.client import DiscordManager
import asyncio

async def test():
    discord = DiscordManager()
    task = asyncio.create_task(discord.connect())
    await asyncio.sleep(3)
    if discord.ready:
        print('✅ Bot connected successfully')
        guilds = await discord.list_guilds()
        print(f'📊 Connected to {len(guilds)} servers')
        await discord.disconnect()
    else:
        print('❌ Connection failed')

asyncio.run(test())
"
```

#### **Send Development Update**
```bash
python -c "
import asyncio
from discord_integration.client import DiscordManager
from discord_integration.messages import MessageManager

async def send_update():
    discord = DiscordManager()
    messages = MessageManager(discord)
    
    await discord.connect()
    await asyncio.sleep(3)
    
    if discord.ready:
        await messages.send_update(
            '🚀・хөгжүүлэлтийн-шинэчлэл',
            'Feature Completed',
            'Description of what was completed'
        )
        await discord.disconnect()
    
asyncio.run(send_update())
"
```

#### **Interactive CLI Mode**
```bash
source venv/bin/activate && python -m discord_integration.cli
```

### **Available Message Types**

#### **Development Updates**
```python
await messages.send_update(
    channel_name='🚀・хөгжүүлэлтийн-шинэчлэл',
    title='Marathon System Enhanced',
    description='Added real-time countdown and notification system',
    color='green'
)
```

#### **Release Announcements**
```python
await messages.send_release(
    channel_name='📦・хувилбарууд',
    version='2.1.0',
    features=['Marathon system', 'UI improvements'],
    fixes=['Dropdown styling', 'Database migration issues']
)
```

#### **Development Status**
```python
await messages.send_development_status(
    channel_name='🚀・хөгжүүлэлтийн-шинэчлэл',
    completed=['Marathon system', 'Discord integration'],
    in_progress=['Analytics dashboard', 'Mobile optimization'],
    planned=['API documentation', 'Plugin system']
)
```

---

## 🚀 Future Sessions Setup

### **Quick Start Checklist**
1. ✅ Activate virtual environment: `source venv/bin/activate`
2. ✅ Verify bot token in `.env`: `DISCORD_BOT_TOKEN=...`
3. ✅ Test connection: Run connection test command above
4. ✅ Ready for commands!

### **Common Use Cases**

#### **Post Project Milestone**
*"Send an update to development-updates about completing the user dashboard"*

#### **Announce New Release**  
*"Post a release announcement for version 2.2.0 with the new features we added"*

#### **Share Development Status**
*"Post our current development status showing what's completed and what's next"*

#### **Create New Channel**
*"Create a new channel called api-documentation in the Development category"*

#### **Send Community Update**
*"Send a message to announcements about the new Discord server structure"*

### **Claude Commands Reference**

Just tell Claude natural language commands like:
- "Send a development update about the marathon feature"
- "Post a release announcement for version 2.1.0"
- "Create a channel for API discussions"
- "Send a welcome message to the new server structure"
- "Start the Discord CLI for interactive management"

---

## ⚙️ Configuration

### **Environment Variables**
```env
# In /srv/www/donalert.invictamotus.com/.env
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here  # Optional
```

### **Bot Permissions Required**
- Manage Channels
- Send Messages
- Manage Messages
- Embed Links
- Read Message History
- Use Slash Commands

### **Dependencies**
```bash
# Installed in existing venv
pip install discord.py
```

---

## 🔧 Troubleshooting

### **Common Issues**

#### **"Module 'discord' has no attribute 'Intents'"**
- **Cause:** Local folder named 'discord' conflicts with discord.py
- **Solution:** Folder renamed to 'discord_integration' ✅ Fixed

#### **"403 Forbidden: Missing Permissions"**
- **Cause:** Bot lacks required permissions
- **Solution:** Check bot permissions in Discord Developer Portal

#### **"Connection timeout"**
- **Cause:** Network issues or invalid token
- **Solution:** Verify token and internet connection

#### **"No guild found"**
- **Cause:** Bot not added to server or wrong server ID
- **Solution:** Re-invite bot or check DISCORD_GUILD_ID

### **Debug Commands**
```bash
# Test Discord.py installation
python -c "import discord; print(discord.__version__)"

# Verify configuration
python -c "from discord_integration.config import DiscordConfig; print(DiscordConfig.validate())"

# Check bot token (first 20 chars)
python -c "from discord_integration.config import DiscordConfig; print(DiscordConfig.BOT_TOKEN[:20] + '...')"
```

---

## 📝 Change Log

### **2025-07-19 - Initial Setup**
- ✅ Created Discord bot integration
- ✅ Set up professional channel structure
- ✅ Added icons and descriptions to all channels
- ✅ Implemented automated messaging system
- ✅ Created comprehensive documentation
- ✅ Removed old channels and empty categories
- ✅ Set up welcome and announcement channels

### **Current Status**
- 🏠 **Server:** Fully organized with 14 channels across 4 categories
- 🤖 **Bot:** Connected and functional with full management capabilities
- 📋 **Documentation:** Complete setup and usage guide
- 🔧 **Integration:** Ready for automated development updates

---

## 🔐 Channel Permissions Setup

### **Required Permission Structure**

**Read-Only Channels (Only developers and bot can post):**
- `📢・мэдээллүүд` - Important project announcements
- `🚀・хөгжүүлэлтийн-шинэчлэл` - Development progress updates  
- `🐛・алдааны-мэдээлэл` - Bug reports and issues
- `👨‍💻・код-шүүмж` - Code review discussions
- `🗺️・замын-зураг` - Planned feature additions and development roadmap
- `📦・хувилбарууд` - Version releases and changelogs
- `🧪・туршилт` - Testing reports and QA feedback
- `🚀・нэвтрүүлэлт` - Deployment status and infrastructure

**Interactive Channels (Users can participate):**
- `👋・тавтай-морил` - Welcome messages and introductions
- `💬・ерөнхий-чат` - General discussions
- `💡・онцлог-хүсэлт` - Feature suggestions from users
- `🔧・техникийн-хэлэлцүүлэг` - Technical architecture discussions
- `🎨・үзүүлэнг` - User setups and customizations
- `💭・санал-хүсэлт` - User feedback and suggestions
- `🆘・тусламж` - Help and assistance for users

### **Manual Permission Setup**

For each **read-only channel**:
1. Right-click channel → Edit Channel
2. Go to Permissions tab
3. Click on @everyone role
4. Set the following permissions:
   - ✅ View Channel: Allow
   - ✅ Read Message History: Allow
   - ✅ Add Reactions: Allow
   - ❌ Send Messages: Deny
   - ❌ Create Public Threads: Deny
   - ❌ Send Messages in Threads: Deny

For each **interactive channel**:
1. Ensure @everyone has default permissions:
   - ✅ View Channel: Allow
   - ✅ Send Messages: Allow
   - ✅ Read Message History: Allow
   - ✅ Add Reactions: Allow
   - ✅ Create Public Threads: Allow
   - ✅ Send Messages in Threads: Allow

### **Bot Permissions Required**
The DonAlert Bot needs the following permissions in all channels:
- Manage Channels
- Send Messages
- Manage Messages
- Embed Links
- Read Message History
- Use External Emojis
- Add Reactions

## ✅ Permissions Implementation Status

**Successfully Configured (2025-07-19):**
- ✅ **Read-only channels**: @everyone can only read/react, Developer role can post
- ✅ **Interactive channels**: All users can participate normally
- ✅ **Role hierarchy**: Master Bot (admin) → Developer → @everyone
- ✅ **Automated setup**: Bot can manage permissions programmatically

**Channel Permission Summary:**
- **8 development channels** → Read-only for users, writable for developers
- **7 community channels** → Interactive for all users
- **Permission verification** → All channels tested and working correctly

## 🎯 Next Steps

### **Potential Enhancements**
- [x] Set up role-based permissions
- [x] Implement automated permission management
- [ ] Create automated deployment notifications
- [ ] Add GitHub webhook integration
- [ ] Set up scheduled status updates
- [ ] Create custom slash commands
- [ ] Add reaction role system

### **Integration Opportunities**
- [ ] Connect with Flask app for real-time notifications
- [ ] Integrate with marathon system for status updates
- [ ] Add donation milestone celebrations
- [ ] Create automated changelog posting
- [ ] Set up error monitoring alerts

---

*Last updated: 2025-07-19*  
*Maintained by: Claude Code Assistant*