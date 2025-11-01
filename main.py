# main.py - For Render.com deployment
import os
from flask import Flask
from database import init_db
from routes import setup_routes

def get_project_root():
    """Get the project root directory"""
    return os.path.dirname(os.path.abspath(__file__))

# Use this for all file operations
db_path = os.path.join(get_project_root(), 'sensor_data.db')

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key')
    setup_routes(app)
    return app

app = create_app()

# Initialize database
with app.app_context():
    init_db()


