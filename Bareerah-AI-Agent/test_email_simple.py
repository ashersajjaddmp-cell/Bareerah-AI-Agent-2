
import requests
import json

RESEND_API_KEY = "re_P3Xh65KG_M1Vo61dQQbHbWAbpMC4ff5yZ"
TO_EMAIL = "jawaddigitalminds@gmail.com"

def send_test_email():
    print(f"Sending Test Email to {TO_EMAIL}...")
    
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    senders = ["Star Skyline <info@sslbookings.com>"]

    for sender in senders:
        payload = {
            "from": sender,
            "to": [TO_EMAIL],
            "subject": "Bareerah AI - Email Configuration Test",
            "html": f"""
            <div style="font-family: sans-serif; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <h2 style="color: #667eea;">Confirming Email Delivery</h2>
                <p>Hello Admin,</p>
                <p>This is a test email from your AI Agent.</p>
                <p><strong>Sent From:</strong> {sender}</p>
                <p><strong>Sent To:</strong> {TO_EMAIL}</p>
                <p style="color: green;">System Ready.</p>
            </div>
            """
        }
        
        try:
            print(f"Attempting to send from: {sender}")
            resp = requests.post("https://api.resend.com/emails", json=payload, headers=headers)
            
            if resp.status_code == 200:
                print(f"SUCCESS! Email sent via {sender}")
                print(f"Server Response: {resp.json()}")
                return
            else:
                print(f"Failed via {sender} (Status: {resp.status_code})")
                print(f"Error Details: {resp.text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    send_test_email()
