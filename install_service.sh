#!/bin/bash
# Install DonAlert as a systemd service

set -e

echo "🔧 Installing DonAlert systemd service..."

# 1. Copy service file
echo "📋 Installing service file..."
sudo cp donalert.service /etc/systemd/system/

# 2. Reload systemd
echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload

# 3. Enable service
echo "✅ Enabling DonAlert service..."
sudo systemctl enable donalert

# 4. Set correct permissions for socket directory
echo "🔐 Setting permissions..."
sudo mkdir -p /srv/www/donalert.invictamotus.com/logs
sudo chown -R xocoo:xocoo /srv/www/donalert.invictamotus.com

echo "✅ Service installed successfully!"
echo ""
echo "Service commands:"
echo "  sudo systemctl start donalert     # Start service"
echo "  sudo systemctl stop donalert      # Stop service" 
echo "  sudo systemctl restart donalert   # Restart service"
echo "  sudo systemctl status donalert    # Check status"
echo "  sudo systemctl enable donalert    # Enable auto-start"
echo "  sudo systemctl disable donalert   # Disable auto-start"
echo ""
echo "Logs:"
echo "  sudo journalctl -u donalert -f    # Follow service logs"
echo "  tail -f logs/gunicorn_error.log   # Follow app logs"