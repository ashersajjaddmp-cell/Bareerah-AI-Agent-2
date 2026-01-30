
import requests
import sys

# Force UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

# URL of your deployed AI Agent
RAILWAY_URL = "https://bareerah-ai-agent-2-production.up.railway.app/voice"

print(f"[TEST] HARD TEST: Ping {RAILWAY_URL} mimicking Twilio...")

# Fake data that Twilio sends when a call starts
twilio_payload = {
    "CallSid": "CA1234567890abcdef1234567890abcdef",
    "Caller": "+15551234567",
    "From": "+15551234567",
    "To": "+13204222373",
    "Direction": "inbound",
    "ApiVersion": "2010-04-01",
    "AccountSid": "ACxxxx"
}

try:
    # Send POST request (just like Twilio does)
    response = requests.post(RAILWAY_URL, data=twilio_payload)
    
    print(f"\n[STATUS CODE]: {response.status_code}")
    
    if response.status_code == 200:
        print("[SUCCESS] Server accepted the call.")
        print("\n[SERVER RESPONSE (TwiML)]:")
        print(response.text)
        
        if "<Say>" in response.text or "<Gather>" in response.text:
            print("\n[VALID] XML is correct. The server is giving correct voice instructions.")
        else:
            print("\n[WARNING] Response is 200 OK but doesn't look like Voice XML.")
            
    else:
        print("[FAILED] Server returned error.")
        print(f"Error Message: {response.text}")

except Exception as e:
    print(f"[CRITICAL] CONNECTION ERROR: {e}")
