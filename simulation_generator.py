# simulation_generator.py
import os

def create_simulation_file(client_name, place_name):
    filename = f"simulated_arduino_{client_name}_{place_name}.py"
    if os.path.exists(filename):
        print(f"⚠️  Simulation file '{filename}' already exists. Skipping creation.")
        return
    
    template = create_simulation_template(client_name, place_name)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(template)
    print(f"✅ Simulation file created: {filename}")

def create_simulation_template(client_name, place_name):
    # Combine client name and place name for unique identifier (client_place format)
    combined_place = f"{client_name}_{place_name}"  # Updated format
    
    return f"""import requests
import random
import time

# Configuration
SERVER_URL = 'http://127.0.0.1:5001/submit-data'
PLACE = '{combined_place}'  # Combined client and place name (client_place format)

# comfort thresholds
TEMP_RANGE = (18, 30)
HUM_RANGE = (30, 70)

def read_sensor():
    \"\"\"Simulate sensor readings (some normal, some abnormal).\"\"\"
    if random.random() < 0.9:
        temp = round(random.uniform(*TEMP_RANGE), 1)
        hum = round(random.uniform(*HUM_RANGE), 1)
    else:
        if random.choice(['temp', 'hum']) == 'temp':
            temp = round(random.uniform(5, 15), 1) if random.random() < 0.5 else round(random.uniform(31, 45), 1)
            hum = round(random.uniform(*HUM_RANGE), 1)
        else:
            hum = round(random.uniform(10, 25), 1) if random.random() < 0.5 else round(random.uniform(75, 95), 1)
            temp = round(random.uniform(*TEMP_RANGE), 1)
    return temp, hum

def send_data(temp, hum):
    data = {{
        'place': PLACE,
        'temperature': temp,
        'humidity': hum
    }}
    response = requests.post(SERVER_URL, json=data)
    print(f"Sent data: {{data}} | Server Response: {{response.text}}")

if __name__ == '__main__':
    while True:
        temp, hum = read_sensor()
        send_data(temp, hum)
        time.sleep(10)
"""