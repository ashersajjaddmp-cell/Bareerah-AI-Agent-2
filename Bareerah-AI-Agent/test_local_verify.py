
import os
import requests
from dotenv import load_dotenv

load_dotenv()
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

LOCATION_MAPPING = {
    "dubai mall": "Dubai Mall, Downtown Dubai, UAE",
    "burj khalifa": "Burj Khalifa, Downtown Dubai, UAE",
    "dxb": "Dubai International Airport (DXB), Dubai, UAE",
    "deira": "Deira Clock Tower, Dubai, UAE",
    "deira hotel": "Deira Clock Tower, Dubai, UAE",
    "stadium": "Dubai International Cricket Stadium, Dubai Sports City, UAE",
    "dubai stadium": "Dubai International Cricket Stadium, Dubai Sports City, UAE",
    "desert safari": "Al Awir Desert Safari Camp, Dubai, UAE"
}

def resolve_address(addr):
    norm = addr.lower().strip()
    for k, v in LOCATION_MAPPING.items():
        if k in norm: return v
    return f"{addr}, Dubai, UAE"

def calc_dist(p, d):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": p, "destinations": d, "mode": "driving", "key": GOOGLE_MAPS_API_KEY}
    res = requests.get(url, params=params).json()
    if res.get("rows") and res["rows"][0]["elements"][0]["status"] == "OK":
        return res["rows"][0]["elements"][0]["distance"]["value"] / 1000.0
    return 0.0

# --- VERIFICATION TEST ---
start = "Deira Hotel"
end = "Dubai Stadium"

r_start = resolve_address(start)
r_end = resolve_address(end)
dist = calc_dist(r_start, r_end)

print(f"\n🚀 BATCH TEST VERIFICATION")
print(f"{'='*50}")
print(f"INPUT START: {start}")
print(f"INPUT END  : {end}")
print(f"{'-'*50}")
print(f"MAPPED START: {r_start}")
print(f"MAPPED END  : {r_end}")
print(f"{'='*50}")
print(f"FINAL CALCULATED DISTANCE: {dist} KM")
print(f"GOOGLE SEARCH EXPECTATION: ~30-35 KM")
print(f"{'='*50}")

if 28 <= dist <= 38:
    print("✅ SUCCESS: Distance matches real-world Dubai geography.")
else:
    print("❌ ERROR: Distance is still inaccurate.")
