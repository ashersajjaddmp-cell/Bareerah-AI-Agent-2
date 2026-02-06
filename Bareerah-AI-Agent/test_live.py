
import requests
import time

def check_live_deployment():
    base_url = "https://bareerah-ai-agent-2-production-dadf.up.railway.app"
    
    print(f"Checking Live Deployment at: {base_url}")
    
    # 1. Check Root (GET /)
    try:
        r = requests.get(base_url, timeout=10)
        print(f"Root Status: {r.status_code}")
        print(f"Response: {r.text}")
    except Exception as e:
        print(f"Root Check Failed: {e}")
        return

    # 2. Check Voice Entry (POST /incoming) - Simulate Twilio
    print("\nSimulating Incoming Call...")
    try:
        r = requests.post(f"{base_url}/incoming", data={"CallSid": "TEST_LIVE_001"}, timeout=10)
        print(f"Call Status: {r.status_code}")
        if "As-Salamu Alaykum" in r.text and "do dabaaein" in r.text or "dabaaein" not in r.text: # Logic change check
             pass
        
        # Verify specific V5.2 Logic
        # V5.2 change: "For English, press 1. For Urdu, press 2." (English text, no "dabaaein")
        
        if "For Urdu, press 2" in r.text:
             print("V5.2 Greeting Confirmed: 'For Urdu, press 2'")
        else:
             print(f"Warning: Greeting format might be old or different.\nReceived: {r.text[:100]}")
             
    except Exception as e:
        print(f"Call Simulation Failed: {e}")

if __name__ == "__main__":
    check_live_deployment()
