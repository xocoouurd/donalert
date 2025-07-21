#!/usr/bin/env python3
"""
Security test script for sound effects file management.
Ensures files are properly contained and accessible only through intended routes.
"""

import os
from app import create_app
from app.models.sound_effect import SoundEffect

def test_file_security():
    """Test file security and access controls"""
    app = create_app()
    
    with app.app_context():
        print("🔒 Testing Sound Effects File Security...")
        
        # Test 1: Verify files are in correct directory
        sound_effects_dir = os.path.join('app', 'static', 'assets', 'sound_effects')
        if os.path.exists(sound_effects_dir):
            print(f"✅ Sound effects directory exists: {sound_effects_dir}")
        else:
            print(f"❌ Sound effects directory missing: {sound_effects_dir}")
            return
        
        # Test 2: Check file permissions are readable but not executable
        for filename in os.listdir(sound_effects_dir):
            filepath = os.path.join(sound_effects_dir, filename)
            stat = os.stat(filepath)
            permissions = oct(stat.st_mode)[-3:]
            
            # Should be readable (644 or 664) but not executable
            if permissions in ['644', '664']:
                print(f"✅ Safe permissions for {filename}: {permissions}")
            else:
                print(f"⚠️  Check permissions for {filename}: {permissions}")
        
        # Test 3: Verify only expected file types
        allowed_extensions = {'.mp3', '.wav', '.ogg'}
        for filename in os.listdir(sound_effects_dir):
            _, ext = os.path.splitext(filename.lower())
            if ext in allowed_extensions:
                print(f"✅ Safe file type: {filename} ({ext})")
            else:
                print(f"⚠️  Unexpected file type: {filename} ({ext})")
        
        # Test 4: Check database records match files
        db_sounds = SoundEffect.query.all()
        filesystem_files = set(os.listdir(sound_effects_dir))
        db_filenames = {sound.filename for sound in db_sounds}
        
        # Files in DB but not on filesystem
        missing_files = db_filenames - filesystem_files
        if missing_files:
            print(f"⚠️  Files in DB but missing from filesystem: {missing_files}")
        else:
            print("✅ All database sound effects have corresponding files")
        
        # Files on filesystem but not in DB
        orphaned_files = filesystem_files - db_filenames
        if orphaned_files:
            print(f"ℹ️  Files on filesystem not in DB: {orphaned_files}")
        else:
            print("✅ All filesystem files are tracked in database")
        
        # Test 5: Verify URL generation doesn't allow directory traversal
        test_sound = db_sounds[0] if db_sounds else None
        if test_sound:
            url = test_sound.get_file_url()
            if '../' not in url and ('static/assets/sound_effects/' in url):
                print(f"✅ Safe URL generation: {url}")
            else:
                print(f"⚠️  Potential security issue in URL: {url}")
        
        # Test 6: Check file sizes are reasonable (not too large)
        max_size_mb = 5  # 5MB limit as per documentation
        max_size_bytes = max_size_mb * 1024 * 1024
        
        for filename in filesystem_files:
            filepath = os.path.join(sound_effects_dir, filename)
            size = os.path.getsize(filepath)
            size_mb = size / (1024 * 1024)
            
            if size <= max_size_bytes:
                print(f"✅ File size OK: {filename} ({size_mb:.2f}MB)")
            else:
                print(f"⚠️  File too large: {filename} ({size_mb:.2f}MB)")
        
        print("\n🔒 Security test completed!")

if __name__ == '__main__':
    test_file_security()