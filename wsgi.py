"""
WSGI Entry Point for Production Deployment with Socket.IO Support
"""
# Import gevent and patch BEFORE importing any other modules
from gevent import monkey
monkey.patch_all()

from app import create_app
from app.extensions import socketio

# Create Flask application
application = create_app()

# For Gunicorn with gevent worker class, gunicorn will serve the socketio.WSGIApp
# which includes both Flask and Socket.IO functionality
app = application

# For direct execution (development)
if __name__ == "__main__":
    socketio.run(application, debug=False)