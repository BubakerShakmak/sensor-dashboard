# app.py - Sensor Monitoring System (Render-ready)
import os
from flask import Flask
from database import init_db
from routes import setup_routes

def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(get_project_root(), 'sensor_data.db')

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key')
    setup_routes(app)
    return app

app = create_app()

with app.app_context():
    init_db()


