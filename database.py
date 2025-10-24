# database.py
import sqlite3
from werkzeug.security import generate_password_hash
from config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    create_tables(c)
    create_default_users(c)
    create_default_places(c)
    
    conn.commit()
    conn.close()

def create_tables(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT,
        places TEXT,
        email_enabled INTEGER DEFAULT 1,
        email TEXT,
        phone TEXT,
        address TEXT
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        place TEXT,
        client_place TEXT,  -- New column: combination of client + place
        temperature REAL,
        humidity REAL,
        warning TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS known_places (
        place TEXT PRIMARY KEY
    )""")

def create_default_users(cursor):
    defaults = [
        ('owner', 'ownerpass', 'owner', None, 1, 'owner@example.com', '+447000000001', 'Nottingham, UK'),
        ('client1', 'client1pass', 'client', 'Office1', 1, 'client1@example.com', '+447000000002', 'Office1, London')
    ]
    
    for u, p, r, pl, e, email, phone, address in defaults:
        cursor.execute('SELECT id FROM users WHERE username=?', (u,))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO users(username,password_hash,role,places,email_enabled,email,phone,address) VALUES (?,?,?,?,?,?,?,?)',
                          (u, generate_password_hash(p), r, pl, e, email, phone, address))

def create_default_places(cursor):
    default_places = ['client1_Office1']  # Updated format
    for p in default_places:
        cursor.execute('INSERT OR IGNORE INTO known_places (place) VALUES (?)', (p,))

def get_user_by_username(username):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_places_all():
    conn = get_db_connection()
    # Get unique client_place combinations instead of just place names
    rows = conn.execute("""
        SELECT DISTINCT client_place 
        FROM sensor_data 
        WHERE client_place IS NOT NULL 
        ORDER BY client_place
    """).fetchall()
    conn.close()
    return [r[0] for r in rows] if rows else ['client1_Office1']

def get_allowed_places_for_user(username):
    user = get_user_by_username(username)
    if not user: return []
    if user['role'] == 'owner': return get_places_all()
    if user['places']: 
        # For clients, show their specific client_place combination
        client_place = f"{user['username']}_{user['places']}"  # Updated format
        return [client_place]
    return []

def get_client_status():
    conn = get_db_connection()
    rows = conn.execute("SELECT username,email_enabled FROM users WHERE role='client'").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_clients():
    conn = get_db_connection()
    clients = conn.execute("SELECT username, places, email, phone, address, email_enabled FROM users WHERE role='client'").fetchall()
    conn.close()
    return clients

def get_client_by_username(username):
    conn = get_db_connection()
    client = conn.execute("SELECT username, places, email, phone, address, email_enabled FROM users WHERE username=? AND role='client'", (username,)).fetchone()
    conn.close()
    return dict(client) if client else None

def save_sensor_data(place, client_place, temperature, humidity, warning):
    conn = get_db_connection()
    conn.execute('INSERT INTO sensor_data(place, client_place, temperature, humidity, warning) VALUES(?,?,?,?,?)',
                (place, client_place, temperature, humidity, warning))
    conn.commit()
    conn.close()

def get_client_for_place(client_place):
    # Extract username from client_place format: "username_place"
    if '_' in client_place:
        username = client_place.split('_')[0]  # Get first part (username)
    else:
        username = client_place
    
    conn = get_db_connection()
    row = conn.execute("SELECT email,email_enabled FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_user_email_enabled(username, enabled):
    conn = get_db_connection()
    conn.execute('UPDATE users SET email_enabled=? WHERE username=?',(enabled, username))
    conn.commit()
    conn.close()

def add_client(username, password, place, email, phone, address):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO users (username,password_hash,role,places,email_enabled,email,phone,address)
            VALUES (?,?, 'client', ?,1,?,?,?)
        """, (username, generate_password_hash(password), place, email, phone, address))
        # Add the combined client_place to known_places (username_place format)
        client_place = f"{username}_{place}"  # Updated format
        conn.execute("INSERT OR IGNORE INTO known_places (place) VALUES (?)", (client_place,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_client(username, place, email, phone, address, email_enabled):
    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE users 
            SET places=?, email=?, phone=?, address=?, email_enabled=?
            WHERE username=? AND role='client'
        """, (place, email, phone, address, email_enabled, username))
        # Update the combined client_place in known_places (username_place format)
        client_place = f"{username}_{place}"  # Updated format
        conn.execute("INSERT OR IGNORE INTO known_places (place) VALUES (?)", (client_place,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating client: {e}")
        return False
    finally:
        conn.close()

def delete_client(username):
    conn = get_db_connection()
    try:
        # Delete the user
        conn.execute("DELETE FROM users WHERE username=? AND role='client'", (username,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting client: {e}")
        return False
    finally:
        conn.close()

def update_client_password(username, new_password):
    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE users 
            SET password_hash=?
            WHERE username=? AND role='client'
        """, (generate_password_hash(new_password), username))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating password: {e}")
        return False
    finally:
        conn.close()