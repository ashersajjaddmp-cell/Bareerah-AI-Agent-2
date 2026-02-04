
import requests
import os
from dotenv import load_dotenv

load_dotenv()
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "https://star-skyline-production.up.railway.app")

def get_token():
    try:
        url = f"{BACKEND_BASE_URL}/api/auth/login"
        resp = requests.post(url, json={"username": "admin", "password": "admin123"}, timeout=5)
        return resp.json().get("token")
    except: return None

def test_types():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BACKEND_BASE_URL}/api/bookings/suggest-vehicles"
    
    print("\n--- Testing with INTS (4, 2) ---")
    r1 = requests.get(url, params={"passengers_count": 4, "luggage_count": 2}, headers=headers)
    print(f"Status: {r1.status_code}")
    print(f"Num Vehicles: {len(r1.json().get('data', {}).get('suggested_vehicles', []))}")
    
    print("\n--- Testing with STRINGS ('4', '2') ---")
    r2 = requests.get(url, params={"passengers_count": "4", "luggage_count": "2"}, headers=headers)
    print(f"Status: {r2.status_code}")
    print(f"Num Vehicles: {len(r2.json().get('data', {}).get('suggested_vehicles', []))}")

if __name__ == "__main__":
    test_types()
