# email_service.py
import smtplib
from email.mime.text import MIMEText
from config import SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD

def send_email(to_email, subject, body):
    if not to_email: return
    
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
            print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Email sending failed: {e}")

def send_alert_email(place, temperature, humidity, warning_msg):
    # Import inside function to avoid circular import
    from database import get_client_for_place
    from config import UK_TZ
    from datetime import datetime
    
    client = get_client_for_place(place)
    if client and client['email_enabled'] == 1 and client['email']:
        subject = f"⚠ Alert: {place} readings out of range"
        body = f"Office: {place}\nTemperature: {temperature}°C\nHumidity: {humidity}%\nWarning: {warning_msg}\nTime: {datetime.now(UK_TZ).strftime('%Y-%m-%d %H:%M:%S')} UK"
        send_email(client['email'], subject, body)