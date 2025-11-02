# database.py - FIXED VERSION: Proper indentation, no syntax errors, unified to 'clients' table
# Run this file once to initialize/migrate DB
# All references to 'users' replaced with 'clients' for consistency
# Owner is now in 'clients' table with role='owner'
# ALTER TABLE moved to safe migration function (run once)

import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from config import DB_PATH  # If you have config; otherwise ignore
from datetime import datetime
import os

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('sensor_data.db')
    conn.row_factory = sqlite3.Row
    return conn

def migrate_db():
    """Safely add new columns if they don't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE clients ADD COLUMN api_key TEXT")
        print("Added column: api_key")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            print(f"Migration warning (api_key): {e}")
    
    try:
        cursor.execute("ALTER TABLE clients ADD COLUMN formatted_name TEXT")
        print("Added column: formatted_name")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            print(f"Migration warning (formatted_name): {e}")
    
    conn.commit()
    conn.close()
    print("Migration complete")

def create_tables():
    """Create tables if not exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'client',
            places TEXT,
            email_enabled INTEGER DEFAULT 1,
            email TEXT,
            phone TEXT,
            address TEXT,
            collection_interval INTEGER DEFAULT 10,
            api_key TEXT UNIQUE,
            formatted_name TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place TEXT,
            client_place TEXT,
            temperature REAL,
            humidity REAL,
            warning TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS known_places (
            place TEXT PRIMARY KEY
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Tables created/verified")

def create_default_owner():
    """Create owner if not exists - now in clients table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM clients WHERE username = ?", ('owner',))
    if not cursor.fetchone():
        hashed = generate_password_hash('ownerpass')
        cursor.execute("""
            INSERT INTO clients 
            (username, password_hash, role, places, email_enabled, email, phone, address, collection_interval)
            VALUES (?, ?, 'owner', NULL, 1, 'owner@example.com', '+447000000001', 'Nottingham, UK', 10)
        """, ('owner', hashed))
        conn.commit()
        print("✅ Default owner created in clients table")
    else:
        print("ℹ️ Owner already exists")
    
    conn.close()

def add_client(username, password, place, email, phone, address, collection_interval, api_key):
    """Add new client with API key"""
    conn = get_db_connection()
    try:
        hashed = generate_password_hash(password)
        formatted_name = f"{username}_{place}_RESILIENT"
        conn.execute("""
            INSERT INTO clients 
            (username, password_hash, role, places, email_enabled, email, phone, address, collection_interval, api_key, formatted_name)
            VALUES (?, ?, 'client', ?, 1, ?, ?, ?, ?, ?, ?)
        """, (username, hashed, place, email, phone, address, collection_interval, api_key, formatted_name))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Add client error: {e}")
        return False
    finally:
        conn.close()

def get_user_by_username(username):
    """Get any user/client by username"""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM clients WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_client_password(username, new_password):
    """Update client password"""
    conn = get_db_connection()
    try:
        hashed = generate_password_hash(new_password)
        conn.execute("UPDATE clients SET password_hash = ? WHERE username = ?", (hashed, username))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Password update error: {e}")
        return False
    finally:
        conn.close()

def update_owner_password(username, new_password):
    """Alias for owner - same as client"""
    return update_client_password(username, new_password)

def update_user_email_enabled(username, enabled):
    """Toggle email alerts"""
    conn = get_db_connection()
    conn.execute("UPDATE clients SET email_enabled = ? WHERE username = ?", (enabled, username))
    conn.commit()
    conn.close()

def get_all_clients():
    """Get all clients for manage page"""
    conn = get_db_connection()
    rows = conn.execute("SELECT username, places, email, phone, address, email_enabled, collection_interval FROM clients WHERE role = 'client'").fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_client(username):
    """Delete client"""
    conn = get_db_connection()
    conn.execute("DELETE FROM clients WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def save_sensor_data(client_place, place, temperature, humidity, warning):
    """Save sensor reading"""
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO sensor_data (client_place, place, temperature, humidity, warning)
        VALUES (?, ?, ?, ?, ?)
    """, (client_place, place, temperature, humidity, warning))
    conn.commit()
    conn.close()

def debug_database():
    """Print DB state for debugging"""
    conn = get_db_connection()
    print("="*60)
    print("🔍 DATABASE DEBUG")
    
    clients = conn.execute("SELECT username, role, places, collection_interval, email_enabled FROM clients").fetchall()
    print(f"\n👥 CLIENTS ({len(clients)} total):")
    for client in clients:
        print(f"  - {client['username']} (Role: {client['role']}, Place: {client['places'] or 'N/A'}, Interval: {client['collection_interval']}s, Alerts: {'On' if client['email_enabled'] else 'Off'})")
    
    print(f"\n🔑 API KEYS CHECK:")
    for client in clients:
        if client['role'] == 'client':
            api = conn.execute("SELECT api_key FROM clients WHERE username = ?", (client['username'],)).fetchone()
            print(f"  - {client['username']}: {'HAS_KEY' if api and api['api_key'] else 'NO_KEY'}")
    
    sensor_count = conn.execute("SELECT COUNT(*) FROM sensor_data").fetchone()[0]
    print(f"\n📊 SENSOR DATA: {sensor_count} records")
    
    conn.close()
    print("="*60)

if __name__ == "__main__":
    create_tables()
    migrate_db()
    create_default_owner()
    debug_database()