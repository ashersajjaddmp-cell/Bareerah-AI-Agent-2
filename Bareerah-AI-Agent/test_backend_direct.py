
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "https://star-skyline-production.up.railway.app")

def get_token():
    creds = [
        {"username": "admin", "password": "admin123"},
        {"email": "admin@starskylimo.com", "password": "password123"}
    ]
    for c in creds:
        try:
            url = f"{BACKEND_BASE_URL}/api/auth/login"
            payload = {"password": c["password"]}
            if "username" in c: payload["username"] = c["username"]
            if "email" in c: payload["email"] = c["email"]
            
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                token = resp.json().get("token")
                print(f"[AUTH] Success with: {c.get('username') or c.get('email')}")
                return token
        except Exception as e:
            print(f"[AUTH] Attempt Error: {e}")
    return None

def test():
    token = get_token()
    if not token:
        print("[AUTH] Critical: Could not get Auth Token")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test Suggest Vehicles
    print("\n--- Testing /api/bookings/suggest-vehicles ---")
    pax, lug = 4, 2
    url = f"{BACKEND_BASE_URL}/api/bookings/suggest-vehicles"
    try:
        resp = requests.get(url, params={"passengers_count": pax, "luggage_count": lug}, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")

    # 2. Test Available Vehicles
    print("\n--- Testing /api/vehicles/available ---")
    url = f"{BACKEND_BASE_URL}/api/vehicles/available"
    try:
        resp = requests.get(url, params={"passengers": pax, "luggage": lug}, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")

    # 3. Test Calculate Fare
    print("\n--- Testing /api/bookings/calculate-fare ---")
    url = f"{BACKEND_BASE_URL}/api/bookings/calculate-fare"
    payload = {
        "distance_km": 20.0,
        "vehicle_type": "classic",
        "booking_type": "point_to_point"
    }
    try:
        resp = requests.post(url, json=payload, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
