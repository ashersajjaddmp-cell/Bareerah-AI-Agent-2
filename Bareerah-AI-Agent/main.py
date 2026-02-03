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

# ✅ 4. AI BRAIN (The "Fluid" Part)
def run_ai(history, slots):
    system = f"""
    You are Bareerah, Star Skyline Limousine's AI agent.
    Goal: Book a ride. Collect: Name, Pickup, Dropoff, DateTime, Car Preference.
    
    Current Info: {json.dumps(slots)}
    
    Rules:
    1. No loops. If you have info, don't ask again.
    2. Zero bags = 0.
    3. Any car = "Standard Sedan".
    4. Once all 5 slots filled -> action: "finalize".
    
    Output JSON: {{ "response": "text", "new_slots": {{key: val}}, "action": "continue|finalize" }}
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
    return "Bareerah Fluid AI V4 Running 🚀"

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
    
    # Finalize Logic
    if action == "finalize":
        p = resolve_address(state['slots'].get('pickup', 'Dubai'))
        d = resolve_address(state['slots'].get('dropoff', 'Dubai'))
        fare = int(50 + (calc_dist(p, d) * 3.5))
        
        # Save Booking
        if conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO bookings (customer_name, phone, pickup, dropoff, fare, status) VALUES (%s, %s, %s, %s, %s, 'CONFIRMED')",
                            (state['slots'].get('customer_name'), request.values.get('From'), p, d, str(fare)))
            conn.commit()
            
        send_email("Booking Confirmed", f"<p>Name: {state['slots'].get('customer_name')}<br>Route: {p} to {d}<br>Fare: AED {fare}</p>")
        
        ai_msg = f"Booking confirmed from {p} to {d}. The fare is {fare} Dirhams. Thank you!"
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
