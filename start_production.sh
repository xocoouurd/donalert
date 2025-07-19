#!/bin/bash
# Production startup script for DonAlert

# Set environment
export FLASK_ENV=production

# Activate virtual environment
source venv/bin/activate

# Apply any pending database migrations
flask db upgrade

# Start Gunicorn with configuration
gunicorn --config gunicorn.conf.py wsgi:application --daemon

echo "✅ DonAlert started in production mode"
echo "🌐 Server running on Unix socket: gunicorn.sock"
echo "🌍 Public URL: https://donalert.invictamotus.com"
echo "📊 Monitor logs: tail -f logs/gunicorn_error.log"
echo "🛑 Stop server: ./stop_production.sh"