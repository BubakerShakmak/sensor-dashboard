from flask import Flask
from routes import setup_routes
from database import get_db_connection
import sqlite3
import os
from datetime import datetime
from config import UK_TZ

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'super-secret-storm-key-2025')

# ====================== DATABASE INIT ======================
print("Initializing StormSaver database...")
conn = get_db_connection()
cursor = conn.cursor()

# Create tables if not exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        places TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        email_enabled INTEGER DEFAULT 1,
        collection_interval INTEGER DEFAULT 10,
        api_key TEXT,
        formatted_name TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        client_place TEXT,
        place TEXT,
        temperature REAL,
        humidity REAL,
        warning TEXT
    )
''')

# Add missing columns if needed
try:
    cursor.execute("ALTER TABLE clients ADD COLUMN api_key TEXT")
except sqlite3.OperationalError:
    pass
try:
    cursor.execute("ALTER TABLE clients ADD COLUMN formatted_name TEXT")
except sqlite3.OperationalError:
    pass
try:
    cursor.execute("ALTER TABLE clients ADD COLUMN collection_interval INTEGER DEFAULT 10")
except sqlite3.OperationalError:
    pass

conn.commit()

# Default owner
cursor.execute("SELECT 1 FROM clients WHERE username = 'owner'")
if not cursor.fetchone():
    from auth import hash_password
    hashed = hash_password('ownerpass')
    cursor.execute("INSERT INTO clients (username, password, role, places) VALUES (?, ?, 'owner', 'N/A')", ('owner', hashed))
    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'owner')", ('owner', hashed))
    conn.commit()
    print("✅ Default owner created in clients table")

# Debug print
cursor.execute("SELECT username, role, places, collection_interval, email_enabled FROM clients")
clients = cursor.fetchall()
print("=============================================================")
print("🔍 DATABASE DEBUG")
print(f"👥 CLIENTS ({len(clients)} total):")
for c in clients:
    print(f"  - {c[0]} (Role: {c[1]}, Place: {c[2]}, Interval: {c[3]}s, Alerts: {'On' if c[4] else 'Off'})")
cursor.execute("SELECT api_key FROM clients WHERE api_key IS NOT NULL")
keys = cursor.fetchall()
print("🔑 API KEYS CHECK:")
for k in keys:
    print(f"   Key exists for client")
cursor.execute("SELECT COUNT(*) FROM sensor_data")
count = cursor.fetchone()[0]
print(f"📊 SENSOR DATA: {count} records")
print("=============================================================")
print("Database ready!")
conn.close()

# ====================== SETUP ROUTES ======================
setup_routes(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
