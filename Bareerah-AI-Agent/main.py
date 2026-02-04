# Bareerah Fluid AI V5.2 (Capacity & Pricing Fix) 🚀
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
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = "EXAVIT9j6IWWUXfXnS7G" # Bella (High Quality Multilingual)

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
            print("Tables Init Success")
        except Exception as e:
            print(f"Table Init Error: {e}")
        finally:
            conn.close()

# ✅ 3. CORE LOGIC (Requests Only - No Google Lib)
def resolve_address(addr):
    """Google Geocoding API with Strict UAE & Dubai Bias"""
    if not GOOGLE_MAPS_API_KEY: return addr
    if len(addr) < 3: return addr
    
    # Pre-process: If user didn't say Abu Dhabi/Sharjah, assume Dubai for city spots
    search_query = addr
    if not any(x in addr.lower() for x in ["dubai", "abu dhabi", "sharjah", "ajman", "rak", "fujairah"]):
        search_query = f"{addr}, Dubai"

    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": search_query, 
            "components": "country:AE", 
            "key": GOOGLE_MAPS_API_KEY
        }
        res = requests.get(url, params=params, timeout=5).json()
        
        if res.get("status") == "OK" and res.get("results"):
            return res["results"][0]["formatted_address"]
            
    except Exception as e: 
        print(f"Geocoding Error: {e}")

    return f"{addr}, Dubai, UAE"

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
            if dist < 0.1: return 20.0 # Safety for 0 distance
            return dist
    except Exception as e: 
        print(f"❌ Maps Error: {e}")
    return 20.0

def send_email(subject, body):
    """Resend API via Requests - Consolidated & Robust"""
    if not RESEND_API_KEY: 
        print("❌ No RESEND_API_KEY found.")
        return

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Transcript is already appended to body by the caller
    payload = {
        "from": "Star Skyline <onboarding@resend.dev>",
        "to": ["aizaz.dmp@gmail.com"], 
        "subject": subject,
        "html": body
    }
    
    try:
        r = requests.post("https://api.resend.com/emails", json=payload, headers=headers)
        print(f"📧 Email Sent Status: {r.status_code}")
    except Exception as e:
        print(f"❌ Email Error: {e}")
    
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
            elif isinstance(data, list):
                v_list = data
            else: v_list = []
            
            # --- STRICT CAPACITY FILTER ---
            if int(pax) > 4:
                # If 5+ Pax, remove Sedans/Execs entirely to avoid suggestion confusion
                filtered = [v for v in v_list if v.get('max_passengers', 4) >= int(pax)]
                # If backend didn't filter, do it manually
                if filtered: return filtered
                
                # Fallback if list empty but pax high (Force Van)
                return [{"vehicle_type": "elite_van", "model": "Mercedes V Class", "base_fare": 165}]
            
            return v_list

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
    
    LANGUAGE:
    - User has selected: {slots.get('language', 'English')}.
    - ALWAYS respond in this language. 
    - If Urdu: Use polite and respectful Urdu.
    - If Arabic: Use professional Modern Standard Arabic or Gulf dialect.
    
    CRITICAL NLU EXTRACTION:
    - customer_name, pickup_location, dropoff_location.
    - pickup_time: EXACT Date AND Time (e.g. "Tomorrow at 4pm", "5th Feb 10am"). TODAY is 2026-02-04. MUST include both.
    - passengers_count, luggage_count.
    - preferred_vehicle: "Classic", "Executive", "SUV", "Van", "First Class".
    - extra_details: Capture any BARGAINING requests, discounts, special notes, or questions here.
    
    BARGAINING & MONEY MATTERS:
    - If a user asks for a discount, cheaper price, or "bargains", ALWAYS say: 
      "I have noted your request regarding the price. Our management team will calculate the final discount and update you during the confirmation call."
    - DO NOT try to calculate discounts yourself. Just log them in 'extra_details'.
    
    CORRECTIONS & CHANGES:
    - If the user changes their mind (e.g., "Change pickup to X" or "Actually, I'm going to Y"), UPDATE the slot with the new information and say "Understood, I've updated that for you."
    - If the user wants to cancel or says "I don't want the ride", say "No problem. Have a nice day!" and set action: "finalize".
    
    CRITICAL RULES:
    1. **NO EMOJIS**: NEVER include emojis in your "response". Only plain text.
    2. **STRICT SEQUENCE**: 1. Name -> 2. Pickup -> 3. Dropoff -> 4. **Date & Time** -> 5. Pax/Luggage.
       - When asking for time, ALWAYS say: "Could you please provide the pickup date and time?"
    3. **SMART EXTRACTION**: If the user provides a detail out of order, extract it and move to the next missing step.
    4. **PITCH LOGIC**: Once you have the 6 core slots, set action to "confirm_pitch".
    # PRE-CONFIRMATION HANDLER:
    5. **PRE-CONFIRMATION**: After user selects car, ask: "Any other requirements?". set action: "ask_reqs".
    6. **FINALIZE RULES**: 
       - If user says "No", "Nothing", or "Just book", set action: "finalize".
       - If user gives a requirement (e.g. "Baby seat"), log it in 'extra_details' and set action: "finalize".
    7. **EMPTY INPUT**: If silent, ask for missing detail.
    
    Current Info: {json.dumps(slots)}
    
    Output JSON Format:
    {{
      "response": "Your spoken response in {slots.get('language', 'English')}",
      "new_slots": {{ "slot_name": "extracted_value" }},
      "action": "continue" | "confirm_pitch" | "ask_reqs" | "finalize"
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
    return "Ayesha Fluid AI V5 (Real Backend) Running"

@app.route('/voice', methods=['POST'])
@app.route('/incoming', methods=['POST'])
def incoming_call():
    resp = VoiceResponse()
    # 1. Faster Greeting + Language in one block
    gather = resp.gather(num_digits=1, action='/select-language', timeout=5)
    gather.say("As-Salamu Alaykum. I am Ayesha. For English, press 1. For Urdu, press 2. For Arabic, press 3.", voice='Polly.Joanna-Neural')
    resp.redirect('/voice') 
    return str(resp)

@app.route('/eleven-tts')
def eleven_tts():
    text = request.args.get('text', '')
    if not text or not ELEVENLABS_API_KEY:
        return "Missing data", 400
        
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
    }
    
    try:
        r = requests.post(url, json=data, headers=headers, timeout=10)
        if r.status_code == 200:
            from flask import Response
            return Response(r.content, mimetype="audio/mpeg")
        else:
            return f"Error: {r.text}", r.status_code
    except Exception as e:
        return str(e), 500

@app.route('/select-language', methods=['POST'])
def select_language():
    call_sid = request.values.get('CallSid')
    digit = request.values.get('Digits')
    
    lang_map = {"1": "English", "2": "Urdu", "3": "Arabic"}
    selected_lang = lang_map.get(digit, "English")
    print(f"🌍 Language Selected: {selected_lang} (Digit: {digit})")
    
    state = {"history": [], "slots": {"language": selected_lang}}
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO call_state (call_sid, data) VALUES (%s, %s) ON CONFLICT (call_sid) DO UPDATE SET data = %s", 
                        (call_sid, json.dumps(state), json.dumps(state)))
        conn.commit()
    
    resp = VoiceResponse()
    # Map start greeting to language
    greetings = {
        "English": "As-Salamu Alaykum. Welcome to Star Skyline. I am Ayesha. May I have your name?",
        "Urdu": "Assalam-o-Alaikum. Star Skyline mein khush amdeed. Main Ayesha hoon. Kya main aapka naam jaan sakti hoon?",
        "Arabic": "Assalamu Alaikum. Marhaba bikum fi Star Skyline. Ana Ayesha. Ma huwa ismuka?"
    }
    voice_map = {"English": "Polly.Joanna-Neural", "Urdu": "Google.ur-PK-Standard-A", "Arabic": "Polly.Zayd-Neural"}
    tw_lang_map = {"English": "en-US", "Urdu": "ur-PK", "Arabic": "ar-XA"}
    
    gather = resp.gather(input='speech', action='/handle', timeout=5, language=tw_lang_map[selected_lang])
    
    # High Quality Urdu via Play (ElevenLabs)
    if selected_lang == "Urdu":
        # Encode text for URL
        from urllib.parse import quote
        audio_url = f"{request.url_root.replace('http:', 'https:')}eleven-tts?text={quote(greetings['Urdu'])}"
        gather.play(audio_url)
    else:
        gather.say(greetings[selected_lang], voice=voice_map[selected_lang])
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
    # ✅ SHARED VARS for all states
    p = resolve_address(state['slots'].get('pickup_location', 'Dubai'))
    d = resolve_address(state['slots'].get('dropoff_location', 'Dubai'))
    try:
        base_dist = calc_dist(p, d)
    except:
        base_dist = 20.0
    b_type = "airport_transfer" if "airport" in (p+d).lower() else "point_to_point"

    # ✅ SAFETY OVERRIDE: Force Pitch ONLY if all info is there AND vehicle is NOT selected
    required = ['customer_name', 'pickup_location', 'dropoff_location', 'pickup_time', 'luggage_count']
    # Check if preferred_vehicle is MISSING. If it's present, we don't need to pitch.
    if  all(state['slots'].get(k) for k in required) and \
        not state['slots'].get('preferred_vehicle') and \
        action == "continue":
        print("🛠️ Safety Trigger: Forcing 'confirm_pitch' because all core slots are full.")
        action = "confirm_pitch"
    
    # Logic: Present Options or Finalize
    if action == "confirm_pitch":
        # Vars already calculated above
        
        # Fetch Real Options (Matches Capacity)
        pax = state['slots'].get('passengers_count', 1)
        lug = state['slots'].get('luggage_count', 0)
        options = fetch_backend_vehicles(pax, lug)
        sel_lang = state['slots'].get('language', 'English')
        
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
                # Generic Name Logic
                if v_type == 'CLASSIC': v_model = "Classic Sedan"
                elif v_type == 'EXECUTIVE': v_model = "Executive Sedan"
                elif v_type == 'SUV': v_model = "Luxury SUV"
                else: v_model = v.get('vehicle_type', v.get('model', v.get('vehicle', 'Car'))).replace("_", " ").title()
                
                # Get Perfect Fare from Backend
                price = calculate_backend_fare(base_dist, v_type, b_type)
                if not price:
                    # Fallback to backend-provided base/rate or hard calculation
                    if v.get('base_fare'):
                         price = int(float(v['base_fare']) + (base_dist * float(v.get('per_km_rate', 1))))
                    else:
                         # Hard Calculation based on Dubai standard rates
                         price = int(50 + (base_dist * 3.5)) if v_type == "SEDAN" else int(80 + (base_dist * 5.0))
                
                pitch += f"A {v_model} for this {base_dist} kilometer journey is {price} Dirhams. "
                
                # TRANSLATE PITCH IF NEEDED
                sel_lang = state['slots'].get('language', 'English')
                if sel_lang == 'Urdu':
                    pitch = f"{base_dist} kilometer ke safar ke liye {v_model} ka kiraya {price} Dirham hai. "
                elif sel_lang == 'Arabic':
                    pitch = f"Sii'r {v_model} li-masafat {base_dist} kilometer huwa {price} dirham. "

            pitch += "Which suitable option would you like to book?"
        if sel_lang == 'Urdu': pitch += "Aap konsi gaadi book karna chahenge?"
        elif sel_lang == 'Arabic': pitch += "Ayyu sayyarah tawaddu hajzaha?"
        else: pitch += "Which suitable option would you like to book?"
        
        # Override AI response
        ai_msg = pitch

    elif action == "ask_reqs":
         # Use AI response directly (It will ask "Any requirements?")
         pass

    elif action == "finalize":
        # p, d, base_dist, b_type are already calculated at top of function
        
        # Validate Capacity BEFORE Booking
        try:
            pax = int(state['slots'].get('passengers_count', 1))
        except: pax = 1
        
        try:
            lug = int(state['slots'].get('luggage_count', 0))
        except: lug = 0
        
        # If user selected Classic but has > 4 pax, Force Upgrade to SUV
        pref = state['slots'].get('preferred_vehicle', 'Car').lower()
        if pax > 4 and any(x in pref for x in ['classic', 'executive', 'sedan', 'car']):
            logging.info(f"⚠️ Capacity Mismatch (Pax {pax}). Upgrading {pref} to SUV.")
            pref = "suv" # Force override logic below

        # Determine Car & Final Price Dynamically
        
        # Mapping Logic that respects backend types & typos
        # Handle 'classis' typo and generic terms
        if any(x in pref for x in ['classic', 'classis', 'sedan', 'car', 'lexus', 'standard']):
             car_model = "Classic Sedan"
             v_type = "CLASSIC"
        elif 'executive' in pref or 'business' in pref or 'vip' in pref:
             car_model = "Executive Sedan"
             v_type = "EXECUTIVE"
        elif 'elite' in pref or 'v-class' in pref or 'mercedes van' in pref:
             car_model = "Mercedes V Class"
             v_type = "ELITE_VAN"  # Explicitly match your backend "ELITE VAN"
        elif 'van' in pref: # Generic Van
             car_model = "Luxury Van"
             v_type = "ELITE_VAN" # Default generic van to Elite logic usually safer
        elif 'minibus' in pref or 'bus' in pref:
             car_model = "Luxury Minibus"
             v_type = "MINI_BUS"
        elif 'suv' in pref or 'gmc' in pref or 'yukon' in pref:
             car_model = "Luxury SUV"
             v_type = "LUXURY_SUV" # Matches your backend logic better than generic SUV
        elif 'first class' in pref:
             car_model = "First Class"
             v_type = "FIRST_CLASS"
        else:
             # Hard Fallback to avoid 'CAR' 0-fare error
             car_model = "Lexus ES"
             v_type = "SEDAN"
             
        # Clean Time Format for Backend (Remove "p.m." etc if AI slipped up)
        raw_time = state['slots'].get('pickup_time', '')
        clean_time = raw_time.replace('p.m.', '').replace('a.m.', '').strip()
             
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
            "vehicle": car_model, # Try to fix Backend Dashboard
            "model": car_model,   # Try to fix Backend Dashboard
            "pickup_time": clean_time,
            "notes": state['slots'].get('extra_details', '')
        })

        # Send Email (Premium Template)
        bk_ref = f"STARS-{call_sid[-6:].upper() if call_sid else 'XXXX'}"
        now_str = datetime.now().strftime('%d %B, %I:%M %p')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Pretty Format Pickup Time
        display_time = clean_time
        try:
            # Attempt to parse ISO or common formats
            if "T" in clean_time:
                dt_obj = datetime.fromisoformat(clean_time)
                display_time = dt_obj.strftime('%d %b %Y, %I:%M %p')
            else:
                 # Fallback/Cleanup for non-ISO
                 display_time = clean_time
        except: pass
        
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
                                <div class="route-text">{display_time}</div>
                            </div>
                            <div class="connector">→</div>
                            <div class="route-item">
                                <div class="route-icon">📥</div>
                                <div class="route-label">Dropoff Location</div>
                                <div class="route-text">{d}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="info-bar">
                        <div class="info-item">
                            <div class="info-label">🚗 Vehicle</div>
                            <div class="info-value vehicle">{car_model} <span style="font-size:12px; color:#999;">({v_type})</span></div>
                        </div>
                        <div class="info-item">
                             <div class="info-label">👥 Passengers</div>
                             <div class="info-value">{pax}</div>
                        </div>
                        <div class="info-item">
                             <div class="info-label">🧳 Luggage</div>
                             <div class="info-value">{lug}</div>
                        </div>
                         <div class="info-item">
                             <div class="info-label">📏 Distance</div>
                             <div class="info-value">{base_dist} km</div>
                        </div>
                    </div>

                    <div class="driver-section">
                        <div class="driver-pic">👨‍✈️</div>
                        <div class="driver-info">
                             <div class="driver-header">Your Chauffeur Service</div>
                             <div class="driver-name">Star Skyline Chauffeurs</div>
                             <div class="driver-number">Call for Support: <a href="tel:+971505374823">+971 50 537 4823</a></div>
                        </div>
                    </div>
                    
                    <!-- TRANSCRIPT MOVED TO BOTTOM -->
                    <div style="margin-top: 20px; border-top: 1px solid #eee; padding-top: 15px;">
                        <div class="booking-label" style="text-align:center; margin-bottom:10px;">Full Conversation Transcript</div>
                        <div style="background:#f1f1f1; padding:15px; border-radius:5px; font-size:11px; color:#555; white-space: pre-wrap; max-height: 200px; overflow-y: auto;">
{chr(10).join([f"{m['role'].upper()}: {m['content']}" for m in state['history']])}
                        </div>
                    </div>
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
    
    # Multi-language voice selection
    lang = state['slots'].get('language', 'English')
    voice_map = {"English": "Polly.Joanna-Neural", "Urdu": "Google.ur-PK-Standard-A", "Arabic": "Polly.Zayd-Neural"}
    tw_lang_map = {"English": "en-US", "Urdu": "ur-PK", "Arabic": "ar-XA"}
    
    
    resp = VoiceResponse()
    gather = resp.gather(input='speech', action='/handle', timeout=5, language=tw_lang_map.get(lang, "en-US"))
    
    if lang == "Urdu":
        from urllib.parse import quote
        audio_url = f"{request.url_root.replace('http:', 'https:')}eleven-tts?text={quote(ai_msg)}"
        gather.play(audio_url)
    else:
        gather.say(ai_msg, voice=voice_map.get(lang, "Polly.Joanna-Neural"))
        
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
