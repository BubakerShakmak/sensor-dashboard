# templates.py

# ------------------ HTML Templates ------------------
LOGIN_TEMPLATE = """<!DOCTYPE html>
<html><head><title>Login</title></head>
<body>
<h2>Login</h2>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
<form method="post" action="{{ url_for('login') }}">
<label>Username: <input type="text" name="username"></label><br><br>
<label>Password: <input type="password" name="password"></label><br><br>
<button type="submit">Login</button>
</form>
</body></html>"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>Sensor Data Dashboard</title>
<style>
body {font-family:Arial;margin:40px;}
.container {max-width:1200px;margin:auto;}
select,button,input {font-size:1em;}
.topbar {display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;}
.red {color:red;font-weight:bold;}
.toggle-btn {margin-top:15px;padding:6px 12px;font-size:1em;}
.dashboard-grid {display:grid;grid-template-columns:2fr 1fr;gap:20px;margin-top:20px;}
.data-section {background:#f9f9f9;padding:15px;border-radius:5px;}
.client-status-section {background:#f0f8ff;padding:15px;border-radius:5px;}
table {border-collapse:collapse;width:100%;margin-top:10px;text-align:center;}
th,td {border:1px solid #ccc;padding:8px;}
.client-table {width:100%;margin-top:10px;}
.client-table th {background:#e9ecef;}
.status-enabled {color:green;font-weight:bold;}
.status-disabled {color:red;font-weight:bold;}
.form-row {margin:10px 0;}
.place-name { font-weight: bold; }
.client-name { color: #666; font-size: 0.9em; }
.filter-section {background:#fff3cd;padding:15px;border-radius:5px;margin-bottom:20px;}
.filter-row {display:flex;gap:10px;align-items:center;flex-wrap:wrap;}
.filter-input {padding:5px;flex:1;min-width:200px;}
.hidden {display:none;}
.highlight {background-color:#fffacd;}
</style>
<script>
const TEMP_MIN={{temp_min}},TEMP_MAX={{temp_max}},HUM_MIN={{hum_min}},HUM_MAX={{hum_max}};
let allSensorData = [];

function formatPlaceName(combinedPlace) {
    if (combinedPlace.includes('_')) {
        const parts = combinedPlace.split('_');
        const clientName = parts[0];
        const placeName = parts.slice(1).join('_');
        return '<span class="place-name">' + placeName + '</span><br><span class="client-name">' + clientName + '</span>';
    }
    return combinedPlace;
}

function filterData() {
    const filterText = document.getElementById('clientFilter').value.toLowerCase();
    const table = document.getElementById('latest').querySelector('table');
    
    if (!table) return;
    
    const rows = table.getElementsByTagName('tr');
    
    for (let i = 1; i < rows.length; i++) { // Skip header row
        const row = rows[i];
        const placeCell = row.cells[2]; // Place column
        const placeText = placeCell.textContent.toLowerCase();
        
        if (filterText === '') {
            row.classList.remove('hidden');
            row.classList.remove('highlight');
        } else if (placeText.includes(filterText)) {
            row.classList.remove('hidden');
            row.classList.add('highlight');
        } else {
            row.classList.add('hidden');
            row.classList.remove('highlight');
        }
    }
}

function clearFilter() {
    document.getElementById('clientFilter').value = '';
    filterData();
}

function refreshData(){
  let place=document.getElementById("place").value;
  fetch("/latest-data?place="+encodeURIComponent(place))
  .then(r=>r.status===403?null:r.json())
  .then(data=>{
    let div=document.getElementById("latest");
    if(!data){div.innerHTML="<b>No data yet.</b>";return;}
    let html="<table><tr><th>ID</th><th>Timestamp (UK)</th><th>Place</th><th>Temperature(°C)</th><th>Humidity(%)</th><th>Warning</th></tr>";
    if(Array.isArray(data)){
      allSensorData = data;
      data.forEach(row=>{
        let tC=(row.temperature<TEMP_MIN||row.temperature>TEMP_MAX)?"red":"";
        let hC=(row.humidity<HUM_MIN||row.humidity>HUM_MAX)?"red":"";
        html+="<tr><td>"+row.id+"</td><td>"+row.timestamp+"</td><td>"+formatPlaceName(row.place)+"</td><td class='"+tC+"'>"+row.temperature+
              "</td><td class='"+hC+"'>"+row.humidity+"</td><td>"+(row.warning||"")+"</td></tr>";
      });
    } else if(data){
      allSensorData = [data];
      let tC=(data.temperature<TEMP_MIN||data.temperature>TEMP_MAX)?"red":"";
      let hC=(data.humidity<HUM_MIN||data.humidity>HUM_MAX)?"red":"";
      html+="<tr><td>"+data.id+"</td><td>"+data.timestamp+"</td><td>"+formatPlaceName(data.place)+"</td><td class='"+tC+"'>"+data.temperature+
            "</td><td class='"+hC+"'>"+data.humidity+"</td><td>"+(data.warning||"")+"</td></tr>";
    }
    html+="</table>";
    div.innerHTML=html;
    
    // Apply any existing filter after refresh
    if (document.getElementById('clientFilter').value) {
        filterData();
    }
  });
}

function toggleEmail(){
  fetch('/toggle-email',{method:'POST'})
  .then(r=>r.json())
  .then(d=>{alert('Email alerts are now '+(d.enabled?'ENABLED':'DISABLED'));location.reload();});
}

setInterval(refreshData,3000);
window.onload=refreshData;
</script>
</head>
<body>
<div class="container">
<div class="topbar"><h2>Sensor Data Dashboard</h2>
<div>
{% if role == 'owner' %}
<a href="{{ url_for('clients_page') }}">Manage Clients</a> |
<a href="{{ url_for('download_clients_csv') }}">Download Clients CSV</a> |
{% endif %}
Logged in as: <b>{{username}}</b> ({{role}}) |
<a href="{{ url_for('logout') }}">Logout</a></div></div>

{% if role == 'client' %}
<button class="toggle-btn" onclick="toggleEmail()">
{{ 'Disable Email Alerts' if email_enabled else 'Enable Email Alerts' }}
</button>
{% endif %}

<div class="form-row">
<label for="place">Select Place:</label>
<select id="place" name="place" onchange="refreshData()">
{% for p in places %}
<option value="{{p}}" {% if loop.first %}selected{% endif %}>{{ p.replace('_', ' - ') }}</option>
{% endfor %}
</select>
<button type="button" onclick="refreshData()">Refresh</button>
<button type="button" onclick="window.location='/download-csv?place='+document.getElementById('place').value">Download CSV</button>
</div>

{% if role == 'owner' and places[0] == 'All' %}
<div class="filter-section">
<h3>Filter Client Data</h3>
<div class="filter-row">
<input type="text" id="clientFilter" class="filter-input" placeholder="Filter by client name (e.g., Client1, Client1-1, Client1-2)" onkeyup="filterData()">
<button type="button" onclick="clearFilter()">Clear Filter</button>
</div>
<p style="margin:5px 0;font-size:0.9em;color:#666;">
💡 Filter by any part of client name: Client1, Client1-1, Client1-2, etc.
</p>
</div>
{% endif %}

<div class="dashboard-grid">
<div class="data-section">
<h3>Sensor Data</h3>
<div id="latest"></div>
</div>

{% if role == 'owner' %}
<div class="client-status-section">
<h3>Client Email Alert Status</h3>
<table class="client-table">
<tr><th>Client Name</th><th>Email Status</th></tr>
{% for c in client_status %}
<tr>
<td>{{c.username}}</td>
<td class="{% if c.email_enabled %}status-enabled{% else %}status-disabled{% endif %}">
{{ 'ENABLED' if c.email_enabled else 'DISABLED' }}
</td>
</tr>
{% endfor %}
</table>
</div>
{% endif %}
</div>
</div>
</body></html>"""