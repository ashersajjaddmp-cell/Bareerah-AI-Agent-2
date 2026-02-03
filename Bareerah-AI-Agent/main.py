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

# ✅ 1. SETUP & CONFIG
load_dotenv()

app = Flask(__name__)
# Configure logging to stdout so it shows in Railway logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
NOTIFICATION_EMAIL = "ashersajjad.dmp@gmail.com"

client = OpenAI(api_key=OPENAI_API_KEY)

# ✅ 2. DATABASE LAYER (Robust)
def get_db():
    try:
        if not DATABASE_URL:
            logging.error("❌ DATABASE_URL is missing!")
            return None
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    except Exception as e:
        logging.error(f"❌ DB Connection Error: {e}")
        return None

def init_app():
    """Create necessary tables on startup"""
    conn = get_db()
    if conn:
        try:
            cur = conn.cursor()
            # 1. Booking Dashboard Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id SERIAL PRIMARY KEY,
                    customer_name TEXT,
                    phone TEXT,
                    pickup TEXT,
                    pickup_lat TEXT,
                    pickup_lng TEXT,
                    dropoff TEXT,
                    dropoff_lat TEXT,
                    dropoff_lng TEXT,
                    fare TEXT,
                    distance_km TEXT,
                    booking_time TEXT,
                    vehicle_type TEXT,
                    status TEXT DEFAULT 'CONFIRMED',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # 2. Call State Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS call_state (
                    call_sid VARCHAR(255) PRIMARY KEY,
                    data JSONB,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            logging.info("✅ Database initialized successfully.")
        except Exception as e:
            logging.error(f"❌ Table Init Error: {e}")
        finally:
            conn.close()

# ✅ 3. INTEGRATIONS (Google, Resend) - NO EXTRA LIBS
def google_geocode(address):
    """Resolve address to formatted string + lat/lng using Google Places Text Search"""
    if not GOOGLE_MAPS_API_KEY:
        logging.warning("⚠️ Google Maps Key missing. Using raw input.")
        return {"address": address, "lat": None, "lng": None}
    
    try:
        url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            "input": address,
            "inputtype": "textquery",
            "fields": "formatted_address,geometry",
            "key": GOOGLE_MAPS_API_KEY
        }
        res = requests.get(url, params=params, timeout=5).json()
        if res.get("status") == "OK" and res.get("candidates"):
            cand = res["candidates"][0]
            fmt = cand.get("formatted_address")
            loc = cand.get("geometry", {}).get("location", {})
            return {"address": fmt, "lat": loc.get("lat"), "lng": loc.get("lng")}
    except Exception as e:
        logging.error(f"⚠️ Geo Error: {e}")
    
    return {"address": address, "lat": None, "lng": None}

def google_distance(origin, dest):
    """Calculate distance in KM between strictly formatted strings or coords"""
    if not GOOGLE_MAPS_API_KEY: return 25.0
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": origin,
            "destinations": dest,
            "mode": "driving",
            "key": GOOGLE_MAPS_API_KEY
        }
        res = requests.get(url, params=params, timeout=5).json()
        if res.get("rows"):
            elem = res["rows"][0]["elements"][0]
            if elem.get("status") == "OK":
                return elem["distance"]["value"] / 1000.0
    except Exception as e:
        logging.error(f"⚠️ Dist Error: {e}")
    return 25.0

def send_confirmation_email(booking):
    """Send HTML email via Resend API (Requests)"""
    if not RESEND_API_KEY:
        logging.warning("⚠️ Resend Key missing. Skipping email.")
        return
    
    subject = f"🚖 New Booking: {booking.get('customer_name')}"
    html = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #333;">New Booking Confirmed</h2>
        <p><strong>Customer:</strong> {booking.get('customer_name')}</p>
        <p><strong>Phone:</strong> {booking.get('phone')}</p>
        <hr>
        <p><strong>Pickup:</strong> {booking.get('pickup')}</p>
        <p><strong>Dropoff:</strong> {booking.get('dropoff')}</p>
        <p><strong>Time:</strong> {booking.get('datetime')}</p>
        <p><strong>Vehicle:</strong> {booking.get('vehicle')}</p>
        <p><strong>Fare:</strong> {booking.get('fare')} AED</p>
        <p><strong>Distance:</strong> {booking.get('distance')} km</p>
    </div>
    """
    
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={
                "from": "Star Skyline <bookings@starskyline.ae>",
                "to": [NOTIFICATION_EMAIL],
                "subject": subject,
                "html": html
            },
            timeout=5
        )
        if resp.status_code in [200, 201]:
            logging.info(f"✅ Email sent to {NOTIFICATION_EMAIL}")
        else:
            logging.error(f"❌ Email Failed: {resp.text}")
    except Exception as e:
        logging.error(f"❌ Email Exception: {e}")

# ✅ 4. AI LOGIC (GPT-4o)
def ai_brain_decision(history, slots):
    """
    Decides the next move based on conversation history.
    Returns JSON with response text and updated slots.
    """
    system_prompt = f"""
    You are Bareerah, the booking agent for Star Skyline Limousine.
    YOUR JOB: Collect these 5 items: Name, Pickup, Dropoff, DateTime, Car Preference.
    
    CURRENT KNOWLEDGE:
    {json.dumps(slots)}
    
    GUIDELINES:
    1. **Be Efficient**: Ask for missing items naturally.
    2. **Locations**: If user gives a location, accept it. (We validate later).
    3. **Time**: If user says "tomorrow", ask "what time?".
    4. **Car**: If user says "Standard" or "Any", use "Lexus ES".
    5. **Confirmation**: When ALL 5 are collected, output action="finalize" to generate price.
    
    OUTPUT FORMAT (JSON):
    {{
      "response_text": "Strings to speak",
      "extracted_updates": {{ "slot_name": "value" }},
      "action": "continue" | "finalize"
    }}
    """
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}] + history[-8:],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        logging.error(f"❌ AI Error: {e}")
        return {"response_text": "I'm having trouble hearing you. Can you repeat?", "extracted_updates": {}, "action": "continue"}

# ✅ 5. ROUTE HANDLER
@app.route('/handle', methods=['POST'])
def handle_call():
    call_sid = request.values.get('CallSid') or "test_sid"
    speech = request.values.get('SpeechResult', '').strip()
    caller = request.values.get('From', 'Unknown')
    
    conn = get_db()
    
    # A. Load State
    state = {"history": [], "slots": {}}
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM call_state WHERE call_sid = %s", (call_sid,))
            row = cur.fetchone()
            if row: state = row['data']
    
    # B. First Contact
    if not speech and not state['history']:
        # Save initial state
        if conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO call_state (call_sid, data) VALUES (%s, %s)", (call_sid, json.dumps(state)))
            conn.commit()
            
        resp = VoiceResponse()
        gather = resp.gather(input='speech', action='/handle', timeout=4)
        gather.say("Welcome to Star Skyline. This is Bareerah. May I have your name?", voice='Polly.Joanna-Neural')
        return str(resp)

    # C. Update History
    state['history'].append({"role": "user", "content": speech})
    
    # D. Consult AI
    decision = ai_brain_decision(state['history'], state['slots'])
    
    ai_resp = decision.get("response_text", "Understood.")
    updates = decision.get("extracted_updates", {})
    action = decision.get("action", "continue")
    
    # E. Apply Updates (with Geo Validation if needed)
    for k, v in updates.items():
        if k in ['pickup', 'dropoff']:
            # Store raw first, background validation is faster but let's do sync for accuracy
            geo = google_geocode(v)
            state['slots'][k] = geo['address'] # Formatted address
            state['slots'][f'{k}_lat'] = geo['lat']
            state['slots'][f'{k}_lng'] = geo['lng']
        else:
            state['slots'][k] = v
            
    state['history'].append({"role": "assistant", "content": ai_resp})

    # F. Finalize (Logic Trigger)
    if action == "finalize":
        # 1. Calculate Price
        p = state['slots'].get('pickup', 'Dubai')
        d = state['slots'].get('dropoff', 'Dubai')
        
        # Use Lat/Lng if available for precision
        p_coord = f"{state['slots'].get('pickup_lat')},{state['slots'].get('pickup_lng')}" if state['slots'].get('pickup_lat') else p
        d_coord = f"{state['slots'].get('dropoff_lat')},{state['slots'].get('dropoff_lng')}" if state['slots'].get('dropoff_lat') else d
        
        dist_km = google_distance(p_coord, d_coord)
        fare = int(50 + (dist_km * 3.5)) # Simple logic
        
        state['slots']['fare'] = str(fare)
        state['slots']['distance'] = f"{dist_km:.1f}"
        
        # 2. Save to Dashboard DB
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bookings 
                    (customer_name, phone, pickup, pickup_lat, pickup_lng, dropoff, dropoff_lat, dropoff_lng, fare, distance_km, booking_time, vehicle_type, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'CONFIRMED')
                """, (
                    state['slots'].get('customer_name'),
                    caller,
                    state['slots'].get('pickup'),
                    str(state['slots'].get('pickup_lat')),
                    str(state['slots'].get('pickup_lng')),
                    state['slots'].get('dropoff'),
                    str(state['slots'].get('dropoff_lat')),
                    str(state['slots'].get('dropoff_lng')),
                    str(fare),
                    str(dist_km),
                    state['slots'].get('datetime'),
                    state['slots'].get('preferred_vehicle', 'Lexus ES')
                ))
            conn.commit()

        # 3. Send Email
        booking_data = {
            "customer_name": state['slots'].get('customer_name'),
            "phone": caller,
            "pickup": state['slots'].get('pickup'),
            "dropoff": state['slots'].get('dropoff'),
            "datetime": state['slots'].get('datetime'),
            "vehicle": state['slots'].get('preferred_vehicle', 'Lexus ES'),
            "fare": fare,
            "distance": f"{dist_km:.1f}"
        }
        send_confirmation_email(booking_data)
        
        # 4. Final Response
        final_msg = f"I have confirmed your booking from {p} to {d}. The total fare is {fare} Dirhams. A confirmation has been sent. Thank you for choosing Star Skyline."
        
        resp = VoiceResponse()
        resp.say(final_msg, voice='Polly.Joanna-Neural')
        resp.hangup()
        return str(resp)

    # G. Save State & Respond
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO call_state (call_sid, data) VALUES (%s, %s)
                ON CONFLICT (call_sid) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
            """, (call_sid, json.dumps(state)))
        conn.commit()
        conn.close()

    resp = VoiceResponse()
    gather = resp.gather(input='speech', action='/handle', timeout=4)
    gather.say(ai_resp, voice='Polly.Joanna-Neural')
    resp.redirect('/handle')
    
    return str(resp)

@app.route('/', methods=['GET'])
def index():
    return "Bareerah AI V3 (Crash-Proof) is Running 🚀"

# Init DB on startup
with app.app_context():
    init_app()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000))
