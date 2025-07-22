#!/bin/bash

# DonAlert Scheduled Changes Management Script
# 
# This script provides convenient commands for managing scheduled subscription changes
# Usage: ./scripts/run_scheduled_changes.sh [command]

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "Activated virtual environment"
fi

# Function to show usage
show_usage() {
    echo "DonAlert Scheduled Changes Management"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  process        Process all due scheduled changes"
    echo "  dry-run        Show what would be processed (no changes)"
    echo "  warnings       Send warning emails only"
    echo "  health         Perform system health check"
    echo "  status         Show current scheduled changes"
    echo "  install-cron   Install cron jobs"
    echo "  remove-cron    Remove cron jobs"
    echo "  logs           Show recent log entries"
    echo "  help           Show this help message"
    echo ""
}

# Function to show current scheduled changes
show_status() {
    echo "Current scheduled changes:"
    python -c "
from app import create_app
from app.models.subscription import Subscription, SubscriptionStatus
from datetime import datetime

app = create_app()
with app.app_context():
    current_time = datetime.utcnow()
    scheduled = Subscription.query.filter(
        Subscription.scheduled_change_date.isnot(None),
        Subscription.status == SubscriptionStatus.ACTIVE
    ).all()
    
    if not scheduled:
        print('No scheduled changes found.')
    else:
        print(f'Found {len(scheduled)} scheduled changes:')
        print()
        for sub in scheduled:
            user = sub.user
            status = '🔴 OVERDUE' if sub.scheduled_change_date < current_time else '🟡 PENDING'
            print(f'{status} User {user.id} ({user.email}):')
            print(f'  Current: {sub.feature_tier.value if sub.feature_tier else \"unknown\"}')
            print(f'  Target:  {sub.scheduled_tier_change.value}')
            print(f'  Date:    {sub.scheduled_change_date}')
            print()
"
}

# Function to install cron jobs
install_cron() {
    echo "Installing cron jobs for scheduled changes..."
    
    # Backup existing crontab
    crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # Install new crontab
    crontab "$SCRIPT_DIR/crontab-scheduled-changes"
    
    echo "Cron jobs installed successfully!"
    echo "Current cron jobs:"
    crontab -l
}

# Function to remove cron jobs
remove_cron() {
    echo "Removing scheduled change cron jobs..."
    
    # Remove the specific cron jobs (this is a simple approach)
    crontab -l | grep -v "process_scheduled_changes.py" | crontab -
    
    echo "Scheduled change cron jobs removed."
    echo "Remaining cron jobs:"
    crontab -l
}

# Function to show recent logs
show_logs() {
    echo "Recent scheduled changes logs:"
    echo "=============================="
    
    if [ -f "logs/scheduled_changes.log" ]; then
        echo "Last 20 entries from scheduled_changes.log:"
        tail -20 logs/scheduled_changes.log
    else
        echo "No scheduled_changes.log found"
    fi
    
    echo ""
    echo "Recent cron logs:"
    echo "================="
    
    if [ -f "logs/cron_scheduled_changes.log" ]; then
        echo "Last 10 entries from cron_scheduled_changes.log:"
        tail -10 logs/cron_scheduled_changes.log
    else
        echo "No cron_scheduled_changes.log found"
    fi
}

# Main command processing
case "${1:-help}" in
    "process")
        echo "Processing scheduled changes..."
        python scripts/process_scheduled_changes.py --verbose
        ;;
    "dry-run")
        echo "Running in dry-run mode..."
        python scripts/process_scheduled_changes.py --dry-run --verbose
        ;;
    "warnings")
        echo "Sending warning emails..."
        python scripts/process_scheduled_changes.py --warnings-only --verbose
        ;;
    "health")
        echo "Performing health check..."
        python scripts/process_scheduled_changes.py --health-check --verbose
        ;;
    "status")
        show_status
        ;;
    "install-cron")
        install_cron
        ;;
    "remove-cron")
        remove_cron
        ;;
    "logs")
        show_logs
        ;;
    "help"|*)
        show_usage
        ;;
esac