# Bareerah Fluid AI V5.1 (Fixed Integration) 🚀
import os
import json
import logging
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse
from openai import OpenAI
from dotenv import load_dotenv

# ✅ 1. SETUP
load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# API Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "https://star-skyline-production.up.railway.app")
NOTIFICATION_EMAIL = "aizaz.dmp@gmail.com" 

# ✅ JWT FOR BACKEND AUTH
CACHED_TOKEN = None

def get_token():
    global CACHED_TOKEN
    if CACHED_TOKEN: return CACHED_TOKEN
    
    # Try multiple credential sets to be safe
    creds = [
        {"username": "admin", "password": "admin123"},
        {"email": "admin@starskylimo.com", "password": "password123"}
    ]
    
    for c in creds:
        try:
            url = f"{BACKEND_BASE_URL}/api/auth/login"
            # Some backends expect 'username', some 'email'
            payload = {"password": c["password"]}
            if "username" in c: payload["username"] = c["username"]
            if "email" in c: payload["email"] = c["email"]
            
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                CACHED_TOKEN = resp.json().get("token")
                print(f"✅ Auth Success with: {c.get('username') or c.get('email')}")
                return CACHED_TOKEN
        except: pass
    
    print("❌ All Auth attempts failed")
    return None

client = OpenAI(api_key=OPENAI_API_KEY)

# ✅ 2. DB HELPERS (Fault Tolerant)
def get_db():
    if not DATABASE_URL: return None
    try:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    except Exception as e:
        logging.error(f"DB Connect Error: {e}")
        return None

def init_tables():
    conn = get_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS call_state (
                    call_sid VARCHAR(255) PRIMARY KEY,
                    data JSONB,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id SERIAL PRIMARY KEY,
                    customer_name TEXT,
                    phone TEXT,
                    pickup TEXT,
                    dropoff TEXT,
                    fare TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            print("✅ Tables Init Success")
        except Exception as e:
            print(f"❌ Table Init Error: {e}")
        finally:
            conn.close()

# ✅ 3. CORE LOGIC (Requests Only - No Google Lib)
def resolve_address(addr):
    """Google Places Text Search via Requests"""
    if not GOOGLE_MAPS_API_KEY: return addr
    try:
        url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {"input": addr, "inputtype": "textquery", "fields": "formatted_address", "key": GOOGLE_MAPS_API_KEY}
        res = requests.get(url, params=params, timeout=5).json()
        if res.get("candidates"):
            return res["candidates"][0]["formatted_address"]
    except: pass
    return addr

def calc_dist(p, d):
    """Google Distance Matrix via Requests"""
    if not GOOGLE_MAPS_API_KEY: 
        print("⚠️ No Google Maps Key. Defaulting to 20km.")
        return 20.0
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {"origins": p, "destinations": d, "mode": "driving", "key": GOOGLE_MAPS_API_KEY}
        res = requests.get(url, params=params, timeout=5).json()
        print(f"🗺️ Maps Status: {res.get('status')} | Elements: {res.get('rows', [{}])[0].get('elements', [{}])[0].get('status') if res.get('rows') else 'N/A'}")
        if res.get("rows") and res["rows"][0]["elements"][0]["status"] == "OK":
            dist = res["rows"][0]["elements"][0]["distance"]["value"] / 1000.0
            print(f"🗺️ Distance Calculated: {dist} km")
            return dist
    except Exception as e: 
        print(f"❌ Maps Error: {e}")
    return 20.0

def send_email(subject, body):
    """Resend API via Requests - Consolidated & Robust"""
    if not RESEND_API_KEY: 
        print("❌ No RESEND_API_KEY found.")
        return
    
    # Try sending with professional domain first, fallback to onboarding if it fails
    senders = ["Star Skyline <onboarding@resend.dev>", "Star Skyline <bookings@starskyline.ae>"]
    
    for sender in senders:
        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": sender, "to": [NOTIFICATION_EMAIL], "subject": subject, "html": body},
                timeout=10
            )
            if resp.status_code == 200:
                print(f"📧 Email Sent Successfully via {sender}")
                return
            else:
                print(f"⚠️ Email Attempt failed via {sender}: {resp.status_code}")
                if "verify a domain" not in resp.text: # If it's not a domain error, don't just loop
                     print(f"❌ Details: {resp.text}")
        except Exception as e:
            print(f"❌ Email Exception: {e}")

def calculate_backend_fare(dist_km, v_type, b_type="point_to_point"):
    """Call backend /api/bookings/calculate-fare for the perfect quote"""
    url = f"{BACKEND_BASE_URL}/api/bookings/calculate-fare"
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        data = {
            "distance_km": dist_km,
            "vehicle_type": v_type.upper(),
            "booking_type": b_type
        }
        print(f"💰 Fetching Fare: {url} -> {data}")
        resp = requests.post(url, json=data, headers=headers, timeout=5)
        if resp.status_code in [200, 201]:
            fare = resp.json().get("fare_aed")
            if fare is not None:
                print(f"💰 Fare Received: {fare}")
                return fare
        print(f"⚠️ Fare API returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Fare API Error: {e}")
    return None

def fetch_backend_vehicles(pax, luggage):
    """Fetch real vehicle suggestions from Backend API based on capacity"""
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    # 1. Try smart suggestion first
    url = f"{BACKEND_BASE_URL}/api/bookings/suggest-vehicles"
    print(f"🚗 Fetching cars from: {url} (pax={pax}, luggage={luggage})")
    try:
        params = {"passengers_count": pax, "luggage_count": luggage}
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            # ✅ FIX: Handle the 'suggested_vehicles' key from logs
            if isinstance(data, dict) and "suggested_vehicles" in data:
                return data["suggested_vehicles"]
            if isinstance(data, list):
                return data
    except: pass
    
    # 2. Fallback to general available vehicles
    url = f"{BACKEND_BASE_URL}/api/vehicles/available"
    try:
        resp = requests.get(url, params={"passengers": pax, "luggage": luggage}, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list): return data
            if isinstance(data, dict):
                return data.get("data", []) or data.get("vehicles", []) or []
    except: pass
    
    return []

def sync_booking_to_backend(booking_data):
    """Sync confirmed booking to external backend"""
    url = f"{BACKEND_BASE_URL}/api/bookings/create-manual"
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        print(f"🔄 Syncing booking to {url}...")
        resp = requests.post(url, json=booking_data, headers=headers, timeout=5)
        print(f"🔄 Sync Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"⚠️ Sync failed: {resp.text}")
    except Exception as e:
        print(f"❌ Sync Error: {e}")

# ✅ 4. AI BRAIN (The "Fluid" Part)
def run_ai(history, slots):
    system = f"""
    You are Bareerah, Star Skyline Limousine's AI agent. Professional and helpful.
    
    CRITICAL NLU EXTRACTION:
    You must extract information into the following exact slot names:
    - customer_name: The customer's full name.
    - pickup_location: The starting point of the journey.
    - dropoff_location: The destination of the journey.
    - pickup_time: The specific date and time for the pickup.
    - passengers_count: Number of people (default 1 if mentioned).
    - luggage_count: Number of bags (default 0).
    
    CRITICAL RULES:
    1. **STRICT ONE QUESTION AT A TIME**: Ask only for ONE missing piece. 
       - Sequence: 1. Name -> 2. Pickup -> 3. Dropoff -> 4. Date & Time -> 5. Passengers & Luggage.
    2. **LUGGAGE IS BAGS**: 'Luggage' and 'Bags' are the same. If you know one, you know the other. Never ask for both.
    3. **PITCH LOGIC**: ONCE you have [customer_name, pickup_location, dropoff_location, pickup_time, luggage_count], output action: "confirm_pitch". 
       - DO NOT pitch cars until you know the luggage count.
    4. **DO NOT REPEAT**: If a slot is filled in 'Current Info', never ask for it again. If names/addresses are already there, MOVE TO THE NEXT missing item.
    
    Current Info: {json.dumps(slots)}
    
    Output JSON Format:
    {{
      "response": "Your spoken response",
      "new_slots": {{ "slot_name": "extracted_value" }},
      "action": "continue" | "confirm_pitch" | "finalize"
    }}
    """
    try:
        # ✅ SPEED: Using gpt-4o-mini for 3x faster response
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}] + history[-15:],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(resp.choices[0].message.content)
    except:
        return {"response": "I'm sorry, I missed that. Could you repeat?", "new_slots": {}, "action": "continue"}

# ✅ 5. ROUTES (Matching Legacy Structure)

@app.route('/', methods=['GET'])
def index():
    return "Bareerah Fluid AI V5 (Real Backend) Running 🚀"

# ✅ ROUTE MATCHING: /voice AND /incoming -> Entry Point
@app.route('/voice', methods=['POST'])
@app.route('/incoming', methods=['POST'])
def incoming_call():
    call_sid = request.values.get('CallSid')
    
    # Init State
    state = {"history": [], "slots": {}}
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO call_state (call_sid, data) VALUES (%s, %s) ON CONFLICT (call_sid) DO NOTHING", (call_sid, json.dumps(state)))
        conn.commit()
    
    resp = VoiceResponse()
    gather = resp.gather(input='speech', action='/handle', timeout=2)
    gather.say("Welcome to Star Skyline. I am Bareerah. May I have your name?", voice='Polly.Joanna-Neural')
    return str(resp)

# ✅ ROUTE MATCHING: /handle -> Main Logic
@app.route('/handle', methods=['POST'])
def handle_call():
    call_sid = request.values.get('CallSid')
    speech = request.values.get('SpeechResult', '')
    
    # Load State
    conn = get_db()
    state = {"history": [], "slots": {}}
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM call_state WHERE call_sid = %s", (call_sid,))
            row = cur.fetchone()
            if row: state = row['data']
    
    state['history'].append({"role": "user", "content": speech})
    
    # Process
    decision = run_ai(state['history'], state['slots'])
    state['slots'].update(decision.get('new_slots', {}))
    ai_msg = decision.get('response', 'Understood.')
    action = decision.get('action', 'continue')
    
    # Logic: Present Options or Finalize
    if action == "confirm_pitch":
        p = resolve_address(state['slots'].get('pickup_location', 'Dubai'))
        d = resolve_address(state['slots'].get('dropoff_location', 'Dubai'))
        base_dist = calc_dist(p, d)
        
        # Fetch Real Options (Matches Capacity)
        pax = state['slots'].get('passengers_count', 1)
        lug = state['slots'].get('luggage_count', 0)
        options = fetch_backend_vehicles(pax, lug)
        
        # Construction of the Pitch
        logging.info(f"🚗 Options found: {type(options)} - {options}")
        
        # Guard against KeyError: slice(None, 2, None) by strictly checking list type
        if isinstance(options, list) and len(options) > 0:
            pitch = "I have checked the availability for you. "
            b_type = "airport_transfer" if "airport" in (p+d).lower() else "point_to_point"
            
            # Use list slicing safely
            for v in options[:2]:
                if not isinstance(v, dict): continue
                # The 'suggest-vehicles' API uses 'vehicle_type', regular API uses 'type'
                v_type = v.get('vehicle_type', v.get('type', v.get('category', 'SEDAN'))).upper()
                v_model = v.get('vehicle_type', v.get('model', v.get('vehicle', 'Car'))).replace("_", " ").title()
                
                # Get Perfect Fare from Backend
                price = calculate_backend_fare(base_dist, v_type, b_type)
                if not price:
                    # Fallback to backend-provided base/rate if available
                    if v.get('base_fare'):
                         price = int(float(v['base_fare']) + (base_dist * float(v.get('per_km_rate', 1))))
                    else:
                         price = int(v.get('base_price', 50) + (base_dist * v.get('rate_per_km', 3.5)))
                
                pitch += f"A {v_model} for this {base_dist} kilometer journey is {price} Dirhams. "
            pitch += "Which one would you like to book?"
        else:
            # Fallback Pitch (Using Backend Fare API even for hardcoded types)
            logging.info("🚕 No suitable cars found in API, using fallback logic.")
            sedan_fare = calculate_backend_fare(base_dist, "SEDAN") or int(50 + (base_dist * 3.5))
            suv_fare = calculate_backend_fare(base_dist, "SUV") or int(80 + (base_dist * 5.0))
            pitch = f"I have a Lexus ES for {sedan_fare} Dirhams or a GMC Yukon for {suv_fare} Dirhams. Which do you prefer?"
        
        # Override AI response
        ai_msg = pitch
        state['history'].append({"role": "assistant", "content": pitch})

    elif action == "finalize":
        p = resolve_address(state['slots'].get('pickup_location', 'Dubai'))
        d = resolve_address(state['slots'].get('dropoff_location', 'Dubai'))
        base_dist = calc_dist(p, d)
        
        pax = state['slots'].get('passengers_count', 1)
        lug = state['slots'].get('luggage_count', 0)
        b_type = "airport_transfer" if "airport" in (p+d).lower() else "point_to_point"

        # Determine Car & Final Price
        pref = state['slots'].get('preferred_vehicle', 'Lexus').lower()
        if 'suv' in pref or 'gmc' in pref:
             car_model = "GMC Yukon"
             v_type = "SUV"
        elif 'van' in pref:
             car_model = "Mercedes V-Class"
             v_type = "VAN"
        else:
             car_model = "Lexus ES"
             v_type = "SEDAN"
             
        # Get Final Perfect Fare from Backend
        fare = calculate_backend_fare(base_dist, v_type, b_type) or (
            int(80 + (base_dist * 5.0)) if v_type == "SUV" else int(50 + (base_dist * 3.5))
        )

        # Save Booking (Verified Columns)
        if conn:
            try:
                with conn.cursor() as cur:
                    try:
                         # Use columns confirmed by validation script:
                         # customer_name, customer_phone, pickup_location, dropoff_location, fare_aed
                         cur.execute("""
                            INSERT INTO bookings 
                            (customer_name, customer_phone, pickup_location, dropoff_location, fare_aed, status) 
                            VALUES (%s, %s, %s, %s, %s, 'CONFIRMED')
                         """, (
                            state['slots'].get('customer_name'), 
                            request.values.get('From'), 
                            p, d, str(fare)
                         ))
                    except Exception as e:
                        cur.connection.rollback()
                        logging.error(f"❌ Primary Insert Failed: {e}")
                        # Minimal Fallback
                        try:
                           cur.execute("INSERT INTO bookings (customer_name, fare_aed, status) VALUES (%s, %s, 'CONFIRMED')",
                                    (state['slots'].get('customer_name'), str(fare)))
                        except:
                           cur.connection.rollback()
                conn.commit()
            except Exception as e:
                logging.error(f"DB Connection Error: {e}")

        # ✅ SYNC TO BACKEND (New Step)
        sync_booking_to_backend({
            "customer_name": state['slots'].get('customer_name'),
            "phone": request.values.get('From'),
            "pickup_location": p,
            "dropoff_location": d,
            "fare_aed": fare,
            "vehicle_model": car_model,
            "pickup_time": state['slots'].get('pickup_time')
        })

        # Send Email (Admin Style)
        email_body = f"""
        <div style="font-family: Arial; padding: 20px; border: 1px solid #ddd;">
            <h2 style="color: #2c3e50;">🔔 New Booking Alert (Admin)</h2>
            <p><strong>Customer:</strong> {state['slots'].get('customer_name')}</p>
            <p><strong>Phone:</strong> {request.values.get('From')}</p>
            <hr>
            <p><strong>Pickup:</strong> {p}</p>
            <p><strong>Dropoff:</strong> {d}</p>
            <p><strong>Vehicle:</strong> {car_model}</p>
            <p><strong>Total Fare:</strong> <span style="font-size: 1.2em; font-weight: bold; color: green;">AED {fare}</span></p>
        </div>
        """
        send_email(f"🚀 NEW BOOKING: {state['slots'].get('customer_name')}", email_body)
        
        ai_msg = f"Great. I have booked the {car_model} for {fare} Dirhams. You will receive a confirmation shortly. Goodbye!"
        resp = VoiceResponse()
        resp.say(ai_msg, voice='Polly.Joanna-Neural')
        resp.hangup()
        
        # Final Save
        state['history'].append({"role": "assistant", "content": ai_msg})
        if conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE call_state SET data = %s WHERE call_sid = %s", (json.dumps(state), call_sid))
            conn.commit()
            conn.close()
        return str(resp)
    
    # Continue Loop
    state['history'].append({"role": "assistant", "content": ai_msg})
    if conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE call_state SET data = %s WHERE call_sid = %s", (json.dumps(state), call_sid))
        conn.commit()
    
    resp = VoiceResponse()
    gather = resp.gather(input='speech', action='/handle', timeout=2)
    gather.say(ai_msg, voice='Polly.Joanna-Neural')
    resp.redirect('/handle')
    return str(resp)

# ✅ ROUTE MATCHING: /call-status -> Dummy handler to prevent 404s
@app.route('/call-status', methods=['POST'])
def call_status():
    return "OK", 200

# Init Tables
with app.app_context():
    init_tables()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000))
