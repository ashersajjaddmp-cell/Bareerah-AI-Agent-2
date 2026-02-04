
import requests
import json
import os

# 1. Test Backend Vehicle Fetch
def test_backend_cars():
    url = "https://star-skyline-production.up.railway.app/api/vehicles/suggest"
    print(f"\n[TEST 1] Fetching Cars from: {url}")
    try:
        resp = requests.get(url, params={"passengers": 1, "luggage": 0}, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("✅ SUCCEES! Data:")
            print(json.dumps(resp.json(), indent=2))
        else:
            print(f"❌ FAILED. Response: {resp.text}")
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

# 2. Test DB Saving (Using your existing connection logic)
def test_db_read():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from dotenv import load_dotenv
    load_dotenv()
    
    DB_URL = os.getenv("DATABASE_URL")
    print(f"\n[TEST 2] Checking Database: {DB_URL[:20]}...")
    
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        # Check last 3 bookings
        cur.execute("SELECT id, customer_name, pickup_location, fare_aed, created_at FROM bookings ORDER BY created_at DESC LIMIT 3")
        rows = cur.fetchall()
        
        print(f"✅ DB CONNECTED. Found {len(rows)} recent bookings:")
        for r in rows:
            print(f" - #{r['id']} | {r['customer_name']} | Fare: {r['fare_aed']} | {r['created_at']}")
            
        conn.close()
    except Exception as e:
        print(f"❌ DB ERROR: {e}")

if __name__ == "__main__":
    test_backend_cars()
    print("-" * 30)
    test_db_read()
