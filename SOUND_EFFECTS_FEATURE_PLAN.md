# Sound Effects Feature - Comprehensive Implementation Plan

## Overview
Add viewer-to-streamer sound effect system that integrates with existing donation infrastructure. Viewers can send paid sound effects that play on stream without visual alerts, contributing to marathon/goal progress.

## Core Architecture

### Database Schema

#### New Tables
```sql
-- Sound library managed by admin
CREATE TABLE sound_effects (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    filename VARCHAR(255) NOT NULL UNIQUE,
    duration_seconds DECIMAL(4,2) NOT NULL, -- 1.00 to 5.00 seconds
    file_size INT NOT NULL, -- bytes
    tags TEXT, -- JSON array of tags
    category VARCHAR(100), -- 'memes', 'gaming', 'reactions', etc.
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active (is_active),
    INDEX idx_category (category)
);

-- User settings for sound effects
CREATE TABLE user_sound_settings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    is_enabled BOOLEAN DEFAULT FALSE,
    price_per_sound DECIMAL(10,2) DEFAULT 1000.00, -- MNT
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user (user_id)
);

-- Transaction logging for analytics
CREATE TABLE sound_effect_donations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sound_effect_id INT NOT NULL,
    streamer_user_id INT NOT NULL,
    donor_name VARCHAR(100) NOT NULL,
    donor_user_id INT NULL, -- NULL for guest donations
    amount DECIMAL(10,2) NOT NULL,
    donation_payment_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sound_effect_id) REFERENCES sound_effects(id),
    FOREIGN KEY (streamer_user_id) REFERENCES users(id),
    FOREIGN KEY (donor_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (donation_payment_id) REFERENCES donation_payments(id),
    INDEX idx_streamer_date (streamer_user_id, created_at),
    INDEX idx_sound_effect (sound_effect_id)
);
```

#### Enhanced Existing Tables
```sql
-- Add to donations table
ALTER TABLE donations ADD COLUMN type ENUM('alert', 'sound_effect') DEFAULT 'alert';
ALTER TABLE donations ADD COLUMN sound_effect_id INT NULL;
ALTER TABLE donations ADD INDEX idx_type (type);
ALTER TABLE donations ADD FOREIGN KEY (sound_effect_id) REFERENCES sound_effects(id);

-- Add to donation_payments table  
ALTER TABLE donation_payments ADD COLUMN type ENUM('alert', 'sound_effect') DEFAULT 'alert';
ALTER TABLE donation_payments ADD COLUMN sound_effect_id INT NULL;
ALTER TABLE donation_payments ADD INDEX idx_type (type);
ALTER TABLE donation_payments ADD FOREIGN KEY (sound_effect_id) REFERENCES sound_effects(id);
```

### File Management
- **Location**: `/app/static/assets/sound_effects/`
- **Format**: MP3 files, normalized volume (-23 LUFS standard)
- **Size Limit**: 5MB max per file
- **Duration**: 1-5 seconds enforced
- **Naming**: UUID-based filenames for security
- **Example**: `sound_effects/a1b2c3d4-e5f6-7890-abcd-ef1234567890.mp3`

## Feature Implementation

### 1. Admin Sound Management
**Location**: New admin interface (future scope for now, manual upload)
- Upload sound files with metadata (name, tags, category)
- Automatic duration detection using audio libraries
- Volume normalization processing
- Enable/disable individual sounds
- **Initial Setup**: Manual database insertion for first sounds

### 2. Streamer Settings Page
**Location**: New `/sound-effects` route and template
- **Enable/Disable Toggle**: Master switch for sound effects
- **Price Setting**: Single price for all sound effects (₮)
- **Testing Section**: "Test Random Sound" button (plays random sound from pool of 5 to overlay)
- **Analytics Dashboard**: 
  - Total sound effect revenue this month
  - Top 5 most popular sounds sent
  - Sound effects vs donation alerts revenue chart
  - Recent sound effect activity log
- **Advanced Tier Only**: Feature locked behind subscription tier check
- **Integration**: Add link to main navigation sidebar

### 3. Public Sound Effects Page
**Location**: New tab on existing donation page (`/donate/{username}`)
- **Sound Browser**: 
  - Grid layout with sound thumbnails (name + category)
  - Search bar (searches name and tags)
  - Category filter dropdown
  - Pagination for large sound libraries
- **Sound Preview**: 
  - Play button on each sound card
  - Switches to stop button when playing
  - Auto-stops other previews when new sound plays
  - Visual waveform or duration indicator
- **Selected State**: 
  - Visual highlight of chosen sound
  - "Selected" badge or border change
  - Sound name appears in "send" section
- **Price Display**: 
  - Streamer's price clearly shown per sound
  - Total cost before payment
- **Send Button**: 
  - Only enabled when sound selected
  - Triggers QPay payment flow with sound metadata

### 4. Payment Integration
**Decision Point**: Reuse vs Duplicate QPay Flow

#### Option A: Enhance Existing Flow (Recommended)
```python
# Enhance existing DonationPayment.create_donation_payment()
def create_donation_payment(cls, streamer_user_id, donor_name, amount, message="", 
                          donor_platform="guest", donor_user_id=None, 
                          payment_type="alert", sound_effect_id=None):
    # Existing logic + new fields
    
# Enhance existing mark_as_paid()
def mark_as_paid(self, payment_method=None):
    # Create donation with type field
    donation = Donation(
        type=self.type,
        sound_effect_id=self.sound_effect_id,
        # ... existing fields
    )
    
    # Route to appropriate handler
    if self.type == 'sound_effect':
        self._send_sound_effect(donation)
    else:
        self._send_donation_alert(donation)
```

#### Option B: Separate Flow (If Needed)
```python
# New dedicated classes
class SoundEffectPayment(db.Model):
    # Similar to DonationPayment but sound-specific
    
class SoundEffectDonation(db.Model):
    # Similar to Donation but sound-specific
```

**Recommendation**: Option A - enhance existing flow with type differentiation

### 5. Queue & Overlay System
**Integrate with existing alert queue**:
```javascript
// Enhance existing overlay queue processing
function processQueueItem(queueItem) {
    if (queueItem.type === 'sound_effect') {
        playSoundEffect(queueItem);
    } else {
        playDonationAlert(queueItem);
    }
}

function playSoundEffect(soundData) {
    const audio = new Audio(`/static/assets/sound_effects/${soundData.sound_filename}`);
    audio.volume = 1.0; // Always 100%
    audio.play();
    
    // Queue next item after sound duration + 1 second gap
    setTimeout(() => {
        processNextQueueItem();
    }, (soundData.duration_seconds * 1000) + 1000);
}
```

## User Experience Flow

### Viewer Journey
1. Visit `/donate/{streamer_username}`
2. See tabs: "Donation" | "Sound Effects"
3. Click "Sound Effects" tab
4. Browse sounds by category or search
5. Click play button to preview sounds
6. Click sound card to select (visual highlight)
7. See selected sound name and price in send section
8. Click "Send Sound Effect" → QPay payment page
9. Complete payment → Return to success page
10. Sound queued and plays on stream

### Streamer Journey
1. Navigate to "Sound Effects" in sidebar
2. Toggle "Enable Sound Effects" switch
3. Set price per sound effect (e.g., 2000₮)
4. Click "Test Random Sound" to hear example on overlay
5. Save settings
6. Monitor real-time analytics as sounds are sent
7. View revenue breakdown in dashboard

## Technical Implementation Details

### Models Structure
```python
class SoundEffect(db.Model):
    __tablename__ = 'sound_effects'
    # Fields as defined in schema above
    
    def get_file_url(self):
        return url_for('static', filename=f'assets/sound_effects/{self.filename}')
    
    def get_tags_list(self):
        return json.loads(self.tags) if self.tags else []

class UserSoundSettings(db.Model):
    __tablename__ = 'user_sound_settings'
    # Fields as defined in schema above
    
    @classmethod
    def get_or_create_for_user(cls, user_id):
        settings = cls.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = cls(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        return settings
```

### Route Structure
```python
# New routes to add
@main_bp.route('/sound-effects')
@login_required
def sound_effects_settings():
    # Streamer settings page

@main_bp.route('/donate/<username>/sounds')
def public_sound_effects(username):
    # Public sound selection page

@main_bp.route('/api/sound-effects/test', methods=['POST'])
@login_required  
def test_random_sound():
    # Send random sound to overlay for testing

@main_bp.route('/api/sound-effects/preview/<int:sound_id>')
def preview_sound(sound_id):
    # Serve sound file for preview (with rate limiting)
```

## Development Phases

### Phase 1: Core Infrastructure (Week 1-2)
1. **Database**: Create migrations for all new tables
2. **Models**: SoundEffect, UserSoundSettings, enhanced Donation/DonationPayment
3. **File Structure**: Set up sound_effects directory and sample files
4. **Basic Admin**: Manual sound upload and database insertion scripts

### Phase 2: Streamer Interface (Week 2-3)
1. **Settings Page**: `/sound-effects` route and template
2. **Enable/Disable**: Toggle functionality
3. **Price Setting**: Form handling and validation
4. **Basic Testing**: Random sound test button
5. **Navigation**: Add to sidebar for advanced tier users

### Phase 3: Public Interface (Week 3-4)
1. **Sound Browser**: Public `/donate/{username}/sounds` page
2. **Search/Filter**: Name and tag search, category filtering
3. **Preview System**: Audio preview with proper controls
4. **Selection UX**: Visual selection states and sound info display

### Phase 4: Payment Integration (Week 4-5)
1. **Enhanced QPay**: Modify existing flow to handle sound effects
2. **Payment Processing**: Create sound effect donations
3. **Webhook Handling**: Process payments and create appropriate records
4. **Error Handling**: Payment failures and retry logic

### Phase 5: Overlay Integration (Week 5-6)
1. **Queue Enhancement**: Integrate sound effects into existing alert queue
2. **Audio Playback**: Sound effect playback in overlay
3. **Timing Logic**: Duration-based queue progression
4. **Testing Tools**: Streamer testing interface

### Phase 6: Analytics & Polish (Week 6-7)
1. **Analytics Dashboard**: Revenue and usage analytics
2. **Popular Sounds**: Most played sounds tracking
3. **Responsive Design**: Mobile-optimized interfaces
4. **Performance**: Audio loading and caching optimization

## QPay Integration Analysis

### Current Flow Analysis
```python
# Current donation flow:
1. User visits /donate/{username}
2. Fills donation form → POST /donate/{username}
3. Creates DonationPayment record
4. Redirects to QPay with invoice
5. User pays → QPay webhook calls back
6. DonationPayment.mark_as_paid() creates Donation record
7. Triggers _send_donation_alert()
```

### Sound Effects Integration Options

#### Option A: Enhance Existing (Recommended)
**Pros**:
- Reuses proven payment logic
- Same webhook handling
- Consistent payment experience
- Less code duplication

**Implementation**:
```python
# Modify existing methods to accept type parameter
DonationPayment.create_donation_payment(
    streamer_user_id=streamer_id,
    donor_name=donor_name,
    amount=sound_price,
    type='sound_effect',
    sound_effect_id=selected_sound_id
)
```

**Changes Required**:
- Add `type` and `sound_effect_id` to DonationPayment model
- Modify `mark_as_paid()` to route based on type
- Add `_send_sound_effect()` method alongside `_send_donation_alert()`

#### Option B: Separate Flow
**Pros**:
- Complete isolation of concerns
- No risk of breaking existing donations
- Can optimize specifically for sound effects

**Cons**:
- Code duplication
- Two payment systems to maintain
- More complex webhook routing

### Recommendation: Option A with Safety Guards

```python
# Safe implementation approach
def mark_as_paid(self, payment_method=None):
    try:
        # Create donation record (existing logic)
        donation = Donation(...)
        
        # Route based on type with fallback
        if getattr(self, 'type', 'alert') == 'sound_effect':
            self._send_sound_effect(donation)
        else:
            self._send_donation_alert(donation)  # Existing logic unchanged
            
    except Exception as e:
        # Existing error handling
```

This approach:
- Preserves all existing donation functionality
- Adds sound effects as an extension
- Provides clear separation in processing
- Maintains single payment/webhook system

## Success Metrics
- **Adoption**: % of advanced tier streamers enabling sound effects
- **Revenue**: Average revenue per sound effect vs regular donation  
- **Engagement**: Sounds sent per viewer session
- **Retention**: Streamer continued usage after first week
- **Performance**: Audio loading times and queue processing speed

## Risk Considerations
- **Audio Spam**: Mitigated by payment requirement and queue system
- **Copyright**: Admin-curated library ensures legal compliance
- **Technical Load**: Audio CDN and bandwidth monitoring needed
- **User Adoption**: Clear onboarding and value demonstration required
- **Payment Conflicts**: Careful testing of enhanced QPay flow

## Future Enhancements (Not Current Scope)
- **Custom Upload Tier**: Premium users upload personal sounds
- **Sound Packs**: Themed collections for purchase ($5-10 packs)
- **Seasonal Content**: Holiday-specific rotations
- **Advanced Analytics**: Sound performance recommendations
- **API Integration**: Third-party sound library partnerships

## Implementation Progress Tracking

### Phase 1: Database Infrastructure ✅ COMPLETED
**Goal**: Establish the foundation without breaking existing functionality
- [x] Create `sound_effects` table for the audio library
- [x] Create `user_sound_settings` table for streamer preferences  
- [x] Create `sound_effect_donations` table for transaction logging
- [x] Add `type` and `sound_effect_id` columns to existing `donations` and `donation_payments` tables
- [x] Create database migration files
- [x] Build corresponding SQLAlchemy models

**Implementation Notes**:
- Created 3 new models: `SoundEffect`, `UserSoundSettings`, `SoundEffectDonation`
- Enhanced existing `Donation` and `DonationPayment` models with type differentiation
- Migration `863d451b92d3` applied successfully
- Enhanced QPay flow with safety guards to route by payment type
- Added `_send_sound_effect()` method alongside existing `_send_donation_alert()`
- Fixed relationship backref conflicts between models
- **TESTED**: All models create, query, and relate correctly
- **VERIFIED**: Enhanced payment flow accepts both 'alert' and 'sound_effect' types

### Phase 2: File Management Setup ✅ COMPLETED
**Goal**: Prepare audio file infrastructure
- [x] Create `/app/static/assets/sound_effects/` directory structure
- [x] Add 5-10 sample sound effect files for testing
- [x] Create manual database insertion script for initial sound library
- [x] Test file serving and security

**Implementation Notes**:
- Created sound_effects directory under `/app/static/assets/`
- Added 5 sample MP3 files: airhorn, applause, classic_bell, coin_drop, thank_you
- Created `populate_sound_effects.py` script to seed database with initial sounds
- Populated database with 5 sounds across 5 categories: gaming, memes, notifications, reactions, voice
- Created `test_sound_security.py` for comprehensive security validation
- **TESTED**: File permissions (664), file types (MP3), size limits (<5MB), URL generation
- **VERIFIED**: No directory traversal vulnerabilities, all files tracked in database
- **SECURITY**: All files properly contained and accessible via Flask static serving
- **INTEGRATION TESTED**: Database-file sync, model methods, query functionality all verified

### Phase 3: Enhanced Payment Flow ⏸️ PENDING
**Goal**: Make QPay system handle both donations and sound effects
- [ ] Enhance `DonationPayment.create_donation_payment()` method
- [ ] Modify `mark_as_paid()` to route by payment type
- [ ] Add `_send_sound_effect()` method alongside existing `_send_donation_alert()`
- [ ] Test payment flow with both types

### Phase 4: Streamer Settings Interface ✅ COMPLETED
**Goal**: Let streamers configure sound effects
- [x] Create `/sound-effects` route and template
- [x] Build enable/disable toggle and price setting form
- [x] Add "Test Random Sound" functionality
- [x] Integrate into sidebar navigation (advanced tier only)

**Implementation Notes**:
- Created comprehensive `/sound-effects` route with advanced tier subscription checking
- Built responsive settings page with glass morphism design matching existing UI
- Implemented real-time settings updates with AJAX form submission
- Added "Test Random Sound" functionality that sends test sounds to overlay
- Created sound preview system for streamers to preview available sounds
- Integrated into sidebar navigation with conditional display for advanced tier users only
- Added comprehensive error handling and user feedback with toast notifications
- **TESTED**: All routes work correctly, UserSoundSettings model functions properly
- **VERIFIED**: Template and CSS files created and accessible
- **INTEGRATION TESTED**: Sidebar navigation shows sound effects link for advanced users

### Phase 5: Public Sound Browser ⏸️ PENDING
**Goal**: Let viewers select and send sound effects
- [ ] Add "Sound Effects" tab to existing `/donate/{username}` page
- [ ] Build sound browser with search/filter/preview
- [ ] Implement sound selection and payment trigger
- [ ] Test complete viewer flow

### Phase 6: Overlay Integration ⏸️ PENDING
**Goal**: Make sound effects play on stream
- [ ] Enhance existing alert queue to handle sound effects
- [ ] Add sound playback functionality to overlay
- [ ] Implement duration-based queue timing
- [ ] Test with real overlay setup

---

**Document Status**: Living document - update as implementation progresses
**Last Updated**: 2025-07-21
**Version**: 1.1 - Added phased implementation plan