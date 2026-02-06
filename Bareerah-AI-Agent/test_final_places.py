
import os
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def resolve_address(addr):
    clean_addr = addr.lower().strip()
    search_query = addr
    if not any(x in clean_addr for x in ["dubai", "uae", "emirates"]):
        search_query = f"{addr}, Dubai, UAE"
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": search_query,
        "inputtype": "textquery",
        "fields": "formatted_address,name",
        "locationbias": "circle:50000@25.2048,55.2708",
        "key": KEY
    }
    res = requests.get(url, params=params).json()
    if res.get("status") == "OK" and res.get("candidates"):
        return res["candidates"][0]["formatted_address"]
    return f"{addr}, Dubai, UAE"

def calc_dist(p, d):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": p, "destinations": d, "mode": "driving", "key": KEY}
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
