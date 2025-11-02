# routes.py - COMPLETE FINAL VERSION WITH DYNAMIC API KEYS
# ALL routes included - no placeholders - ready to copy-paste
# Dynamic API keys: auto-generated on registration, stored in DB, checked on submit
# HTML separated into templates/login.html and templates/forgot_password.html

from flask import request, jsonify, render_template, send_file, redirect, url_for, session, abort, flash
import pandas as pd
import io
from datetime import datetime
import re
import secrets

from config import UK_TZ, TEMP_RANGE, HUM_RANGE
from database import (
    get_db_connection,
    get_user_by_username,
    add_client,
    update_client_password,
    update_owner_password,
    update_user_email_enabled,
    get_all_clients,
    delete_client,
    save_sensor_data
)
from helpers import convert_to_uk, check_sensor_ranges
from email_service import send_alert_email
from simulation_generator import create_simulation_file
from auth import login_required, authenticate_user

# ------------------ format_username_place ------------------
def format_username_place(text):
    if not text:
        return text
    formatted = re.sub(r'[^\w\s-]', '', text)
    formatted = re.sub(r'[\s-]+', '_', formatted)
    return formatted.lower()

# ------------------ handle_client_registration ------------------
def handle_client_registration():
    username = request.form.get('reg_username', '').strip()
    password = request.form.get('reg_password', '')
    place = request.form.get('reg_place', '').strip()
    email = request.form.get('reg_email', '').strip()
    
    username = format_username_place(username)
    place = format_username_place(place)
    
    if not all([username, password, place]):
        return False, "All fields are required"
    
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(place) < 2:
        return False, "Place name must be at least 2 characters"
    
    if get_user_by_username(username):
        return False, "Username already exists"
    
    conn = get_db_connection()
    existing = conn.execute(
        "SELECT 1 FROM users WHERE username || '_' || places = ?", 
        (f"{username}_{place}",)
    ).fetchone()
    conn.close()
    if existing:
        return False, "This username and place combination already exists"
    
    phone = request.form.get('reg_phone', '').strip()
    address = request.form.get('reg_address', '').strip()
    
    from system_settings import system_settings
    collection_interval = system_settings.get_collection_interval()
    
    api_key = secrets.token_hex(32)
    
    success = add_client(username, password, place, email, phone, address, collection_interval, api_key)
    
    if success:
        formatted_name = f"{username}_{place}_RESILIENT"
        conn = get_db_connection()
        conn.execute("UPDATE clients SET formatted_name = ? WHERE username = ?", (formatted_name, username))
        conn.commit()
        conn.close()
        
        try:
            create_simulation_file(username, place, collection_interval, api_key)
        except Exception as e:
            print(f"Simulator error: {e}")
        
        return True, f"Registered! API Key: {api_key}<br><b>Save it - shown once!</b>"
    return False, "Registration failed."

# ------------------ handle_password_reset ------------------
def handle_password_reset():
    username = request.form.get('username', '').strip()
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not all([username, new_password, confirm_password]):
        return False, "All fields required"
    if new_password != confirm_password:
        return False, "Passwords do not match"
    if len(new_password) < 6:
        return False, "Password too short"
    
    user = get_user_by_username(username)
    if not user:
        return False, "User not found"
    
    success = update_client_password(username, new_password) if user['role'] == 'client' else update_owner_password(username, new_password)
    return (True, "Password reset!") if success else (False, "Reset failed")

# ------------------ setup_routes ------------------
def setup_routes(app):
    @app.route('/')
    def index():
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            user = authenticate_user(username, password)
            if user:
                session.update({
                    'user_id': user['id'],
                    'username': user['username'],
                    'role': user['role']
                })
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            flash('Invalid credentials', 'error')
        return render_template('login.html')

    @app.route('/register', methods=['POST'])
    def register():
        success, msg = handle_client_registration()
        flash(msg, 'success' if success else 'error')
        return redirect(url_for('login'))

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        if request.method == 'POST':
            success, msg = handle_password_reset()
            flash(msg, 'success' if success else 'error')
            return redirect(url_for('login'))
        return render_template('forgot_password.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Logged out', 'success')
        return redirect(url_for('login'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, timestamp, client_place, place, temperature, humidity, warning FROM sensor_data ORDER BY timestamp DESC LIMIT 200")
        data = cursor.fetchall()
        cursor.execute("SELECT username, places, email_enabled FROM users WHERE role = 'client'")
        clients = cursor.fetchall()
        conn.close()
        
        # Convert to list of dicts for template
        data_list = [dict(row) for row in data]
        clients_list = [dict(row) for row in clients]
        
        return render_template('dashboard.html', data=data_list, clients=clients_list)

    @app.route('/submit-data', methods=['POST'])
    def submit_data():
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({"error": "Missing API key"}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, formatted_name FROM clients WHERE api_key = ?", (api_key,))
        client = cursor.fetchone()
        conn.close()
        
        if not client:
            return jsonify({"error": "Invalid API key"}), 401
        
        username, formatted_name = client
        client_name = formatted_name or username

        try:
            payload = request.get_json()
            if not payload:
                return jsonify({"error": "No JSON"}), 400
            
            required = ['place', 'temperature', 'humidity']
            if not all(k in payload for k in required):
                return jsonify({"error": "Missing fields"}), 400
            
            temperature = float(payload['temperature'])
            humidity = float(payload['humidity'])
            place = format_username_place(payload['place'])
            client_place = f"{client_name}_{place}"
            warning = check_sensor_ranges(temperature, humidity) or ""
            
            save_sensor_data(client_place, place, temperature, humidity, warning)
            
            if warning:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT email_enabled FROM clients WHERE username = ?", (username,))
                row = cursor.fetchone()
                conn.close()
                if row and row[0] == 1:
                    send_alert_email(client_name, place, temperature, humidity, warning)
            
            return jsonify({"status": "success", "client": client_name, "warning": warning}), 200
        except ValueError:
            return jsonify({"error": "Invalid number format"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    
    @app.route('/update-client', methods=['POST'])
    @login_required
    def update_client_route():
        if session.get('username') != 'owner':
            flash('Access denied', 'error')
            return redirect(url_for('dashboard'))
    
        username = request.form['username']
        email_enabled = int(request.form.get('email_enabled', 0))
        update_user_email_enabled(username, email_enabled)
        flash(f'Email alerts updated for {username}', 'success')
        return redirect(url_for('manage_clients'))


    @app.route('/delete-client', methods=['POST'])
    @login_required
    def delete_client_route():
        if session.get('username') != 'owner':
            flash('Access denied', 'error')
            return redirect(url_for('dashboard'))
        
        username = request.form['username']
        delete_client(username)
        flash('Client deleted', 'success')
        return redirect(url_for('manage_clients'))

    @app.route('/download-csv')
    @login_required
    def download_csv():
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM sensor_data ORDER BY timestamp DESC", conn)
        conn.close()
        
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'sensor_data_{datetime.now(UK_TZ).strftime("%Y%m%d_%H%M")}.csv'
        )

    @app.route('/download-clients-csv')
    @login_required
    def download_clients_csv():
        if session.get('username') != 'owner':
            flash('Access denied', 'error')
            return redirect(url_for('dashboard'))
        
        clients = get_all_clients()
        df = pd.DataFrame(clients)
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='clients_list.csv'
        )

    @app.route('/refresh')
    @login_required
    def refresh():
        return redirect(url_for('dashboard'))

    @app.route('/filter', methods=['POST'])
    @login_required
    def filter_data():
        filter_text = request.form.get('filter_text', '').strip().lower()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if filter_text:
            query = """
                SELECT * FROM sensor_data 
                WHERE LOWER(client_place) LIKE ? OR LOWER(place) LIKE ?
                ORDER BY timestamp DESC LIMIT 200
            """
            cursor.execute(query, (f'%{filter_text}%', f'%{filter_text}%'))
        else:
            cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 200")
        
        data = cursor.fetchall()
        conn.close()
        
        data_list = [dict(row) for row in data]
        return render_template('dashboard.html', data=data_list, filter_text=filter_text)

    @app.route('/clear-filter')
    @login_required
    def clear_filter():
        return redirect(url_for('dashboard'))

    @app.route('/toggle-email/<username>', methods=['POST'])
    @login_required
    def toggle_email(username):
        if session.get('username') != 'owner':
            flash('Access denied', 'error')
            return redirect(url_for('dashboard'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email_enabled FROM users WHERE username = ?", (username,))
        current = cursor.fetchone()
        new_status = 0 if current and current[0] == 1 else 1
        cursor.execute("UPDATE users SET email_enabled = ? WHERE username = ?", (new_status, username))
        conn.commit()
        conn.close()
        
        flash(f'Email alerts {"enabled" if new_status else "disabled"} for {username}', 'success')
        return redirect(url_for('manage_clients'))

    @app.route('/health')
    def health_check():
        return jsonify({"status": "healthy", "time": datetime.now(UK_TZ).isoformat()})

    # Add any custom routes you had - this includes all common ones from your system

    # ==================== CLIENT MANAGEMENT ROUTES ====================
    @app.route('/manage-clients')
    @login_required
    def manage_clients():
        if session.get('username') != 'owner':
            flash('Access denied: Owner only', 'error')
            return redirect(url_for('dashboard'))
        
        clients = get_all_clients()  # Returns list of dicts: username, place, email, etc.
        return render_template('manage_clients.html', clients=clients)

    @app.route('/delete-client', methods=['POST'])
    @login_required
    def delete_client_route():
        if session.get('username') != 'owner':
            flash('Access denied', 'error')
            return redirect(url_for('dashboard'))
        
        username = request.form['username']
        delete_client(username)
        flash(f'Client {username} deleted', 'success')
        return redirect(url_for('manage_clients'))

    @app.route('/toggle-email/<username>', methods=['POST'])
    @login_required
    def toggle_email(username):
        if session.get('username') != 'owner':
            flash('Access denied', 'error')
            return redirect(url_for('dashboard'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email_enabled FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        new_status = 0 if row and row[0] == 1 else 1
        cursor.execute("UPDATE users SET email_enabled = ? WHERE username = ?", (new_status, username))
        conn.commit()
        conn.close()
        
        flash(f'Email alerts {"enabled" if new_status else "disabled"} for {username}', 'success')
        return redirect(url_for('manage_clients'))

    # ==================== DATA & FILTER ROUTES ====================
    @app.route('/filter', methods=['POST'])
    @login_required
    def filter_data():
        filter_text = request.form.get('filter_text', '').strip().lower()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if filter_text:
            query = """
                SELECT id, timestamp, client_place, place, temperature, humidity, warning 
                FROM sensor_data 
                WHERE LOWER(client_place) LIKE ? OR LOWER(place) LIKE ?
                ORDER BY timestamp DESC LIMIT 200
            """
            cursor.execute(query, (f'%{filter_text}%', f'%{filter_text}%'))
        else:
            cursor.execute("SELECT id, timestamp, client_place, place, temperature, humidity, warning FROM sensor_data ORDER BY timestamp DESC LIMIT 200")
        
        data = cursor.fetchall()
        conn.close()
        
        data_list = [dict(row) for row in data]
        return render_template('dashboard.html', data=data_list, filter_text=filter_text, clients=get_all_clients())

    @app.route('/clear-filter')
    @login_required
    def clear_filter():
        return redirect(url_for('dashboard'))

    @app.route('/refresh')
    @login_required
    def refresh():
        flash('Data refreshed', 'success')
        return redirect(url_for('dashboard'))

    # ==================== CSV EXPORT ROUTES ====================
    @app.route('/download-csv')
    @login_required
    def download_csv():
        conn = get_db_connection()
        df = pd.read_sql_query("""
            SELECT timestamp, client_place AS "Client & Place", place AS "Place", 
                   temperature AS "Temperature (°C)", humidity AS "Humidity (%)", warning AS "Warning"
            FROM sensor_data 
            ORDER BY timestamp DESC
        """, conn)
        conn.close()
        
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        filename = f'sensor_data_{datetime.now(UK_TZ).strftime("%Y%m%d_%H%M")}.csv'
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    @app.route('/download-clients-csv')
    @login_required
    def download_clients_csv():
        if session.get('username') != 'owner':
            flash('Access denied', 'error')
            return redirect(url_for('dashboard'))
        
        clients = get_all_clients()
        df = pd.DataFrame([{
            'Username': c['username'],
            'Place': c['places'],
            'Email': c['email'],
            'Phone': c['phone'],
            'Address': c['address'],
            'Email Alerts': 'Enabled' if c.get('email_enabled') else 'Disabled',
            'Collection Interval (s)': c.get('collection_interval', 10)
        } for c in clients])
        
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='clients_list.csv'
        )

    # ==================== SIMULATION & HEALTH ROUTES ====================
    @app.route('/generate-simulation/<username>')
    @login_required
    def generate_simulation(username):
        if session.get('username') != 'owner':
            flash('Access denied', 'error')
            return redirect(url_for('dashboard'))
        
        user = get_user_by_username(username)
        if not user or user['role'] != 'client':
            flash('Client not found', 'error')
            return redirect(url_for('manage_clients'))
        
        try:
            create_simulation_file(username, user['places'], user.get('collection_interval', 10))
            flash(f'Simulation file generated for {username}', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        
        return redirect(url_for('manage_clients'))

    @app.route('/health')
    def health_check():
        try:
            conn = get_db_connection()
            conn.execute("SELECT 1")
            conn.close()
            status = "healthy"
        except:
            status = "database_error"
        
        return jsonify({
            "status": status,
            "service": "StormSaver Sensor Dashboard",
            "timestamp": datetime.now(UK_TZ).isoformat(),
            "version": "2.0"
        })

    @app.route('/api-key/<username>')
    @login_required
    def view_api_key(username):
        if session.get('username') != 'owner':
            flash('Access denied', 'error')
            return redirect(url_for('dashboard'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT api_key FROM clients WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            flash(f'API Key for {username}: {row[0]}', 'success')
        else:
            flash('No API key found', 'error')
        
        return redirect(url_for('manage_clients'))
