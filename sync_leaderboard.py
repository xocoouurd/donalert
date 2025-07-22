#!/usr/bin/env python3
"""
Sync existing donations into donor_leaderboard table.
This addresses the historical data gap where donations existed before the leaderboard system.
"""

from app import create_app
from app.models.donation import Donation  
from app.models.donor_leaderboard import DonorLeaderboard
from app.extensions import db
from sqlalchemy import func

def sync_leaderboard_data():
    """Sync all existing donations into donor_leaderboard table"""
    app = create_app()
    
    with app.app_context():
        print("🔄 Starting leaderboard sync...")
        
        # Clear existing leaderboard data to rebuild from scratch
        print("🗑️  Clearing existing leaderboard data...")
        DonorLeaderboard.query.delete()
        db.session.commit()
        
        # Get all donations grouped by user and donor
        print("📊 Analyzing existing donations...")
        
        # Group donations by streamer and donor_name only (merge guest + registered)
        donation_groups = db.session.query(
            Donation.user_id,
            Donation.donor_name,
            func.sum(Donation.amount).label('total_amount'),
            func.count(Donation.id).label('donation_count'),
            func.max(Donation.amount).label('biggest_single'),
            func.min(Donation.created_at).label('first_donation'),
            func.max(Donation.created_at).label('last_donation')
        ).group_by(
            Donation.user_id,
            Donation.donor_name
        ).all()
        
        print(f"📈 Found {len(donation_groups)} unique donor groups")
        
        # Create leaderboard entries
        created_count = 0
        for group in donation_groups:
            entry = DonorLeaderboard(
                user_id=group.user_id,
                donor_name=group.donor_name,
                donor_user_id=None,  # Merged entry - not tied to specific registration
                total_amount=group.total_amount,
                donation_count=group.donation_count,
                biggest_single_donation=group.biggest_single,
                first_donation_date=group.first_donation,
                last_donation_date=group.last_donation
            )
            
            db.session.add(entry)
            created_count += 1
            
            print(f"✅ {group.donor_name}: {group.total_amount}₮ ({group.donation_count} donations)")
        
        # Commit all changes
        db.session.commit()
        print(f"🎉 Successfully created {created_count} leaderboard entries!")
        
        # Show final stats
        print("\n📊 Final leaderboard stats:")
        for user_id in db.session.query(Donation.user_id).distinct():
            user_id = user_id[0]
            top_donors = DonorLeaderboard.get_top_donors(user_id, limit=5)
            print(f"\n👤 User {user_id} top donors:")
            for i, donor in enumerate(top_donors, 1):
                print(f"  #{i}: {donor.donor_name} - {donor.total_amount}₮")

if __name__ == '__main__':
    sync_leaderboard_data()