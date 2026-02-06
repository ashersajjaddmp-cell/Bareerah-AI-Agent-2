
import os
import requests
from dotenv import load_dotenv

# Load keys
load_dotenv()
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def resolve_address(addr):
    """Google Geocoding API with Strict UAE & Dubai Bias (Copied from main.py for local testing)"""
    if not GOOGLE_MAPS_API_KEY: return addr
    if len(addr) < 3: return addr
    
    # Pre-process: If user didn't say Abu Dhabi/Sharjah, assume Dubai for city spots
    search_query = addr
    if not any(x in addr.lower() for x in ["dubai", "abu dhabi", "sharjah", "ajman", "rak", "fujairah"]):
        search_query = f"{addr}, Dubai"

    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": search_query, 
            "components": "country:AE", 
            "key": GOOGLE_MAPS_API_KEY
        }
        res = requests.get(url, params=params, timeout=5).json()
        
        if res.get("status") == "OK" and res.get("results"):
            addr_found = res["results"][0]["formatted_address"]
            if addr_found.strip() in ["United Arab Emirates", "UAE"]:
                 pass 
            else:
                 return addr_found
    except: pass
    return f"{addr}, Dubai, UAE"

def calc_dist(p, d):
    """Google Distance Matrix (Copied from main.py)"""
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {"origins": p, "destinations": d, "mode": "driving", "key": GOOGLE_MAPS_API_KEY}
        res = requests.get(url, params=params, timeout=5).json()
        if res.get("rows") and res["rows"][0]["elements"][0]["status"] == "OK":
            dist = res["rows"][0]["elements"][0]["distance"]["value"] / 1000.0
            return dist
    except: pass
    return 0.0

# --- BATCH TEST ---
test_cases = [
    ("Dubai Mall", "Desert Safari"),
    ("Deira Hotel", "Dubai Stadium"),
    ("JBR", "DXB Airport"),
    ("Stadium", "Dubai Mall"),
    ("Palm Jumeirah", "Mall of the Emirates"),
    ("Burj Khalifa", "Global Village"),
    ("Burj Al Arab", "Atlantis"),
    ("Dubai Frame", "Museum of the Future"),
    ("Dubai Marina", "Zabeel Park"),
    ("City Walk", "La Mer")
]

print(f"{'#':<3} {'FROM':<20} {'TO':<20} | {'RESOLVED FROM':<40} | {'DIST (KM)':<10}")
print("-" * 140)

for i, (start, end) in enumerate(test_cases, 1):
    r_start = resolve_address(start)
    r_end = resolve_address(end)
    dist = calc_dist(r_start, r_end)
    
    print(f"{i:<3} {start:<20} {end:<20} | {r_start[:40]:<40} | {dist:<10.2f}")
