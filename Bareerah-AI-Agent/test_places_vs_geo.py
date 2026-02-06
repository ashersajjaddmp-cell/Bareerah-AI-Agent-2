
import os
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def test_places(q):
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": q,
        "inputtype": "textquery",
        "fields": "formatted_address,name",
        "locationbias": "circle:50000@25.2048,55.2708", # Bias to Dubai center
        "key": KEY
    }
    res = requests.get(url, params=params).json()
    return res

print("Searching 'Dubai Stadium' via PLACES API...")
print(test_places("Dubai Stadium"))
