
import os
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("GOOGLE_MAPS_API_KEY")

s = "Deira - Dubai - United Arab Emirates"
e = "Prime Business Centre - Sheikh Mohammed Bin Zayed Rd - Jumeirah Village - Dubai Sports City - Dubai - United Arab Emirates"

url = "https://maps.googleapis.com/maps/api/distancematrix/json"
params = {"origins": s, "destinations": e, "mode": "driving", "key": KEY}
res = requests.get(url, params=params).json()

print(res)
