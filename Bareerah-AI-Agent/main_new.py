import os
import json
import time
import uuid
import threading
import requests
import jwt
from datetime import datetime, timedelta, timezone
from flask import Flask, request, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client as TwilioClient
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bareerah-secret-new')

# ✅ Configuration & API Keys
OPENAI_CLIENT = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# User explicitly provided this key for locations
GOOGLE_MAPS_API_KEY = "AIzaSyBO7G5z5PCC5B8HZapjLbHniqg17u-rRHk" 
DATABASE_URL = os.environ.get("DATABASE_URL")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "https://star-skyline-production.up.railway.app")
JWT_SECRET = os.environ.get("JWT_SECRET", "your-jwt-secret")

# ✅ DB Setup
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS call_state_new (
            call_sid TEXT PRIMARY KEY,
            state JSONB,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ✅ State Persistence Helpers
def save_state(call_sid, state):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO call_state_new (call_sid, state, updated_at) VALUES (%s, %s, NOW()) ON CONFLICT (call_sid) DO UPDATE SET state = %s, updated_at = NOW()",
                (call_sid, json.dumps(state), json.dumps(state)))
    conn.commit()
    cur.close()
    conn.close()

def load_state(call_sid):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT state FROM call_state_new WHERE call_sid = %s", (call_sid,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row['state'] if row else None

# ✅ Utility Functions
def get_jwt_token():
    payload = {"role": "agent", "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def geocode_location(address):
    """Use Google Places/Geocoding API to validate address"""
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_MAPS_API_KEY}"
    try:
        resp = requests.get(url, timeout=5).json()
        if resp.get("status") == "OK":
            result = resp["results"][0]
            return {
                "formatted_address": result["formatted_address"],
                "lat": result["geometry"]["location"]["lat"],
                "lng": result["geometry"]["location"]["lng"]
            }
    except Exception as e:
        print(f"[GEO] Error: {e}")
    return None

def calculate_distance(pickup_obj, dropoff_obj):
    """Calculate distance using Google Matrix API"""
    origins = f"{pickup_obj['lat']},{pickup_obj['lng']}"
    destinations = f"{dropoff_obj['lat']},{dropoff_obj['lng']}"
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origins}&destinations={destinations}&key={GOOGLE_MAPS_API_KEY}"
    try:
        resp = requests.get(url, timeout=5).json()
        if resp.get("status") == "OK" and resp["rows"][0]["elements"][0]["status"] == "OK":
            distance_text = resp["rows"][0]["elements"][0]["distance"]["text"]
            distance_km = resp["rows"][0]["elements"][0]["distance"]["value"] / 1000.0
            return distance_km
    except Exception as e:
        print(f"[DISTANCE] Error: {e}")
    return 20.0 # Fallback

def get_vehicle_suggestions(pax, luggage, jwt_token):
    url = f"{BACKEND_BASE_URL}/api/vehicles/suggest?passengers={pax}&luggage={luggage}"
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5).json()
        if resp.get("success"):
            return resp.get("data", {}).get("suggested_vehicles", [])
    except Exception as e:
        print(f"[BACKEND] Vehicle error: {e}")
    return []

def calculate_fare(distance_km, vehicle_type, jwt_token):
    url = f"{BACKEND_BASE_URL}/api/bookings/calculate-fare"
    headers = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"}
    body = {"distance_km": distance_km, "vehicle_type": vehicle_type, "booking_type": "point_to_point"}
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=5).json()
        if resp.get("success"):
            return resp.get("fare")
    except Exception as e:
         print(f"[BACKEND] Fare error: {e}")
    return int(50 + (distance_km * 4)) # Local fallback

# ✅ NLU Core
def process_nlu(text, current_state, language="en"):
    locked = current_state.get("locked_slots", {})
    known_str = json.dumps(locked)
    
    # Strictly define the order of collection
    order = ["customer_name", "dropoff", "pickup", "datetime", "passengers", "luggage", "preferred_vehicle"]
    missing = [s for s in order if s not in locked]
    
    system_prompt = f"""You are Bareerah, a world-class limousine assistant for Star Skyline.
ALREADY COLLECTED: {known_str}
STRICTLY MISSING: {missing}

RULES:
1. CAPTURE EVERYTHING: Extract ALL info the user provides in this sentence, even if not asked.
2. EXTRACTION: Map user info ONLY to these keys: customer_name, dropoff, pickup, datetime, passengers, luggage, preferred_vehicle.
3. NEXT QUESTION: Check what is still missing. Only THEN ask for the FIRST missing item.
4. CONFIRMATION: If all info is collected, set intent to "confirm" and repeat all details back: "I have you down for [DateTime] from [Pickup] to [Dropoff]. Fare is [Fare]. Should I book it?"

Return JSON ONLY:
{{
  "extracted": {{ "slot_name": "value" }},
  "response": "Acknowledge what they said + Ask for the next missing item",
  "intent": "continue | confirm"
}}"""

    try:
        resp = OPENAI_CLIENT.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Customer said: '{text}'"}
            ],
            response_format={"type": "json_object"},
            timeout=10
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"[NLU] Error: {e}")
        return {"extracted": {}, "response": "Could you please repeat that?", "intent": "continue"}

# ✅ Twilio Routes
@app.route('/incoming', methods=['POST'])
def incoming():
    resp = VoiceResponse()
    call_sid = request.values.get('CallSid')
    
    # Initialize State
    initial_state = {
        "flow_step": "customer_name",
        "locked_slots": {},
        "language": "en"
    }
    save_state(call_sid, initial_state)
    
    gather = resp.gather(input='speech', action='/handle_new', timeout=3, enhanced=True)
    gather.say("Welcome to Star Skyline Limousine. May I have your name please?", voice="Polly.Aditi")
    
    return str(resp)

@app.route('/handle_new', methods=['POST'])
def handle_new():
    call_sid = request.values.get('CallSid')
    speech = request.values.get('SpeechResult', '')
    
    if not speech:
        resp = VoiceResponse()
        gather = resp.gather(input='speech', action='/handle_new', timeout=3)
        gather.say("I'm sorry, I didn't catch that. Could you repeat?")
        return str(resp)

    state = load_state(call_sid)
    if not state:
        return str(VoiceResponse().hangup())

    # 1. Process NLU
    nlu_result = process_nlu(speech, state)
    extracted = nlu_result.get("extracted", {})
    response_text = nlu_result.get("response")
    print(f"[BRAIN] extracted: {extracted}", flush=True)
    
    # 2. Update State with extracted info
    for slot, val in extracted.items():
        if val:
            # Domain-specific validation
            if slot in ["pickup", "dropoff"]:
                geo = geocode_location(val)
                if geo:
                    state["locked_slots"][slot] = geo["formatted_address"]
                    state["locked_slots"][f"{slot}_geo"] = geo
                else:
                    # If geocoding fails, we ask again or accept if it looks okay
                    state["locked_slots"][slot] = val
            else:
                state["locked_slots"][slot] = val

    # 3. Determine Flow Progression
    order = ["customer_name", "dropoff", "pickup", "datetime", "passengers", "luggage", "preferred_vehicle"]
    missing = [s for s in order if s not in state["locked_slots"]]
    
    resp = VoiceResponse()
    
    if not missing:
        # Check if we have vehicle suggestions
        if "fare" not in state["locked_slots"]:
            jwt_token = get_jwt_token()
            pax = state["locked_slots"].get("passengers", 1)
            lug = state["locked_slots"].get("luggage", 0)
            
            # Distance
            dist = 20.0
            if "pickup_geo" in state["locked_slots"] and "dropoff_geo" in state["locked_slots"]:
                dist = calculate_distance(state["locked_slots"]["pickup_geo"], state["locked_slots"]["dropoff_geo"])
            
            suggestions = get_vehicle_suggestions(pax, lug, jwt_token)
            if suggestions:
                best = suggestions[0]
                model = best.get("model", "Luxury Sedan")
                fare = calculate_fare(dist, best.get("type", "sedan"), jwt_token)
                
                state["locked_slots"]["vehicle_model"] = model
                state["locked_slots"]["fare"] = fare
                state["flow_step"] = "confirm"
                
                msg = f"Got it. Based on your needs, I recommend a {model}. The total fare will be AED {fare}. Shall I confirm this booking?"
                gather = resp.gather(input='speech', action='/handle_new', timeout=3)
                gather.say(msg)
                save_state(call_sid, state)
                return str(resp)

        # Handle final confirmation
        if nlu_result.get("intent") == "confirm" or "yes" in speech.lower() or "confirm" in speech.lower():
            jwt_token = get_jwt_token()
            url = f"{BACKEND_BASE_URL}/api/bookings/create-manual"
            headers = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"}
            
            # Prepare payload for backend
            booking_payload = {
                "customer_name": state["locked_slots"].get("customer_name"),
                "pickup_location": state["locked_slots"].get("pickup"),
                "dropoff_location": state["locked_slots"].get("dropoff"),
                "pickup_datetime": state["locked_slots"].get("datetime"),
                "vehicle_type": state["locked_slots"].get("vehicle_model"),
                "passengers": int(state["locked_slots"].get("passengers", 1)),
                "luggage": int(state["locked_slots"].get("luggage", 0)),
                "fare_quoted": state["locked_slots"].get("fare"),
                "pickup_lat": state["locked_slots"].get("pickup_geo", {}).get("lat"),
                "pickup_lng": state["locked_slots"].get("pickup_geo", {}).get("lng"),
                "dropoff_lat": state["locked_slots"].get("dropoff_geo", {}).get("lat"),
                "dropoff_lng": state["locked_slots"].get("dropoff_geo", {}).get("lng"),
            }
            
            try:
                final_resp = requests.post(url, headers=headers, json=booking_payload, timeout=10).json()
                if final_resp.get("success"):
                    resp.say("Perfect! Your booking is confirmed. You will receive an SMS shortly. Thank you for choosing Star Skyline.")
                else:
                    resp.say("I've processed your request, and our team will contact you shortly to finalize the details. Thank you!")
            except Exception as e:
                print(f"[BOOKING] Final error: {e}")
                resp.say("Your booking request has been sent to our dispatch team. They will call you back in a few minutes. Thank you!")
            
            resp.hangup()
            return str(resp)

    # Standard loop: ask response from NLU
    gather = resp.gather(input='speech', action='/handle_new', timeout=3)
    gather.say(response_text)
    
    save_state(call_sid, state)
    return str(resp)

if __name__ == '__main__':
    print("🚀 Force Redeploy Triggered: v2.0 Live", flush=True)
    app.run(host='0.0.0.0', port=5001, debug=True)
