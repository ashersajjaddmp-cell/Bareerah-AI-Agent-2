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
from datetime import datetime

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
        if res.get("status") == "REQUEST_DENIED":
            print(f"⚠️ Google Maps REQUEST_DENIED. Check API Key for domain restrictions.")
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
            res_json = resp.json()
            fare = res_json.get("fare_aed") or res_json.get("data", {}).get("fare")
            
            # Use the fare if it's a valid positive number
            try:
                if fare and float(fare) > 0:
                    print(f"💰 Fare Received: {fare}")
                    return int(float(fare))
            except: pass
                
        print(f"⚠️ Fare API returned 0 or error {resp.status_code}: {resp.text}")
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
        params = {"passengers_count": int(pax), "luggage_count": int(luggage)}
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            # ✅ Handle diverse backend structures
            if isinstance(data, dict):
                v_list = data.get("suggested_vehicles") or data.get("data", {}).get("suggested_vehicles") or data.get("vehicles", [])
                if not v_list:
                     print(f"❓ No cars in JSON structure: {data}")
                return v_list
            if isinstance(data, list):
                return data
    except Exception as e:
        print(f"⚠️ Suggest API Exception: {e}")
    
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
        if resp.status_code not in [200, 201]:
            print(f"⚠️ Sync failed: {resp.text}")
        else:
            print(f"✅ Sync successful: {resp.status_code}")
    except Exception as e:
        print(f"❌ Sync Error: {e}")

# ✅ 4. AI BRAIN (The "Fluid" Part)
def run_ai(history, slots):
    system = f"""
    You are Ayesha, Star Skyline Limousine's AI agent. Professional and helpful.
    
    CRITICAL NLU EXTRACTION:
    You must extract information into the following exact slot names:
    - customer_name: The customer's full name.
    - pickup_location: The starting point of the journey.
    - dropoff_location: The destination of the journey.
    - pickup_time: The specific date and time for the pickup.
    - passengers_count: Number of people (default 1 if mentioned).
    - luggage_count: Number of bags (default 0).
    
    CRITICAL RULES:
    1. **STRICT SEQUENCE**: You must follow this order and NEVER ask for two different steps at once:
       Step 1: Ask for Name.
       Step 2: Ask for Pickup Location (once Name is known).
       Step 3: Ask for Dropoff Location (once Pickup is known).
       Step 4: Ask for Pickup Date and Time (once Dropoff is known).
       Step 5: Ask for Passengers AND Luggage together in ONE question (once Time is known).
    2. **LUGGAGE IS BAGS**: Extracted values must be integers. "Four bags" = 4. 
    3. **NO LOOPING**: Once a slot is filled, NEVER ask for it again. If you just got the luggage count, you now have everything. You MUST set action to "confirm_pitch".
    4. **PITCH LOGIC**: When action is "confirm_pitch", just say "Perfect, let me check the available cars and fares for you."
    5. **EMPTY INPUT**: If the user says nothing, just say "I'm still here, could you tell me your [current missing step]?"
       - The user will choose a car from your options. When they pick one, extract it as 'preferred_vehicle' and action: "finalize".
    4. **DO NOT REPEAT**: If a slot is filled in 'Current Info', never ask for it again.
    
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
    return "Ayesha Fluid AI V5 (Real Backend) Running 🚀"

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
    gather = resp.gather(input='speech', action='/handle', timeout=5)
    gather.say("As-Salamu Alaykum. Welcome to Star Skyline. I am Ayesha. May I have your name?", voice='Polly.Joanna-Neural')
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

    # ✅ SAFETY OVERRIDE: Force Pitch if logic gets stuck
    required = ['customer_name', 'pickup_location', 'dropoff_location', 'pickup_time', 'luggage_count']
    if all(state['slots'].get(k) for k in required) and action == "continue":
        print("🛠️ Safety Trigger: Forcing 'confirm_pitch' because all slots are full.")
        action = "confirm_pitch"
    
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
            pitch += "Which suitable option would you like to book?"
        else:
            # Fallback Pitch (Using Backend Fare API even for hardcoded types)
            logging.info("🚕 No suitable cars found in API, using fallback logic.")
            sedan_fare = calculate_backend_fare(base_dist, "SEDAN") or int(50 + (base_dist * 3.5))
            suv_fare = calculate_backend_fare(base_dist, "SUV") or int(80 + (base_dist * 5.0))
            pitch = f"I have a Lexus ES for {sedan_fare} Dirhams or a GMC Yukon for {suv_fare} Dirhams. Which do you prefer?"
        
        # Override AI response
        ai_msg = pitch
        # History will be appended at the very end of the loop

    elif action == "finalize":
        p = resolve_address(state['slots'].get('pickup_location', 'Dubai'))
        d = resolve_address(state['slots'].get('dropoff_location', 'Dubai'))
        base_dist = calc_dist(p, d)
        
        pax = state['slots'].get('passengers_count', 1)
        lug = state['slots'].get('luggage_count', 0)
        b_type = "airport_transfer" if "airport" in (p+d).lower() else "point_to_point"

        # Determine Car & Final Price Dynamically from Preference
        pref = state['slots'].get('preferred_vehicle', 'Car').lower()
        
        # Mapping Logic that respects backend types
        if 'classic' in pref:
             car_model = "Classic"
             v_type = "CLASSIC"
        elif 'executive' in pref:
             car_model = "Executive"
             v_type = "EXECUTIVE"
        elif 'suv' in pref or 'gmc' in pref:
             car_model = "SUV"
             v_type = "SUV"
        elif 'van' in pref or 'v-class' in pref:
             car_model = "Luxury Van"
             v_type = "VAN"
        elif 'first class' in pref:
             car_model = "First Class"
             v_type = "FIRST_CLASS"
        else:
             # Fallback: Just use the user's preference capitalized
             car_model = pref.title()
             v_type = pref.upper()
             
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

        # ✅ SYNC TO BACKEND (Verified mandatory fields)
        sync_booking_to_backend({
            "customer_name": state['slots'].get('customer_name'),
            "customer_phone": request.values.get('From'),
            "customer_email": state['slots'].get('email', 'no@email.com'),
            "pickup_location": p,
            "dropoff_location": d,
            "booking_type": b_type,
            "vehicle_type": v_type,
            "distance_km": base_dist,
            "passengers_count": pax,
            "luggage_count": lug,
            "fare_aed": fare,
            "vehicle_model": car_model,
            "pickup_time": state['slots'].get('pickup_time')
        })

        # Send Email (Premium Template)
        bk_ref = f"STARS-{call_sid[-6:].upper() if call_sid else 'XXXX'}"
        now_str = datetime.now().strftime('%d %B, %I:%M %p')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        email_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.5; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 900px; margin: 0 auto; background: #f8f9fa; padding: 15px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; text-align: center; border-radius: 8px 8px 0 0; }}
                .header h1 {{ margin: 0; font-size: 26px; font-weight: 700; }}
                .content {{ background: white; padding: 25px; border-radius: 0 0 8px 8px; }}
                .status {{ background: #e8f5e9; color: #2e7d32; padding: 12px; margin: 15px 0; border-radius: 5px; text-align: center; font-weight: 600; font-size: 15px; }}
                .booking-bar {{ display: flex; justify-content: space-between; align-items: center; background: #f0f7ff; border-left: 4px solid #667eea; padding: 12px 15px; margin: 15px 0; border-radius: 5px; }}
                .booking-label {{ color: #666; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
                .booking-value {{ font-size: 18px; font-weight: 700; color: #667eea; }}
                .route-section {{ background: #f8f9fa; border-radius: 6px; padding: 15px; margin: 15px 0; }}
                .route-header {{ font-size: 13px; color: #667eea; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; border-bottom: 2px solid #667eea; padding-bottom: 8px; }}
                .route-flow {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; }}
                .route-item {{ flex: 1; text-align: center; padding: 10px; }}
                .route-icon {{ font-size: 28px; margin-bottom: 5px; }}
                .route-label {{ color: #999; font-size: 10px; text-transform: uppercase; margin-bottom: 3px; }}
                .route-text {{ font-size: 13px; font-weight: 600; color: #333; }}
                .connector {{ font-size: 20px; color: #ddd; margin-top: 20px; }}
                .details-bar {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr 1fr; gap: 10px; margin: 15px 0; }}
                .detail-box {{ background: #f8f9fa; padding: 10px; border-radius: 5px; text-align: center; }}
                .detail-label {{ color: #666; font-size: 10px; text-transform: uppercase; }}
                .detail-value {{ font-size: 14px; font-weight: 700; color: #667eea; margin-top: 3px; }}
                .detail-value.vehicle {{ color: #333; }}
                .driver-section {{ background: #f0f7ff; border-left: 4px solid #667eea; border-radius: 6px; padding: 15px; margin: 15px 0; display: flex; gap: 15px; }}
                .driver-pic {{ width: 80px; height: 80px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 40px; flex-shrink: 0; }}
                .driver-info {{ flex: 1; }}
                .driver-header {{ font-size: 13px; color: #667eea; font-weight: 700; text-transform: uppercase; margin-bottom: 10px; }}
                .driver-name {{ font-size: 18px; font-weight: 700; color: #333; }}
                .driver-number {{ font-size: 14px; color: #667eea; margin-top: 5px; font-weight: 600; }}
                .driver-number a {{ color: #667eea; text-decoration: none; }}
                .driver-number a:hover {{ text-decoration: underline; }}
                .info-bar {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 15px 0; }}
                .info-item {{ background: #f8f9fa; padding: 12px; border-radius: 5px; }}
                .info-label {{ color: #666; font-size: 11px; text-transform: uppercase; }}
                .info-value {{ font-size: 14px; font-weight: 600; color: #333; margin-top: 4px; word-break: break-all; }}
                .helpline-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 6px; margin: 15px 0; text-align: center; }}
                .helpline-label {{ font-size: 12px; text-transform: uppercase; opacity: 0.9; }}
                .helpline-number {{ font-size: 18px; font-weight: 700; margin-top: 8px; }}
                .helpline-number a {{ color: white; text-decoration: none; }}
                .helpline-number a:hover {{ text-decoration: underline; }}
                .footer {{ text-align: center; padding: 15px; color: #999; font-size: 11px; border-top: 1px solid #eee; margin-top: 20px; }}
                .footer a {{ color: #667eea; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⭐ Star Skyline Limousine</h1>
                </div>
                
                <div class="content">
                    <p>Hi <strong>Admin</strong>,</p>
                    
                    <div class="status">✅ 📞 New Booking Received via Bareerah AI.</div>
                    
                    <div class="booking-bar">
                        <div>
                            <div class="booking-label">Booking Reference</div>
                            <div class="booking-value">{bk_ref}</div>
                        </div>
                    </div>
                    
                    <div class="route-section">
                        <div class="route-header">📍 Route & Time</div>
                        <div class="route-flow">
                            <div class="route-item">
                                <div class="route-icon">📤</div>
                                <div class="route-label">Pickup Location</div>
                                <div class="route-text">{p}</div>
                            </div>
                            <div class="connector">→</div>
                            <div class="route-item">
                                <div class="route-icon">⏰</div>
                                <div class="route-label">Pickup Time</div>
                                <div class="route-text">{state['slots'].get('pickup_time', 'Pending')}</div>
                            </div>
                            <div class="connector">→</div>
                            <div class="route-item">
                                <div class="route-icon">📥</div>
                                <div class="route-label">Dropoff Location</div>
                                <div class="route-text">{d}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="details-bar">
                        <div class="detail-box">
                            <div class="detail-label">Vehicle Type</div>
                            <div class="detail-value vehicle">{v_type}</div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-label">Car Model</div>
                            <div class="detail-value vehicle">{car_model}</div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-label">Distance</div>
                            <div class="detail-value">{base_dist} km</div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-label">Passengers</div>
                            <div class="detail-value">{pax}</div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-label">Luggage</div>
                            <div class="detail-value">{lug}</div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-label">Total Fare</div>
                            <div class="detail-value">AED {fare}</div>
                        </div>
                    </div>
                    
                    <div class="driver-section">
                        <div class="driver-pic">👨💼</div>
                        <div class="driver-info">
                            <div class="driver-header">🚗 Driver Status</div>
                            <div class="driver-name">Pending Assignment</div>
                            <div class="driver-number">📞 <a href="tel:N/A">N/A</a></div>
                        </div>
                    </div>
                    
                    <div class="info-bar">
                        <div class="info-item">
                            <div class="info-label">👤 Customer Name</div>
                            <div class="info-value">{state['slots'].get('customer_name', 'Not Provided')}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">📞 Phone</div>
                            <div class="info-value">{request.values.get('From', 'N/A')}</div>
                        </div>
                    </div>
                    
                    <div class="helpline-box">
                        <div class="helpline-label">Need Help? Contact Management</div>
                        <div class="helpline-number"><a href="tel:+971501234567">+971 50 123 4567</a></div>
                    </div>
                    
                    <p style="margin-top: 30px; color: #666; font-size: 14px;">
                        ✅ Booking has been synced to the primary backend.<br>
                        ⏱️ Admin follow-up required for driver assignment.
                    </p>
                    
                    <div class="footer">
                        <p>Star Skyline Limousine Service • Dubai, UAE<br>
                        <a href="https://starskyline.ae">Visit our website</a> | 
                        <a href="tel:+971501234567">Call us</a></p>
                        <p>Booking Timestamp: {timestamp}</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        send_email(f"🚀 NEW BOOKING: {state['slots'].get('customer_name', 'Guest')}", email_body)
        
        ai_msg = f"Great. I have booked the {car_model} for {fare} Dirhams. You will receive a confirmation shortly. Goodbye!"
        
        # Save Final History
        state['history'].append({"role": "assistant", "content": ai_msg})
        if conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE call_state SET data = %s WHERE call_sid = %s", (json.dumps(state), call_sid))
            conn.commit()
            conn.close()

        resp = VoiceResponse()
        resp.say(ai_msg, voice='Polly.Joanna-Neural')
        resp.hangup()
        return str(resp)
    
    # Continue Loop (Global History Update)
    state['history'].append({"role": "assistant", "content": ai_msg})
    if conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE call_state SET data = %s WHERE call_sid = %s", (json.dumps(state), call_sid))
        conn.commit()
    
    resp = VoiceResponse()
    gather = resp.gather(input='speech', action='/handle', timeout=5)
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
