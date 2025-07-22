#!/usr/bin/env python3
"""
Populate donor leaderboard from existing donations.
This script aggregates all existing donations to build initial leaderboard data.
"""

import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.donation import Donation
from app.models.donor_leaderboard import DonorLeaderboard
from app.models.user import User
from collections import defaultdict

def populate_leaderboard():
    """Populate leaderboard from existing donations"""
    app = create_app()
    
    with app.app_context():
        print("Starting donor leaderboard population...")
        
        # Clear existing leaderboard data
        print("Clearing existing leaderboard data...")
        DonorLeaderboard.query.delete()
        db.session.commit()
        
        # Get all donations
        print("Fetching all donations...")
        donations = Donation.query.order_by(Donation.created_at.asc()).all()
        print(f"Found {len(donations)} donations")
        
        if not donations:
            print("No donations found. Exiting.")
            return
        
        # Group donations by streamer and donor
        streamer_donors = defaultdict(lambda: defaultdict(list))
        
        for donation in donations:
            streamer_id = donation.user_id
            
            # For now, treat all donors as guests since we don't have user linkage
            # In the future, we can enhance this to link platform users to registered users
            donor_key = ('guest', donation.donor_name, donation.donor_name)
            
            streamer_donors[streamer_id][donor_key].append(donation)
        
        print(f"Processing donations for {len(streamer_donors)} streamers...")
        
        total_entries = 0
        for streamer_id, donors in streamer_donors.items():
            streamer = User.query.get(streamer_id)
            if not streamer:
                print(f"Warning: Streamer {streamer_id} not found, skipping...")
                continue
            
            print(f"Processing {len(donors)} donors for streamer: {streamer.username}")
            
            for donor_key, donations_list in donors.items():
                donor_type, donor_identifier, donor_name = donor_key
                
                # Calculate aggregated data
                total_amount = sum(d.amount for d in donations_list)
                donation_count = len(donations_list)
                biggest_single = max(d.amount for d in donations_list)
                first_date = min(d.created_at for d in donations_list)
                last_date = max(d.created_at for d in donations_list)
                
                # Create leaderboard entry
                if donor_type == 'user':
                    donor_user_id = donor_identifier
                else:
                    donor_user_id = None
                
                leaderboard_entry = DonorLeaderboard(
                    user_id=streamer_id,
                    donor_name=donor_name,
                    donor_user_id=donor_user_id,
                    total_amount=total_amount,
                    donation_count=donation_count,
                    biggest_single_donation=biggest_single,
                    first_donation_date=first_date,
                    last_donation_date=last_date,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                db.session.add(leaderboard_entry)
                total_entries += 1
                
                # Log progress
                print(f"  {donor_name}: {donation_count} donations, {total_amount}₮ total")
        
        # Commit all entries
        print(f"Saving {total_entries} leaderboard entries...")
        db.session.commit()
        
        # Verification
        print("\nVerification:")
        total_leaderboard_entries = DonorLeaderboard.query.count()
        print(f"Total leaderboard entries created: {total_leaderboard_entries}")
        
        # Show sample top donors for each streamer
        streamers = User.query.filter(User.id.in_(streamer_donors.keys())).all()
        for streamer in streamers:
            top_donors = DonorLeaderboard.get_top_donors(streamer.id, limit=3)
            if top_donors:
                print(f"\nTop donors for {streamer.username}:")
                for i, donor in enumerate(top_donors, 1):
                    print(f"  {i}. {donor.donor_name}: {donor.total_amount}₮ ({donor.donation_count} donations)")
        
        print("\nDonor leaderboard population completed successfully!")

def verify_data_integrity():
    """Verify that leaderboard data matches donation totals"""
    app = create_app()
    
    with app.app_context():
        print("\nVerifying data integrity...")
        
        # Check total amounts match
        total_donations_amount = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
        total_leaderboard_amount = db.session.query(db.func.sum(DonorLeaderboard.total_amount)).scalar() or 0
        
        print(f"Total donations amount: {total_donations_amount}₮")
        print(f"Total leaderboard amount: {total_leaderboard_amount}₮")
        
        if abs(float(total_donations_amount) - float(total_leaderboard_amount)) < 0.01:
            print("✓ Amounts match!")
        else:
            print("✗ Amount mismatch detected!")
            return False
        
        # Check donation counts
        total_donations_count = Donation.query.count()
        total_leaderboard_count = db.session.query(db.func.sum(DonorLeaderboard.donation_count)).scalar() or 0
        
        print(f"Total donations count: {total_donations_count}")
        print(f"Total leaderboard count: {total_leaderboard_count}")
        
        if total_donations_count == total_leaderboard_count:
            print("✓ Counts match!")
        else:
            print("✗ Count mismatch detected!")
            return False
        
        print("✓ Data integrity verification passed!")
        return True

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--verify-only':
        verify_data_integrity()
    else:
        populate_leaderboard()
        verify_data_integrity()