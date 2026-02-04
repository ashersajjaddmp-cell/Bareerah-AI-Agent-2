
import requests
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GOOGLE_MAPS_API_KEY")

def test_google_api():
    origin = "Dubai Marina"
    destination = "Dubai Mall"
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origin}&destinations={destination}&key={key}"
    
    try:
        resp = requests.get(url)
        data = resp.json()
        print(f"Status Code: {resp.status_code}")
        print(f"Global Status: {data.get('status')}")
        
        if data.get('rows'):
            element = data['rows'][0]['elements'][0]
            print(f"Element Status: {element.get('status')}")
            if element.get('status') == 'OK':
                print(f"Distance: {element.get('distance', {}).get('text')}")
                print(f"Value: {element.get('distance', {}).get('value')} meters")
        else:
            print("No rows found in response.")
            
        if data.get('error_message'):
            print(f"Error Message: {data.get('error_message')}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_google_api()
