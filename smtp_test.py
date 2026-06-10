import smtplib

HOST = "smtp.zoho.in"
PORT = 465

USER = "sales@siaratechnology.com"
PASSWORD = "fQCBj9YFu1ne"

try:
    print("Connecting to Zoho SMTP...")

    with smtplib.SMTP_SSL(HOST, PORT, timeout=30) as server:
        server.set_debuglevel(1)  # Remove after testing

        print("Logging in...")
        server.login(USER, PASSWORD)

        print("✅ LOGIN SUCCESS")

except smtplib.SMTPAuthenticationError as e:
    print("❌ Authentication Failed:", e)

except Exception as e:
    print("❌ ERROR:", repr(e))