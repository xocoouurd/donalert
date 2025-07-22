#!/usr/bin/env python3
"""
Scheduled Tier Change Processor

This script processes scheduled subscription tier changes that are due.
It should be run as a cron job daily to handle downgrades and other scheduled changes.

Usage:
    python scripts/process_scheduled_changes.py [--dry-run] [--verbose]
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.subscription import Subscription
from app.extensions import db

def setup_logging(verbose=False):
    """Setup logging configuration"""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'scheduled_changes.log')),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def send_notification_email(user, change_type, old_tier, new_tier, change_date):
    """Send email notification about tier change"""
    try:
        # TODO: Implement email notification system
        # For now, just log the notification
        logger.info(f"EMAIL NOTIFICATION: User {user.id} ({user.email}) tier change: "
                   f"{old_tier.value} -> {new_tier.value} on {change_date}")
        
        # In a real implementation, you would:
        # 1. Load email template
        # 2. Populate with user data
        # 3. Send via SMTP or email service
        # 4. Log success/failure
        
        return True
    except Exception as e:
        logger.error(f"Failed to send notification email to user {user.id}: {e}")
        return False

def process_scheduled_changes(dry_run=False):
    """Process all scheduled tier changes that are due"""
    logger.info(f"Starting scheduled change processing (dry_run={dry_run})")
    
    try:
        # Get count of changes to process
        changes_processed = Subscription.process_scheduled_changes() if not dry_run else 0
        
        if dry_run:
            # In dry run mode, just count what would be processed
            from app.models.subscription import SubscriptionStatus
            current_time = datetime.utcnow()
            
            subscriptions_due = Subscription.query.filter(
                Subscription.scheduled_change_date.isnot(None),
                Subscription.scheduled_change_date <= current_time,
                Subscription.status == SubscriptionStatus.ACTIVE
            ).all()
            
            logger.info(f"DRY RUN: Found {len(subscriptions_due)} scheduled changes to process")
            
            for subscription in subscriptions_due:
                user = subscription.user
                logger.info(f"DRY RUN: Would process user {user.id} ({user.email}) - "
                           f"Change from {subscription.feature_tier.value if subscription.feature_tier else 'unknown'} "
                           f"to {subscription.scheduled_tier_change.value} "
                           f"scheduled for {subscription.scheduled_change_date}")
            
            return len(subscriptions_due)
        else:
            logger.info(f"Successfully processed {changes_processed} scheduled changes")
            return changes_processed
            
    except Exception as e:
        logger.error(f"Error processing scheduled changes: {e}")
        raise

def send_upcoming_change_warnings():
    """Send warning emails for changes happening in 3 days"""
    logger.info("Checking for upcoming tier changes requiring warnings")
    
    try:
        from app.models.subscription import SubscriptionStatus
        from datetime import timedelta
        
        # Find subscriptions with changes in 3 days
        warning_date = datetime.utcnow() + timedelta(days=3)
        warning_start = datetime.utcnow() + timedelta(days=2, hours=23)  # 3 days minus 1 hour window
        
        upcoming_changes = Subscription.query.filter(
            Subscription.scheduled_change_date.isnot(None),
            Subscription.scheduled_change_date >= warning_start,
            Subscription.scheduled_change_date <= warning_date,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).all()
        
        warnings_sent = 0
        for subscription in upcoming_changes:
            user = subscription.user
            if user and user.email:
                success = send_notification_email(
                    user=user,
                    change_type='warning',
                    old_tier=subscription.feature_tier,
                    new_tier=subscription.scheduled_tier_change,
                    change_date=subscription.scheduled_change_date
                )
                if success:
                    warnings_sent += 1
        
        logger.info(f"Sent {warnings_sent} warning emails for upcoming tier changes")
        return warnings_sent
        
    except Exception as e:
        logger.error(f"Error sending tier change warnings: {e}")
        return 0

def check_system_health():
    """Perform basic system health checks"""
    logger.info("Performing system health checks")
    
    try:
        # Check database connectivity
        db.session.execute("SELECT 1")
        logger.debug("Database connectivity: OK")
        
        # Check for orphaned pending subscriptions (older than 1 day)
        from app.models.subscription import SubscriptionStatus
        from datetime import timedelta
        
        old_pending = Subscription.query.filter(
            Subscription.status == SubscriptionStatus.PENDING,
            Subscription.created_at < datetime.utcnow() - timedelta(days=1)
        ).count()
        
        if old_pending > 0:
            logger.warning(f"Found {old_pending} old pending subscriptions that may need cleanup")
        
        # Check for subscriptions with scheduled changes but no pending subscription
        orphaned_scheduled = Subscription.query.filter(
            Subscription.scheduled_change_date.isnot(None),
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count()
        
        logger.info(f"System health check complete. {orphaned_scheduled} subscriptions have scheduled changes")
        
        return True
        
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Process scheduled subscription tier changes')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be processed without making changes')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--warnings-only', action='store_true',
                       help='Only send warning emails, skip processing changes')
    parser.add_argument('--health-check', action='store_true',
                       help='Only perform system health checks')
    
    args = parser.parse_args()
    
    # Setup logging
    global logger
    logger = setup_logging(args.verbose)
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        try:
            start_time = datetime.utcnow()
            logger.info(f"Scheduled change processor started at {start_time}")
            
            # Perform health check
            if not check_system_health():
                logger.error("System health check failed. Aborting.")
                return 1
            
            if args.health_check:
                logger.info("Health check completed successfully")
                return 0
            
            # Send warning emails for upcoming changes
            warnings_sent = send_upcoming_change_warnings()
            
            if args.warnings_only:
                logger.info(f"Warnings-only mode: sent {warnings_sent} warning emails")
                return 0
            
            # Process scheduled changes
            changes_processed = process_scheduled_changes(dry_run=args.dry_run)
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"Processing completed in {duration:.2f}s. "
                       f"Changes processed: {changes_processed}, Warnings sent: {warnings_sent}")
            
            return 0
            
        except Exception as e:
            logger.error(f"Fatal error in scheduled change processor: {e}")
            return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)