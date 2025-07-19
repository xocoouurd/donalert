"""
WSGI Entry Point for Production Deployment with Socket.IO Support
"""
# Fix gevent monkey patching warning by patching early
import gevent.monkey
gevent.monkey.patch_all()

from app import create_app
from app.extensions import socketio

# Create Flask application
application = create_app()

# For Gunicorn with eventlet worker class, gunicorn will serve the socketio.WSGIApp
# which includes both Flask and Socket.IO functionality
app = application

# For direct execution (development)
if __name__ == "__main__":
    socketio.run(application, debug=False)