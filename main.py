# main.py - For Render.com deployment
import os
from flask import Flask
from database import init_db
from routes import setup_routes

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    setup_routes(app)
    return app

app = create_app()

# Initialize database
@app.before_first_request
def create_tables():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)