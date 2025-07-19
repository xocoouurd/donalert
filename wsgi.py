"""
WSGI Entry Point for Production Deployment
"""
from app import create_app
from app.extensions import socketio

# Create Flask application
application = create_app()

# For Gunicorn with SocketIO support
if __name__ == "__main__":
    socketio.run(application, debug=False)