# routes.py
from flask import request, jsonify, render_template_string, send_file, redirect, url_for, session
import pandas as pd
import io
from datetime import datetime

from config import UK_TZ, TEMP_RANGE, HUM_RANGE
from templates import LOGIN_TEMPLATE, HTML_TEMPLATE
from database import (
    get_user_by_username, get_allowed_places_for_user, get_client_status, 
    get_all_clients, save_sensor_data, update_user_email_enabled,
    get_db_connection, add_client, update_client, delete_client,
    get_client_by_username, update_client_password
)
from helpers import convert_to_uk, check_sensor_ranges
from email_service import send_alert_email
from simulation_generator import create_simulation_file
from auth import login_required, authenticate_user

# ------------------ Helper Functions ------------------
def get_all_latest_data():
    conn = get_db_connection()
    query = """
    SELECT id, timestamp, place, temperature, humidity, warning
    FROM (
        SELECT id, timestamp, place, temperature, humidity, warning,
               ROW_NUMBER() OVER (PARTITION BY place ORDER BY timestamp DESC, id DESC) AS rn
        FROM sensor_data
    )
    WHERE rn=1
    ORDER BY place;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["timestamp"] = df["timestamp"].apply(convert_to_uk)
    return jsonify(df.to_dict(orient='records'))

def get_single_latest_data(place):
    conn = get_db_connection()
    row = conn.execute("SELECT id,timestamp,place,temperature,humidity,warning FROM sensor_data WHERE place=? ORDER BY timestamp DESC,id DESC LIMIT 1",(place,)).fetchone()
    conn.close()
    
    if not row: return jsonify(None)
    d = dict(row)
    d["timestamp"] = convert_to_uk(d["timestamp"])
    return jsonify(d)

def download_all_csv():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id,timestamp,place,temperature,humidity,warning FROM sensor_data ORDER BY timestamp DESC,id DESC",conn)
    conn.close()
    return create_csv_response(df, "All")

def download_single_csv(place):
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id,timestamp,place,temperature,humidity,warning FROM sensor_data WHERE place=? ORDER BY timestamp DESC,id DESC",conn,params=(place,))
    conn.close()
    return create_csv_response(df, place)

def create_csv_response(df, place_name):
    df["timestamp"] = df["timestamp"].apply(convert_to_uk)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    fname = f"{place_name}_{datetime.now(UK_TZ).strftime('%Y%m%d_%H%M%S')}_UK.csv"
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name=fname)

def handle_add_client():
    username = request.form.get('username','').strip()
    password = request.form.get('password','').strip()
    place = request.form.get('place','').strip()
    email = request.form.get('email','').strip()
    phone = request.form.get('phone','').strip()
    address = request.form.get('address','').strip()

    if username and password and place:
        success = add_client(username, password, place, email, phone, address)
        if success:
            try:
                create_simulation_file(username, place)
            except Exception as e:
                print(f"Error creating simulation file: {e}")
        return success
    return False

def handle_update_client():
    username = request.form.get('username','').strip()
    place = request.form.get('place','').strip()
    email = request.form.get('email','').strip()
    phone = request.form.get('phone','').strip()
    address = request.form.get('address','').strip()
    email_enabled = 1 if request.form.get('email_enabled') == 'on' else 0

    if username and place:
        return update_client(username, place, email, phone, address, email_enabled)
    return False

def handle_delete_client():
    username = request.form.get('username','').strip()
    if username:
        return delete_client(username)
    return False

def handle_update_password():
    username = request.form.get('username','').strip()
    new_password = request.form.get('new_password','').strip()
    
    if username and new_password:
        return update_client_password(username, new_password)
    return False

def render_clients_management_page(clients, message=None):
    html = """<!DOCTYPE html><html><head><title>Manage Clients</title>
    <style>
    body {font-family:Arial;margin:40px;background:#f5f5f5;}
    .container {max-width:1200px;margin:auto;}
    table {border-collapse:collapse;width:100%;margin-top:20px;background:white;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
    th,td {border:1px solid #ddd;padding:12px;text-align:center;}
    .message {padding:12px;margin:15px 0;border-radius:6px;font-weight:bold;}
    .success {background-color:#d4edda;color:#155724;border:1px solid #c3e6cb;}
    .error {background-color:#f8d7da;color:#721c24;border:1px solid #f5c6cb;}
    .actions {display:flex;gap:8px;justify-content:center;}
    .btn {padding:6px 12px;text-decoration:none;border-radius:4px;font-size:0.9em;border:none;cursor:pointer;transition:background-color 0.2s;}
    .btn-edit {background-color:#007bff;color:white;}
    .btn-edit:hover {background-color:#0056b3;}
    .btn-delete {background-color:#dc3545;color:white;}
    .btn-delete:hover {background-color:#c82333;}
    .btn-password {background-color:#28a745;color:white;}
    
    /* Form Styles */
    .form-container {background:white;padding:25px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);margin:20px 0;}
    .form-title {color:#333;margin-bottom:20px;padding-bottom:10px;border-bottom:2px solid #007bff;}
    .form-grid {display:grid;grid-template-columns:1fr 1fr;gap:20px;}
    .form-group {display:flex;flex-direction:column;margin-bottom:15px;}
    .form-group.full-width {grid-column:1 / -1;}
    .form-label {font-weight:bold;margin-bottom:6px;color:#555;}
    .form-input {padding:10px;border:2px solid #e1e1e1;border-radius:4px;font-size:14px;transition:border-color 0.2s;}
    .form-input:focus {outline:none;border-color:#007bff;box-shadow:0 0 0 2px rgba(0,123,255,0.25);}
    .form-input:required {border-left:3px solid #dc3545;}
    .form-input:required:valid {border-left:3px solid #28a745;}
    .form-submit {background:#007bff;color:white;padding:12px 30px;border:none;border-radius:4px;font-size:16px;cursor:pointer;transition:background-color 0.2s;margin-top:10px;}
    .form-submit:hover {background:#0056b3;}
    .form-help {font-size:12px;color:#666;margin-top:4px;}
    
    /* Header Styles */
    .header {background:white;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-bottom:20px;}
    .header-links {display:flex;gap:15px;align-items:center;}
    .header-links a {color:#007bff;text-decoration:none;padding:8px 12px;border-radius:4px;transition:background-color 0.2s;}
    .header-links a:hover {background-color:#f8f9fa;}
    
    /* Table Header */
    .table-header {background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);color:white;}
    
    /* Responsive */
    @media (max-width: 768px) {
        .form-grid {grid-template-columns:1fr;}
        body {margin:20px;}
    }
    </style></head><body>
    <div class="container">
    <div class="header">
        <h2>Client Management</h2>
        <div class="header-links">
            <a href="{{ url_for('index') }}">← Back to Dashboard</a>
            <a href="{{ url_for('download_clients_csv') }}">⬇ Download Clients CSV</a>
        </div>
    </div>
    
    {% if message %}
    <div class="message {{ 'success' if 'success' in message else 'error' }}">{{ message }}</div>
    {% endif %}
    
    <div class="form-container">
        <h3 class="form-title">Add New Client</h3>
        <form method="post" action="{{ url_for('clients_page') }}">
            <input type="hidden" name="action" value="add">
            <div class="form-grid">
                <div class="form-group">
                    <label class="form-label" for="username">Username *</label>
                    <input class="form-input" type="text" name="username" required placeholder="Enter unique username">
                    <div class="form-help">This will be used for login</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="password">Password *</label>
                    <input class="form-input" type="password" name="password" required placeholder="Enter secure password">
                    <div class="form-help">Minimum 6 characters</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="place">Office Name *</label>
                    <input class="form-input" type="text" name="place" required placeholder="e.g., Building1, Office2">
                    <div class="form-help">Physical location name</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="email">Email</label>
                    <input class="form-input" type="email" name="email" placeholder="client@example.com">
                    <div class="form-help">For email alerts</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="phone">Phone</label>
                    <input class="form-input" type="text" name="phone" placeholder="+447000000000">
                    <div class="form-help">International format</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="address">Address</label>
                    <input class="form-input" type="text" name="address" placeholder="Street, City, Postcode">
                    <div class="form-help">Physical address</div>
                </div>
            </div>
            <button type="submit" class="form-submit">Add Client</button>
        </form>
    </div>

    <h3 style="color:#333;margin-top:30px;">Existing Clients</h3>
    <table>
    <tr class="table-header"><th>Username</th><th>Place</th><th>Email</th><th>Phone</th><th>Address</th><th>Email Enabled</th><th>Actions</th></tr>
    {% for c in clients %}
    <tr>
      <td>{{c.username}}</td>
      <td>{{c.places}}</td>
      <td>{{c.email or '-'}}</td>
      <td>{{c.phone or '-'}}</td>
      <td>{{c.address or '-'}}</td>
      <td>{% if c.email_enabled %}✅{% else %}<b style="color:red;">❌</b>{% endif %}</td>
      <td class="actions">
        <a href="{{ url_for('edit_client_page', username=c.username) }}" class="btn btn-edit">Edit</a>
        <form method="post" action="{{ url_for('clients_page') }}" style="display:inline;">
          <input type="hidden" name="username" value="{{c.username}}">
          <input type="hidden" name="action" value="delete">
          <button type="submit" class="btn btn-delete" onclick="return confirm('Are you sure you want to delete {{c.username}}?')">Delete</button>
        </form>
      </td>
    </tr>
    {% endfor %}
    </table>
    </div>
    </body></html>"""
    return render_template_string(html, clients=clients, message=message)

def render_edit_client_page(client):
    html = """<!DOCTYPE html><html><head><title>Edit Client</title>
    <style>
    body {font-family:Arial;margin:40px;background:#f5f5f5;}
    .container {max-width:800px;margin:auto;}
    .form-container {background:white;padding:30px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);}
    .form-title {color:#333;margin-bottom:25px;padding-bottom:15px;border-bottom:2px solid #007bff;}
    .form-group {margin:20px 0;}
    .form-label {display:block;font-weight:bold;margin-bottom:8px;color:#555;}
    .form-input {padding:12px;border:2px solid #e1e1e1;border-radius:4px;font-size:14px;width:100%;box-sizing:border-box;transition:border-color 0.2s;}
    .form-input:focus {outline:none;border-color:#007bff;box-shadow:0 0 0 2px rgba(0,123,255,0.25);}
    .btn {padding:12px 24px;margin:5px;text-decoration:none;border-radius:4px;border:none;cursor:pointer;transition:background-color 0.2s;font-size:14px;}
    .btn-save {background-color:#28a745;color:white;}
    .btn-save:hover {background-color:#218838;}
    .btn-cancel {background-color:#6c757d;color:white;}
    .btn-cancel:hover {background-color:#5a6268;}
    .btn-password {background-color:#17a2b8;color:white;}
    .btn-password:hover {background-color:#138496;}
    .section {margin:30px 0;padding:20px;background:#f8f9fa;border-radius:6px;}
    .checkbox-group {display:flex;align-items:center;gap:10px;}
    .checkbox-group input[type="checkbox"] {transform:scale(1.2);}
    </style></head><body>
    <div class="container">
    <div class="form-container">
    <h2 class="form-title">Edit Client: {{ client.username }}</h2>
    <a href="{{ url_for('clients_page') }}" class="btn btn-cancel">← Back to Clients</a>
    
    <div class="section">
    <form method="post" action="{{ url_for('clients_page') }}">
      <input type="hidden" name="action" value="update">
      <input type="hidden" name="username" value="{{ client.username }}">
      
      <div class="form-group">
        <label class="form-label">Username:</label>
        <strong style="font-size:16px;color:#333;">{{ client.username }}</strong>
      </div>
      
      <div class="form-group">
        <label class="form-label" for="place">Office Name:</label>
        <input class="form-input" type="text" name="place" value="{{ client.places }}" required>
      </div>
      
      <div class="form-group">
        <label class="form-label" for="email">Email:</label>
        <input class="form-input" type="email" name="email" value="{{ client.email or '' }}" placeholder="client@example.com">
      </div>
      
      <div class="form-group">
        <label class="form-label" for="phone">Phone:</label>
        <input class="form-input" type="text" name="phone" value="{{ client.phone or '' }}" placeholder="+447000000000">
      </div>
      
      <div class="form-group">
        <label class="form-label" for="address">Address:</label>
        <input class="form-input" type="text" name="address" value="{{ client.address or '' }}" placeholder="Street, City, Postcode">
      </div>
      
      <div class="form-group">
        <div class="checkbox-group">
          <input type="checkbox" name="email_enabled" id="email_enabled" {{ 'checked' if client.email_enabled }}>
          <label class="form-label" for="email_enabled" style="margin:0;">Enable email alerts</label>
        </div>
      </div>
      
      <button type="submit" class="btn btn-save">Save Changes</button>
    </form>
    </div>
    
    <div class="section">
    <h3 style="color:#333;margin-bottom:15px;">Change Password</h3>
    <form method="post" action="{{ url_for('clients_page') }}">
      <input type="hidden" name="action" value="update_password">
      <input type="hidden" name="username" value="{{ client.username }}">
      
      <div class="form-group">
        <label class="form-label" for="new_password">New Password:</label>
        <input class="form-input" type="password" name="new_password" required placeholder="Enter new password">
      </div>
      
      <button type="submit" class="btn btn-password">Update Password</button>
    </form>
    </div>
    </div>
    </div>
    </body></html>"""
    return render_template_string(html, client=client)

# ------------------ Route Setup Function ------------------
def setup_routes(app):
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            u = request.form.get('username','').strip()
            p = request.form.get('password','')
            user = authenticate_user(u, p)
            if user:
                session['username'] = u
                session['role'] = user['role']
                return redirect(url_for('index'))
            return render_template_string(LOGIN_TEMPLATE, error='Invalid credentials')
        return render_template_string(LOGIN_TEMPLATE, error=None)

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/')
    @login_required
    def index():
        u = session['username']
        role = session.get('role', 'client')
        user = get_user_by_username(u)
        places = get_allowed_places_for_user(u)
        
        if role == 'owner':
            places = ['All'] + places
        
        client_status = []
        if role == 'owner':
            client_status = get_client_status()
        
        return render_template_string(HTML_TEMPLATE,
            username=u, role=role, places=places,
            email_enabled=user.get('email_enabled',1),
            client_status=client_status,
            temp_min=TEMP_RANGE[0], temp_max=TEMP_RANGE[1],
            hum_min=HUM_RANGE[0], hum_max=HUM_RANGE[1])

    @app.route('/toggle-email', methods=['POST'])
    @login_required
    def toggle_email():
        u = session['username']
        user = get_user_by_username(u)
        
        if user['role'] != 'client':
            return jsonify({'error':'only clients can toggle'}),403
        
        new_val = 0 if user['email_enabled'] else 1
        update_user_email_enabled(u, new_val)
        return jsonify({'enabled':bool(new_val)})

    @app.route('/latest-data')
    @login_required
    def latest_data():
        place = request.args.get('place','Office1')
        u = session['username']
        allowed = get_allowed_places_for_user(u)
        
        if place == 'All':
            if session.get('role') != 'owner':
                return ('Forbidden',403)
            return get_all_latest_data()
        else:
            if place not in allowed:
                return ('Forbidden',403)
            return get_single_latest_data(place)

    @app.route('/download-csv')
    @login_required
    def download_csv():
        place = request.args.get('place','Office1')
        u = session['username']
        allowed = get_allowed_places_for_user(u)
        
        if place == 'All':
            if session.get('role') != 'owner':
                return ('Forbidden',403)
            return download_all_csv()
        else:
            if place not in allowed:
                return ('Forbidden',403)
            return download_single_csv(place)

    @app.route('/submit-data', methods=['POST'])
    def submit_data():
        d = request.get_json() or {}
        place = d.get('place'); t = d.get('temperature'); h = d.get('humidity')
        
        if not place:
            return jsonify({'status':'error','reason':'place required'}),400
        
        # Extract client name from place if format is "clientname_place"
        client_place = place
        if '_' in place:
            # Format is already "clientname_place"
            pass
        else:
            # For backward compatibility, try to find a client for this place
            # This handles old simulation files that only send place name
            conn = get_db_connection()
            row = conn.execute("SELECT username FROM users WHERE role='client' AND places=?", (place,)).fetchone()
            conn.close()
            if row:
                client_place = f"{row['username']}_{place}"  # Updated format
            else:
                client_place = f"unknown_{place}"  # Updated format
        
        warning_msg = check_sensor_ranges(t, h)
        save_sensor_data(place, client_place, t, h, warning_msg)
        
        if warning_msg:
            send_alert_email(client_place, t, h, warning_msg)
        
        return jsonify({'status':'success','warning':warning_msg}),200

    @app.route('/clients', methods=['GET','POST'])
    @login_required
    def clients_page():
        if session.get('role') != 'owner':
            return redirect(url_for('index'))

        action = request.form.get('action', 'add')
        message = None
        
        if request.method == 'POST':
            if action == 'add':
                success = handle_add_client()
                message = "Client added successfully!" if success else "Error: Username already exists!"
            elif action == 'update':
                success = handle_update_client()
                message = "Client updated successfully!" if success else "Error updating client!"
            elif action == 'delete':
                success = handle_delete_client()
                message = "Client deleted successfully!" if success else "Error deleting client!"
            elif action == 'update_password':
                success = handle_update_password()
                message = "Password updated successfully!" if success else "Error updating password!"
        
        clients = get_all_clients()
        return render_clients_management_page(clients, message)

    @app.route('/edit-client/<username>')
    @login_required
    def edit_client_page(username):
        if session.get('role') != 'owner':
            return redirect(url_for('index'))
        
        client = get_client_by_username(username)
        if not client:
            return redirect(url_for('clients_page'))
        
        return render_edit_client_page(client)

    @app.route('/download-clients-csv')
    @login_required
    def download_clients_csv():
        if session.get('role') != 'owner':
            return redirect(url_for('index'))

        conn = get_db_connection()
        df = pd.read_sql_query("""
            SELECT username, places, email, phone, address,
                   CASE WHEN email_enabled=1 THEN 'Enabled' ELSE 'Disabled' END AS email_status
            FROM users WHERE role='client'
            ORDER BY username
        """, conn)
        conn.close()

        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)

        fname = f"clients_{datetime.now(UK_TZ).strftime('%Y%m%d_%H%M%S')}_UK.csv"
        return send_file(io.BytesIO(output.getvalue().encode()),
                         mimetype='text/csv',
                         as_attachment=True,
                         download_name=fname)