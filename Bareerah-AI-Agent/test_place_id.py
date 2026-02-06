
import os
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def resolve_id(addr):
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": f"{addr}, Dubai, UAE",
        "inputtype": "textquery",
        "fields": "place_id,formatted_address",
        "locationbias": "circle:50000@25.2048,55.2708",
        "key": KEY
    }
    res = requests.get(url, params=params).json()
    if res.get("status") == "OK" and res.get("candidates"):
        return f"place_id:{res['candidates'][0]['place_id']}", res['candidates'][0]['formatted_address']
    return addr, addr

def calc_dist(p, d):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": p, "destinations": d, "mode": "driving", "key": KEY}
    res = requests.get(url, params=params).json()
    if res.get("status") == "OK" and res.get("rows"):
        element = res["rows"][0]["elements"][0]
        if element["status"] == "OK":
            return element["distance"]["value"] / 1000.0
    return 0.0

# Test
s, e = "Deira Hotel", "Dubai Stadium"
sid, stext = resolve_id(s)
eid, etext = resolve_id(e)
dist = calc_dist(sid, eid)

print(f"ORIGIN: {stext}")
print(f"DEST  : {etext}")
print(f"RESULT: {dist} km")
