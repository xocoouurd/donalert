#!/usr/bin/env python3
"""
Test script to verify donor leaderboard models work correctly.
"""

import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.donor_leaderboard import DonorLeaderboard
from app.models.donor_leaderboard_settings import DonorLeaderboardSettings
from app.models.user import User

def test_models():
    """Test donor leaderboard models functionality"""
    app = create_app()
    
    with app.app_context():
        print("Testing DonorLeaderboard and DonorLeaderboardSettings models...\n")
        
        # Get a test user (streamer)
        streamer = User.query.first()
        if not streamer:
            print("No users found. Please create a user first.")
            return
        
        print(f"Testing with streamer: {streamer.username} (ID: {streamer.id})")
        
        # Test 1: DonorLeaderboard queries
        print("\n1. Testing DonorLeaderboard queries:")
        
        # Get top donors
        top_donors = DonorLeaderboard.get_top_donors(streamer.id, limit=5)
        print(f"   Top {len(top_donors)} donors:")
        for i, donor in enumerate(top_donors, 1):
            print(f"   {i}. {donor.donor_name}: {donor.total_amount}₮ ({donor.donation_count} donations)")
        
        # Test position checking
        if top_donors:
            test_donor = top_donors[0]
            position = DonorLeaderboard.get_donor_position(streamer.id, test_donor.donor_name)
            print(f"   Position of {test_donor.donor_name}: #{position}")
        
        # Test 2: DonorLeaderboardSettings
        print("\n2. Testing DonorLeaderboardSettings:")
        
        # Create or get settings
        settings = DonorLeaderboardSettings.get_or_create_for_user(streamer.id)
        print(f"   Settings created/retrieved for user {streamer.id}")
        print(f"   Is enabled: {settings.is_enabled}")
        print(f"   Positions count: {settings.positions_count}")
        
        # Test styling methods
        throne_styling = settings.get_throne_styling()
        print(f"   Throne styling keys: {list(throne_styling.keys())}")
        
        podium_styling = settings.get_podium_styling()
        print(f"   Podium styling keys: {list(podium_styling.keys())}")
        
        global_styling = settings.get_global_styling()
        print(f"   Global styling keys: {list(global_styling.keys())}")
        
        # Test settings update
        settings.update_settings(
            is_enabled=True,
            positions_count=5,
            show_amounts=True,
            show_donation_counts=False
        )
        db.session.commit()
        print(f"   Updated settings: enabled={settings.is_enabled}, positions={settings.positions_count}")
        
        # Test custom styling
        custom_throne = {
            'background_color': '#FF0000',
            'text_color': '#FFFFFF',
            'glow_effect': True
        }
        settings.set_throne_styling(custom_throne)
        db.session.commit()
        
        retrieved_styling = settings.get_throne_styling()
        print(f"   Custom throne background: {retrieved_styling.get('background_color')}")
        
        # Test to_dict() methods
        print("\n3. Testing serialization:")
        if top_donors:
            donor_dict = top_donors[0].to_dict()
            print(f"   DonorLeaderboard.to_dict() keys: {list(donor_dict.keys())}")
        
        settings_dict = settings.to_dict()
        print(f"   DonorLeaderboardSettings.to_dict() keys: {list(settings_dict.keys())}")
        
        # Test 4: Position change detection
        print("\n4. Testing position change detection:")
        if top_donors and len(top_donors) > 1:
            test_donor = top_donors[1]  # Second place donor
            old_amount = float(test_donor.total_amount) - 1000  # Simulate previous lower amount
            
            change_info = test_donor.check_position_change(old_amount)
            print(f"   Position change for {test_donor.donor_name}:")
            print(f"   Changed: {change_info['changed']}")
            print(f"   Old position: {change_info['old_position']}")
            print(f"   New position: {change_info['new_position']}")
            print(f"   Throne takeover: {change_info['is_throne_takeover']}")
        
        print("\n✓ All model tests completed successfully!")

if __name__ == '__main__':
    test_models()