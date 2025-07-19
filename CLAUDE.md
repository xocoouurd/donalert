# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Environment Setup:**
```bash
source venv/bin/activate  # Activate virtual environment
pip install -r requirements.txt  # Install dependencies
```

**Running the Application:**
```bash
python run.py  # Start Flask development server on localhost:5000
```

**Database Operations:**
```bash
flask db init      # Initialize migration repository (first time only)
flask db migrate   # Generate migration files after model changes
flask db upgrade   # Apply migrations to database
flask db downgrade # Rollback last migration
```

## Architecture Overview

This Flask donation alert platform uses the **Application Factory Pattern** with modular blueprint architecture. The system provides comprehensive donation management, analytics, and real-time streaming integration for content creators. Key architectural components:

### Application Factory (`app/__init__.py`)
- `create_app()` function initializes Flask app and extensions
- Extensions (SQLAlchemy, Flask-Login, Flask-Migrate, SocketIO) initialized using `init_app()` pattern
- Blueprints registered in factory function
- Login manager configured for authentication flow

### Extension Management (`app/extensions.py`)
- Singleton pattern for extension instances: `db`, `login_manager`, `migrate`, `socketio`
- Prevents circular imports and ensures consistent access across modules
- Extensions imported into factory and individual modules as needed

### Configuration System (`config.py`)
- Single `Config` class with environment-based settings
- Uses `python-dotenv` for `.env` file loading
- Database: MySQL with PyMySQL connector
- File uploads: Pillow for image processing, configurable size/type restrictions
- Security: Environment variable-based secret management

### Technology Stack
- **Flask 3.0.0** with SQLAlchemy ORM
- **MySQL database** with PyMySQL connector
- **Flask-SocketIO** for real-time features
- **Flask-Login** for authentication
- **Flask-Migrate** for database schema management
- **Pillow** for image processing

## Complete Feature Documentation

### 1. Donation Alert System
**Core real-time donation alerts with comprehensive customization**
- WebSocket-based real-time alerts to streamer overlays
- Multiple animation effects (fade, slide, zoom, bounce)
- Custom GIF and sound upload support
- Font, color, and positioning customization
- Minimum amount thresholds for alerts
- TTS integration with Mongolian voice synthesis
- Platform-specific donor identification and avatars

### 2. Income Dashboard & Analytics
**Professional revenue tracking and analytics platform**
- Real-time donation statistics (total, average, count)
- Visual analytics with Chart.js trend visualization
- Comprehensive donation history with search/filter
- Top donors leaderboard with contribution tracking
- Export capabilities for financial record keeping
- Revenue trend analysis and projections
- Performance metrics and growth tracking

### 3. Donation Goal Tracker
**Visual goal tracking with real-time progress updates**
- Dynamic goal setting with customizable targets
- Real-time progress updates from donations
- Manual adjustment capabilities for offline donations
- Visual customization (fonts, colors, animations)
- Progress bar styling and animation effects
- OBS overlay integration with responsive design
- Goal reset and total amount override features

### 4. Public Donation System
**Viewer-facing donation pages with integrated payments**
- Shareable donation URLs for each streamer
- Guest donation support (no account required)
- Authenticated donations with platform integration
- QPay payment processing with QR codes
- Bank app integration for mobile payments
- Real-time donation feed for public viewing
- Mobile-optimized responsive design

### 5. Marathon System
**Time-based donation system with countdown timers**
- Configurable price per minute system
- Real-time countdown timer with WebSocket sync
- Manual time controls (add/remove/pause/resume/reset)
- Automatic time addition from donations
- Visual timer customization (fonts, colors, effects)
- Animation effects (pulse, bounce, glow, shake)
- Status tracking and accumulated donation totals

### 6. Multi-Platform OAuth Integration
**Seamless integration with major streaming platforms**
- Twitch, YouTube, and Kick OAuth support
- Primary platform designation system
- Multiple platform connection management
- Platform-specific profile picture integration
- Authenticated donation linking to platforms
- Platform indicator displays throughout UI

### 7. Subscription Management
**Comprehensive subscription and payment system**
- Multiple subscription tiers (Monthly, Quarterly, Annual)
- QPay payment integration with Mongolian banks
- Free trial system for new users
- 24-hour grace period for expired subscriptions
- Auto-renewal capabilities
- Subscription status tracking and notifications

### 8. Bank Account Management
**Secure bank account integration for payments**
- IBAN validation for Mongolian bank format
- Bank logo display and selection system
- QPay bank code integration
- Secure account verification process
- Payment history tracking per bank account

### 9. Mongolian TTS Integration
**Advanced text-to-speech with usage management**
- Chimege API integration for Mongolian voices
- Multiple voice options with pre-generated samples
- Usage tracking and rate limiting system
- Speed and pitch control for voice customization
- Automatic audio file cleanup after playback
- Message-only TTS for donation alerts

### 10. Discord Community Management
**Professional Discord server with automated management**
- Automated bot for development updates
- 14 organized channels across 4 categories
- Real-time development progress notifications
- Interactive CLI for server management
- Professional channel structure with icons
- Comprehensive documentation system

## Development Patterns

### Blueprint Structure
When creating new features, follow the modular blueprint pattern:
- Create blueprint in separate module (e.g., `app/auth/routes.py`)
- Register blueprint in `create_app()` function
- Use `@login_required` decorator for protected routes
- Separate API endpoints from HTML template rendering

### Model Design
- Define models in separate files by feature area
- Use SQLAlchemy relationships with proper cascade options
- Import all models in `app/__init__.py` for migration detection
- Follow foreign key naming conventions

### File Upload Handling
- Use UUID-based filenames to prevent conflicts
- Implement size and format validation per `config.py` settings
- Store uploads in organized subdirectories by content type
- Use Pillow for automatic image resizing/optimization

### Database Migration Workflow
1. Modify models in code
2. Run `flask db migrate -m "description"` to generate migration
3. Review generated migration file
4. Run `flask db upgrade` to apply changes
5. Commit both model changes and migration files

## Configuration Requirements

Update `.env` file with actual values before running:
- `SECRET_KEY`: Generate secure random key for production
- Database credentials: `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`
- Upload settings: `UPLOAD_FOLDER`, `MAX_IMAGE_SIZE_MB`
- Server config: `SERVER_NAME`, `PREFERRED_URL_SCHEME` (for production)

## Localization Requirements

**Language Policy:**
- **Frontend Text**: All user-facing text must be in Mongolian (Монгол)
- **Backend Values**: All backend logs, variable names, comments, and internal values must remain in English for developer understanding
- **Database**: Store data in English but display in Mongolian
- **Error Messages**: User-facing errors in Mongolian, technical logs in English

**Implementation Notes:**
- Use Mongolian Cyrillic script for all UI elements
- Maintain English for technical documentation and code comments
- Keep API responses in English format but translate display values
- Flash messages and user notifications must be in Mongolian

## Design System

**Visual Design Philosophy:**
- **Glass morphism aesthetic** - translucent cards with backdrop blur effects
- **Clean, minimal layout** - plenty of white space, simple and focused
- **Techy typography** - Inter font for UI, JetBrains Mono for code/brand elements
- **Gradient background** - consistent purple/blue gradient throughout the site
- **No scrolling homepage** - content fits exactly in viewport (navbar + content + footer)

**Key Design Elements:**
- `.glass-card` class for all content containers
- Consistent color scheme using CSS custom properties
- FontAwesome icons throughout
- Smooth hover animations and micro-interactions
- Fixed navbar (transparent with blur) and footer
- Responsive design for mobile devices

**Design Implementation:**
- Main gradient: `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- Glass cards: `background: rgba(255, 255, 255, 0.25)` with `backdrop-filter: blur(20px)`
- Primary color: `#6366f1` (indigo)
- Typography: Inter (UI), JetBrains Mono (monospace/brand)

**Layout Structure:**
- Fixed navbar with glass effect
- Content area calculated as `calc(100vh - navbar - footer)`
- Fixed footer at bottom
- No page scrolling on main pages

## CSS Architecture

**Complete Styling System (8 CSS Files):**
- `app/static/css/style.css` - Global styles and base components
- `app/static/css/donation-alert.css` - Alert settings page styling
- `app/static/css/overlay.css` - Alert overlay for OBS integration
- `app/static/css/donate.css` - Public donation page styling
- `app/static/css/donations-history.css` - Income dashboard styling
- `app/static/css/donation-goal.css` - Goal settings page styling
- `app/static/css/goal-overlay.css` - Goal overlay for OBS integration
- `app/static/css/marathon.css` - Marathon system styling

**CSS Scoping Strategy:**
- Global styles in `style.css` for cross-page components
- Page-specific styles in separate files to avoid conflicts
- Modal-specific overrides for Bootstrap components
- Body class-based exclusions (`body:not(.bank-account-page)`) for conflicting styles

**Dropdown Management:**
- Bootstrap's default dropdown arrows removed globally with `.dropdown-toggle::after { display: none !important; }`
- Custom arrows added where needed (navbar dropdown)
- Manual FontAwesome icons preserved (bank account dropdown)
- Form select elements get proper background-image arrows with SVG data URLs

**CSS Loading Pattern:**
```html
<!-- base.html -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
{% block head %}{% endblock %}

<!-- donation_alert.html -->
{% block head %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/donation-alert.css') }}">
{% endblock %}
```

## Technical Architecture

### Database Schema (12 Models)
- **User Management**: `user.py`, `platform_connection.py`, `user_asset.py`
- **Donations**: `donation.py`, `donation_payment.py`, `donation_alert_settings.py`
- **Goals & Marathon**: `donation_goal.py`, `marathon.py`
- **Subscriptions**: `subscription.py`, `subscription_payment.py`
- **Systems**: `tts_usage.py`

### Route Architecture (4 Blueprints)
- **Main Routes**: Core application logic, marathon API, donation processing
- **Authentication**: User registration, login, session management
- **OAuth**: Platform integration (Twitch, YouTube, Kick)
- **TTS**: Mongolian text-to-speech processing

### Frontend Architecture (8 CSS Files)
- **Global**: `style.css` - Base styling and components
- **Donation System**: `donation-alert.css`, `overlay.css`
- **Public Pages**: `donate.css` for viewer-facing pages
- **Analytics**: `donations-history.css` for income dashboard
- **Goals**: `donation-goal.css`, `goal-overlay.css`
- **Marathon**: `marathon.css` for time-based system

### Real-Time System (WebSocket)
- **Donation Alerts**: Live alert delivery to overlays
- **Goal Updates**: Real-time progress synchronization
- **Marathon Timer**: Countdown synchronization across clients
- **Donation Feed**: Public donation updates for viewers
- **Settings Updates**: Live preview updates during configuration

### Payment Integration
- **QPay API**: Mongolian payment gateway integration
- **Bank Integration**: Major Mongolian bank support
- **QR Code Generation**: Mobile payment support
- **Webhook Processing**: Automatic payment verification
- **Invoice Management**: Payment tracking and status updates

## TTS Integration

**Chimege API Integration:**
- **Voices**: Multiple male/female Mongolian voices with pre-generated samples
- **Usage Limits**: 20 daily requests, 600 monthly requests, 3000 daily characters
- **File Management**: Automatic cleanup of temporary TTS audio files after playback
- **Rate Limiting**: Built-in rate limiting to prevent API abuse

**Voice Sample System:**
- Pre-generated voice samples stored in `app/static/assets/voice_models/`
- Prevents API calls during voice selection and testing
- Sample text: "Сайн байна уу? Энэ бол миний хоолой. Танд таалагдаж байгаа байх гэж найдаж байна."

**TTS Workflow:**
1. User enables TTS in donation alert settings
2. System generates TTS audio file via Chimege API
3. Audio file served to overlay page via URL
4. Audio plays during donation alert
5. File automatically cleaned up after playback

## Multi-Platform OAuth

**Supported Platforms:**
- Twitch OAuth integration
- YouTube OAuth integration  
- Kick OAuth integration

**Connection Management:**
- Users can connect multiple platforms
- Primary platform designation for main integration
- Individual platform disconnect functionality
- OAuth token refresh handling

**Platform Data Structure:**
```python
class PlatformConnection(db.Model):
    platform_type = db.Column(db.String(50), nullable=False)  # 'twitch', 'youtube', 'kick'
    platform_user_id = db.Column(db.String(100), nullable=False)
    platform_username = db.Column(db.String(100), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
```

## Subscription System

**Payment Integration:**
- **Provider**: QPay QuickQR for Mongolian market
- **Bank Integration**: Support for major Mongolian banks with logo display
- **Pricing**: Multiple tiers with bulk discounts (40,000₮/month base)
- **Trial System**: Free trial for new users

**Bank Account Management:**
- IBAN validation (MN + 18 digits)
- Bank selection with logo display
- Account name and number storage
- Integration with QPay bank codes

**Payment Flow:**
1. User selects subscription tier and duration
2. System creates QPay invoice
3. User pays via bank app or QR code
4. Payment verification and subscription activation
5. Subscription tracking and expiration handling

## Real-Time System

**WebSocket Implementation:**
- **Technology**: Flask-SocketIO for real-time communication
- **Rooms**: User-specific rooms for targeted alerts
- **Events**: `donation_alert`, `test_alert`, `settings_updated`, `goal_updated`, `marathon_updated`
- **Authentication**: User ID-based room joining

**Alert Queue System:**
- Queue management for multiple simultaneous donations
- Priority handling and processing order
- Visual queue display for pending alerts
- Automatic queue processing after alert completion

**Animation Sequence:**
1. **Entrance**: Animation based on user settings (fade-in, slide-up, etc.)
2. **Display**: Static display for configured duration
3. **Exit**: Opposite animation (fade-out, slide-down-exit, etc.)

## Security Considerations

**Authentication & Authorization:**
- Flask-Login for session management
- OAuth integration with external platforms
- User-specific data isolation
- Protected routes with `@login_required` decorator

**File Upload Security:**
- UUID-based filename generation
- File type validation (images, audio)
- Size limits enforced
- Organized storage structure

**API Security:**
- TTS rate limiting to prevent abuse
- Usage tracking and monitoring
- Secure token storage for external APIs
- Environment variable-based configuration

## Development Standards

**Code Organization:**
- **Models**: Feature-based separation with comprehensive relationships
- **Routes**: Blueprint modularization with clear API boundaries
- **Templates**: Component-based with specialized CSS per feature
- **Static Assets**: Organized by feature with performance optimization

**Naming Conventions:**
- **Database**: English schemas with Mongolian display localization
- **CSS**: Feature-scoped with glass morphism design system
- **API**: RESTful endpoints with consistent response formats
- **WebSocket**: Event-driven with room-based targeting

**Quality Standards:**
- **Error Handling**: Comprehensive exception management
- **Logging**: Detailed activity tracking for debugging
- **Security**: Input validation and SQL injection prevention
- **Performance**: Optimized queries and caching strategies

## Production Status

**Current Status**: Fully operational donation alert platform
- **10 major feature systems** completely implemented
- **12 database models** with comprehensive relationships
- **4 route blueprints** with full API coverage
- **Professional UI/UX** with glass morphism design
- **Real-time WebSocket** integration across all features
- **Payment processing** with QPay and bank integration
- **Analytics dashboard** with Chart.js visualization
- **Discord community** with automated management
- **Comprehensive documentation** for maintenance and expansion

**Key Integrations**:
- Chimege API for Mongolian TTS
- QPay for payment processing
- Multi-platform OAuth (Twitch, YouTube, Kick)
- Discord bot for community management
- Chart.js for analytics visualization
- Bootstrap 5 for responsive design
- Flask-SocketIO for real-time features

**Performance Characteristics**:
- Real-time WebSocket communication
- Optimized database queries with proper indexing
- Rate limiting for API endpoints
- Automatic file cleanup and asset management
- Professional error handling and logging
- Mobile-optimized responsive design

## Marathon System

**Purpose**: Stream time extension system where donations add time based on configurable minute pricing

**Key Components:**
- `app/models/marathon.py` - Marathon model with time calculations and WebSocket updates
- `app/templates/marathon.html` - Settings page with real-time preview and controls
- `app/templates/marathon_overlay.html` - OBS overlay with countdown timer
- `app/static/css/marathon.css` - Professional styling with animations

**Features:**
- Real-time countdown timer with WebSocket synchronization
- Flexible pricing system (price per minute)
- Manual time controls (add/remove/pause/resume/reset)
- Donation integration for automatic time addition
- Status tracking (accumulated donations, donated time, manual adjustments)
- Animation effects for timer display
- Font customization for timer and notifications

**Database Schema:**
```sql
marathons table:
- user_id (FK to users)
- minute_price (Decimal)
- remaining_time_minutes, donated_time_minutes, manual_adjustments_minutes
- timer/notification font settings
- started_at, paused_at, is_paused, total_paused_duration
- accumulated_donations tracking
```

**WebSocket Events:**
- `marathon_updated` - Sync countdown state across clients
- `marathon_notification` - Time addition notifications
- Room-based messaging for user-specific sessions

## Discord Integration

**Purpose**: Automated community management and development updates

**Module Structure:**
```
discord_integration/
├── client.py           # Discord client wrapper with connection management
├── channels.py         # Channel creation, editing, deletion, permissions
├── messages.py         # Message sending, embeds, development updates
├── cli.py              # Interactive command-line interface
├── config.py           # Configuration management
├── SERVER_DOCUMENTATION.md  # Complete setup guide
├── QUICK_REFERENCE.md       # Copy/paste commands
└── COMMANDS_HISTORY.md      # Activity logging
```

**Bot Capabilities:**
- Channel management (create/edit/delete with icons and descriptions)
- Rich embed messages with colors and formatting
- Development status updates with completion tracking
- Release announcements with features and bug fixes
- Interactive CLI for real-time Discord management

**Server Architecture:**
- **ЕРӨНХИЙ**: Тавтай морил, зарлал, ерөнхий чат
- **ХӨГЖҮҮЛЭЛТ**: Шинэчлэл, хүсэлт, алдааны мэдээлэл, кодын шалгалт, техникийн хэлэлцүүлэг
- **ХУВИЛБАР**: Хувилбарын гаргалт, туршилт, байршуулалт
- **НИЙГЭМЛЭГ**: Танилцуулга, санал хүсэлт, дэмжлэг

**Configuration:**
```env
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here  # Optional
```

**Usage Examples:**
```bash
# Test connection
python -c "from discord_integration.client import DiscordManager; ..."

# Send development update
# Tell Claude: "Send an update about the marathon system to development-updates"

# Interactive mode
python -m discord_integration.cli
```

**Important**: When posting Discord updates, always write messages in **Mongolian**, not English, as this is a platform for Mongolian content creators.

# System Overview Summary

DonAlert is a **comprehensive donation alert and revenue management platform** specifically designed for Mongolian content creators. The system provides:

**For Streamers**: Complete donation management with real-time alerts, goal tracking, marathon systems, income analytics, and subscription management.

**For Viewers**: Public donation pages with QPay integration, real-time donation feeds, and seamless mobile payment experience.

**For Developers**: Modular Flask architecture, comprehensive documentation, Discord integration, and professional development workflow.

The platform is **production-ready** with 10 major feature systems, professional UI/UX, and complete documentation.

## Features Relevant to Streamers

### Core Streaming Features

1. **Donation Alert System** - Get real-time alerts when viewers donate with custom animations and sounds

2. **Income Dashboard & Analytics** - Track your earnings, see donation trends, and monitor top donors

3. **Donation Goal Tracker** - Set fundraising goals with visual progress bars for your audience

4. **Public Donation Pages** - Give viewers an easy way to donate with shareable links

5. **Marathon System** - Let donations add time to your stream with countdown timers

6. **Multi-Platform Integration** - Connect your Twitch, YouTube, or Kick accounts

7. **Mongolian TTS** - Have donation messages read aloud in Mongolian voices

8. **Custom Assets** - Upload your own GIFs, sounds, and images for personalized alerts

9. **Bank Account Setup** - Connect your Mongolian bank account to receive payments

### Optional Features

10. **Discord Integration** - Automatically post updates to your Discord community server

*Note: All features work together seamlessly with real-time updates and professional design that integrates with OBS for streaming.*

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.