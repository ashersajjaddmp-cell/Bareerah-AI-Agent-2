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
NOTIFICATION_EMAIL = "ashersajjad.dmp@gmail.com"

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
    if not GOOGLE_MAPS_API_KEY: return 20.0
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {"origins": p, "destinations": d, "mode": "driving", "key": GOOGLE_MAPS_API_KEY}
        res = requests.get(url, params=params, timeout=5).json()
        if res.get("rows") and res["rows"][0]["elements"][0]["status"] == "OK":
            return res["rows"][0]["elements"][0]["distance"]["value"] / 1000.0
    except: pass
    return 20.0

def send_email(subject, body):
    """Resend API via Requests"""
    if not RESEND_API_KEY: return
    try:
        requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={"from": "Star Skyline <bookings@starskyline.ae>", "to": [NOTIFICATION_EMAIL], "subject": subject, "html": body},
            timeout=5
        )
    except: pass

def send_email(subject, body):
    """Resend API via Requests"""
    if not RESEND_API_KEY: 
        print("❌ No RESEND_API_KEY found.")
        return
    try:
        # ✅ FIX: Use Resend's default testing domain since custom domain is unverified
        sender_email = "onboarding@resend.dev" 
        
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={"from": sender_email, "to": [NOTIFICATION_EMAIL], "subject": subject, "html": body},
            timeout=10
        )
        print(f"📧 Email Send Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ Email Error Details: {resp.text}")
    except Exception as e:
        print(f"❌ Email Exception: {e}")

def fetch_backend_vehicles(pax, luggage, pickup, dropoff):
    """Fetch real vehicle suggestions from Backend API"""
    url = f"{BACKEND_BASE_URL}/api/vehicles/available"
    print(f"🚗 Fetching cars from: {url} (pax={pax}, route={pickup}->{dropoff})")
    try:
        # Backend likely needs route info to calculate price/availability
        params = {
            "passengers": pax, 
            "luggage": luggage,
            "pickup_location": pickup,
            "dropoff_location": dropoff
        }
        resp = requests.get(url, params=params, timeout=6)
        print(f"🚗 Backend Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            vehicles = []
            if isinstance(data, list):
                vehicles = data
            elif isinstance(data, dict):
                vehicles = data.get("data", []) or data.get("vehicles", [])
            return vehicles
            
    except Exception as e:
        print(f"❌ Backend Fetch Error: {e}")
    return []

def sync_booking_to_backend(booking_data):
    """Sync confirmed booking to external backend"""
    url = f"{BACKEND_BASE_URL}/api/bookings"
    try:
        print(f"🔄 Syncing booking to {url}...")
        resp = requests.post(url, json=booking_data, timeout=5)
        print(f"🔄 Sync Status: {resp.status_code}")
    except Exception as e:
        print(f"❌ Sync Error: {e}")

# ✅ 4. AI BRAIN (The "Fluid" Part)
def run_ai(history, slots):
    system = f"""
    You are Bareerah, Star Skyline Limousine's AI agent.
    
    GOAL: Complete this 3-Step Flow:
    1. **COLLECT DETAILS**: Ask one-by-one for Name, Pickup, Dropoff, DateTime.
    2. **PITCH OPTIONS**: When you have those 4 items, output action: "confirm_pitch". (Do not ask "what car" yet).
    3. **FINALIZE**: The user will hear prices. When they choose a car, extract 'preferred_vehicle' and output action: "finalize".
    
    Current Info: {json.dumps(slots)}
    
    Rules:
    - If user selects a car (e.g. "The Lexus", "The first one"), set 'preferred_vehicle'.
    - Once 'preferred_vehicle' is set -> action: "finalize".
    
    Output JSON: {{ "response": "text", "new_slots": {{key: val}}, "action": "continue|confirm_pitch|finalize" }}
    """
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system}] + history[-6:],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(resp.choices[0].message.content)
    except:
        return {"response": "Could you say that again?", "new_slots": {}, "action": "continue"}

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
    gather = resp.gather(input='speech', action='/handle', timeout=4)
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
        p = resolve_address(state['slots'].get('pickup', 'Dubai'))
        d = resolve_address(state['slots'].get('dropoff', 'Dubai'))
        base_dist = calc_dist(p, d)
        
        # Fetch Real Options
        options = fetch_backend_vehicles(state['slots'].get('passengers', 1))
        
        # Construction of the Pitch
        if options:
            pitch = "I have checked availability. "
            for v in options[:2]: # Top 2
                price = int(v.get('base_price', 50) + (base_dist * v.get('rate_per_km', 3.5)))
                pitch += f"A {v['model']} is {price} Dirhams. "
            pitch += "Which one would you like to book?"
        else:
            # Fallback Pitch
            sedan_price = int(50 + (base_dist * 3.5))
            suv_price = int(80 + (base_dist * 5.0))
            pitch = f"I have a Lexus ES for {sedan_price} Dirhams or a GMC Yukon for {suv_price} Dirhams. Which do you prefer?"
        
        # Override AI response with accurate pricing pitch
        ai_msg = pitch
        state['history'].append({"role": "assistant", "content": pitch})

    elif action == "finalize":
        p = resolve_address(state['slots'].get('pickup', 'Dubai'))
        d = resolve_address(state['slots'].get('dropoff', 'Dubai'))
        base_dist = calc_dist(p, d)
        
        # Determine Car & Price (Default Logic if not explicit)
        pref = state['slots'].get('preferred_vehicle', 'Lexus').lower()
        if 'suv' in pref or 'gmc' in pref:
             car_model = "GMC Yukon"
             fare = int(80 + (base_dist * 5.0))
        elif 'van' in pref:
             car_model = "Mercedes V-Class"
             fare = int(90 + (base_dist * 6.0))
        else:
             car_model = "Lexus ES"
             fare = int(50 + (base_dist * 3.5))

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

        # Send Email
        send_email("Booking Confirmed", f"<p>Name: {state['slots'].get('customer_name')}<br>Car: {car_model}<br>Fare: AED {fare}</p>")
        
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
    gather = resp.gather(input='speech', action='/handle', timeout=4)
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
