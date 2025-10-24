# helpers.py
from datetime import datetime
from zoneinfo import ZoneInfo
from config import UK_TZ

def convert_to_uk(dt_str):
    if not dt_str: return dt_str
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(UK_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return dt_str

def check_sensor_ranges(temperature, humidity):
    from config import TEMP_RANGE, HUM_RANGE
    warn = []
    
    if temperature < TEMP_RANGE[0] or temperature > TEMP_RANGE[1]:
        warn.append(f"Temperature out of range ({temperature}°C)")
    
    if humidity < HUM_RANGE[0] or humidity > HUM_RANGE[1]:
        warn.append(f"Humidity out of range ({humidity}%)")
    
    return '; '.join(warn) if warn else None