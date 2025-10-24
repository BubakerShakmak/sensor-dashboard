# config.py
import os
from zoneinfo import ZoneInfo

# Configuration with environment variables for security
TEMP_RANGE = (18, 25)
HUM_RANGE = (40, 60)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = os.environ.get('EMAIL_SENDER', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
UK_TZ = ZoneInfo("Europe/London")
DB_PATH = "sensor_data.db"
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')