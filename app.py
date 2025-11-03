from flask import Flask
from database import create_tables, migrate_db, create_default_owner, debug_database
from routes import setup_routes
import os

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')

def init_app():
    print("Initializing StormSaver database...")
    create_tables()
    migrate_db()
    create_default_owner()
    debug_database()
    print("Database ready!")

with app.app_context():
    conn = get_db_connection()
    try:
        conn.execute("ALTER TABLE clients ADD COLUMN api_key TEXT")
        conn.execute("ALTER TABLE clients ADD COLUMN formatted_name TEXT")
        conn.execute("ALTER TABLE clients ADD COLUMN collection_interval INTEGER DEFAULT 10")
        conn.commit()
    except:
        pass  # Already exists
    conn.close()

setup_routes(app)

# KEEP THIS LINE EXACTLY
if __name__ == '__main__':
    print("StormSaver running locally: http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
