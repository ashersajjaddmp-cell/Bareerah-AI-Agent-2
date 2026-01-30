
import requests
import json
import os
import sys

# Force UTF-8 encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')

# Configuration
BACKEND_URL = "https://star-skyline-production.up.railway.app"
API_KEY = "bareerah-voice-agent-secure-2024"

def test_backend():
    print(f"Testing connection to: {BACKEND_URL}")
    
    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    
    # 2. Test Booking Price Calculation
    payload = {
        "distance_km": 10,
        "vehicle_type": "sedan",
        "booking_type": "transfer"
    }
    
    url = f"{BACKEND_URL}/api/bookings/calculate-fare"
    print(f"\nTesting Fare Calculation: {url}")
    
    try:
        resp = requests.post(url, json=payload, headers=headers)
        
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            print("[SUCCESS] Backend is working and responding.")
            print("Response:", json.dumps(resp.json(), indent=2))
        else:
            print("[FAILED] Response:")
            print(resp.text)
            
    except Exception as e:
        print(f"[ERROR] CONNECTION ERROR: {e}")

if __name__ == "__main__":
    test_backend()
