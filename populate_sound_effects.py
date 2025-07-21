#!/usr/bin/env python3
"""
Script to populate the sound_effects table with initial sample sounds.
Run this script after Phase 1 database migration is complete.
"""

import os
import json
from app import create_app
from app.extensions import db
from app.models.sound_effect import SoundEffect

# Sample sound effects data
SOUND_EFFECTS = [
    {
        'name': 'Airhorn',
        'filename': 'airhorn.mp3',
        'duration_seconds': 2.0,
        'category': 'memes',
        'tags': ['airhorn', 'loud', 'hype', 'meme']
    },
    {
        'name': 'Applause',
        'filename': 'applause.mp3',
        'duration_seconds': 3.5,
        'category': 'reactions',
        'tags': ['applause', 'clap', 'celebration', 'positive']
    },
    {
        'name': 'Classic Bell',
        'filename': 'classic_bell.mp3',
        'duration_seconds': 1.5,
        'category': 'notifications',
        'tags': ['bell', 'classic', 'notification', 'alert']
    },
    {
        'name': 'Coin Drop',
        'filename': 'coin_drop.mp3',
        'duration_seconds': 1.0,
        'category': 'gaming',
        'tags': ['coin', 'money', 'gaming', 'retro']
    },
    {
        'name': 'Thank You',
        'filename': 'thank_you.mp3',
        'duration_seconds': 2.5,
        'category': 'voice',
        'tags': ['thank you', 'voice', 'appreciation', 'gratitude']
    }
]

def get_file_size(filename):
    """Get file size in bytes"""
    filepath = os.path.join('app', 'static', 'assets', 'sound_effects', filename)
    if os.path.exists(filepath):
        return os.path.getsize(filepath)
    return 0

def populate_sound_effects():
    """Populate the sound_effects table with sample data"""
    app = create_app()
    
    with app.app_context():
        print("🎵 Populating sound effects database...")
        
        # Check if sound effects already exist
        existing_count = SoundEffect.query.count()
        if existing_count > 0:
            print(f"⚠️  Found {existing_count} existing sound effects. Skipping population.")
            return
        
        # Add each sound effect
        for sound_data in SOUND_EFFECTS:
            # Get actual file size
            file_size = get_file_size(sound_data['filename'])
            
            if file_size == 0:
                print(f"❌ File not found: {sound_data['filename']}")
                continue
            
            # Create sound effect record
            sound_effect = SoundEffect(
                name=sound_data['name'],
                filename=sound_data['filename'],
                duration_seconds=sound_data['duration_seconds'],
                file_size=file_size,
                category=sound_data['category'],
                tags=json.dumps(sound_data['tags']),
                is_active=True
            )
            
            db.session.add(sound_effect)
            print(f"✅ Added: {sound_data['name']} ({sound_data['filename']}) - {file_size} bytes")
        
        # Commit all changes
        db.session.commit()
        
        # Verify results
        total_sounds = SoundEffect.query.count()
        active_sounds = SoundEffect.query.filter_by(is_active=True).count()
        categories = SoundEffect.get_categories()
        
        print(f"\n🎉 Successfully populated sound effects database!")
        print(f"   Total sounds: {total_sounds}")
        print(f"   Active sounds: {active_sounds}")
        print(f"   Categories: {', '.join(categories)}")
        
        # Test query functionality
        print(f"\n🔍 Testing queries:")
        gaming_sounds = SoundEffect.get_active_sounds(category='gaming')
        print(f"   Gaming sounds: {len(gaming_sounds)}")
        
        search_results = SoundEffect.get_active_sounds(search_term='bell')
        print(f"   Sounds matching 'bell': {len(search_results)}")

if __name__ == '__main__':
    populate_sound_effects()