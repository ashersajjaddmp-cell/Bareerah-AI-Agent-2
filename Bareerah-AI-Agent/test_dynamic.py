
import os
import requests
from dotenv import load_dotenv

load_dotenv()
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def resolve_address(addr):
    if not GOOGLE_MAPS_API_KEY: return addr
    clean_addr = addr.lower().strip()
    search_query = addr
    generic_terms = ["stadium", "safari", "mall", "deira", "marina", "jbr", "jlt", "palm", "airport"]
    if any(term in clean_addr for term in generic_terms):
        if "dubai" not in clean_addr:
             search_query = f"{addr}, Dubai, UAE"
    if "uae" not in search_query.lower() and "emirates" not in search_query.lower():
         search_query += ", United Arab Emirates"

    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": search_query, "components": "country:AE", "key": GOOGLE_MAPS_API_KEY}
        res = requests.get(url, params=params, timeout=5).json()
        if res.get("status") == "OK" and res.get("results"):
            return res["results"][0]["formatted_address"]
    except: pass
    return f"{addr}, Dubai, UAE"

def calc_dist(p, d):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": p, "destinations": d, "mode": "driving", "key": GOOGLE_MAPS_API_KEY}
    res = requests.get(url, params=params).json()
    if res.get("rows") and res["rows"][0]["elements"][0]["status"] == "OK":
        return res["rows"][0]["elements"][0]["distance"]["value"] / 1000.0
    return 0.0

# Test
s, e = "Deira Hotel", "Dubai Stadium"
rs, re = resolve_address(s), resolve_address(e)
d = calc_dist(rs, re)
print(f"From: {rs}")
print(f"To: {re}")
print(f"Distance: {d} km")
