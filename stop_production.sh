#!/bin/bash
# Stop production server

if [ -f gunicorn.pid ]; then
    PID=$(cat gunicorn.pid)
    echo "🛑 Stopping DonAlert (PID: $PID)"
    kill $PID
    rm -f gunicorn.pid
    echo "✅ Server stopped"
else
    echo "❌ No PID file found. Server may not be running."
fi