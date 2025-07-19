#!/bin/bash
# Setup domain configuration for donalert.invictamotus.com

set -e

echo "🌐 Setting up donalert.invictamotus.com domain configuration..."

# 1. Copy nginx configuration
echo "📋 Installing nginx configuration..."
sudo cp nginx_donalert.conf /etc/nginx/sites-available/donalert.invictamotus.com

# 2. Enable the site (remove default if exists)
echo "✅ Enabling nginx site..."
sudo ln -sf /etc/nginx/sites-available/donalert.invictamotus.com /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 3. Test nginx configuration
echo "🔍 Testing nginx configuration..."
sudo nginx -t

# 4. Install certbot if not present
if ! command -v certbot &> /dev/null; then
    echo "📦 Installing certbot..."
    sudo apt update
    sudo apt install -y certbot python3-certbot-nginx
fi

# 5. Get SSL certificate
echo "🔒 Obtaining SSL certificate..."
sudo certbot --nginx -d donalert.invictamotus.com --non-interactive --agree-tos --email admin@invictamotus.com

# 6. Reload nginx
echo "🔄 Reloading nginx..."
sudo systemctl reload nginx

# 7. Enable auto-renewal
echo "⏰ Setting up SSL auto-renewal..."
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

echo "✅ Domain setup complete!"
echo "🌐 Site available at: https://donalert.invictamotus.com"
echo ""
echo "Next steps:"
echo "1. Start the application: ./start_production.sh"
echo "2. Test the domain: curl -I https://donalert.invictamotus.com"