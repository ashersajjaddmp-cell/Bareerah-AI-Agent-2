import os
import json
import logging
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse
from openai import OpenAI
from dotenv import load_dotenv

# ✅ LOAD ENV
load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ✅ CONFIG
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
NOTIFICATION_EMAIL = "ashersajjad.dmp@gmail.com"

client = OpenAI(api_key=OPENAI_API_KEY)

# ✅ DB CONNECTION
def get_db():
    try:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    except Exception as e:
        logging.error(f"DB Error: {e}")
        return None

def init_tables():
    conn = get_db()
    if conn:
        try:
            cur = conn.cursor()
            # State Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS call_state (
                    call_sid VARCHAR(255) PRIMARY KEY,
                    data JSONB,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Dashboard Table (Simplified)
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
        finally:
            conn.close()

# ✅ GOOGLE API HELPERS (No External Libs)
def google_geocode(address):
    """Find lat/lng and formatted address"""
    if not GOOGLE_MAPS_API_KEY: return address
    try:
        url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            "input": address,
            "inputtype": "textquery",
            "fields": "formatted_address,geometry",
            "key": GOOGLE_MAPS_API_KEY
        }
        res = requests.get(url, params=params).json()
        if res.get("status") == "OK" and res.get("candidates"):
            return res["candidates"][0]["formatted_address"]
    except Exception as e:
        logging.error(f"Geo Error: {e}")
    return address

def google_distance(origin, dest):
    """Get KM distance"""
    if not GOOGLE_MAPS_API_KEY: return 25
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": origin,
            "destinations": dest,
            "mode": "driving",
            "key": GOOGLE_MAPS_API_KEY
        }
        res = requests.get(url, params=params).json()
        if res.get("rows"):
            element = res["rows"][0]["elements"][0]
            if element.get("status") == "OK":
                return element["distance"]["value"] / 1000.0
    except Exception as e:
        logging.error(f"Dist Error: {e}")
    return 25

# ✅ EMAIL HELPER (Requests Only)
def send_email_via_resend(subject, html_body):
    if not RESEND_API_KEY: 
        print("❌ No Resend Key")
        return
    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "from": "Star Skyline <bookings@starskyline.ae>", # Update if you have a verified sender
            "to": [NOTIFICATION_EMAIL],
            "subject": subject,
            "html": html_body
        }
        resp = requests.post(url, headers=headers, json=data)
        print(f"📧 Email Status: {resp.status_code}")
    except Exception as e:
        logging.error(f"Email Error: {e}")

# ✅ AI BRAIN
def consult_brain(history, current_slots):
    system = f"""
    You are Bareerah, the AI agent for Star Skyline Limousine.
    GOAL: Book a ride by collecting: Name, Pickup, Dropoff, DateTime, Vehicle Preference.
    
    CURRENT DATA: {json.dumps(current_slots)}
    
    RULES:
    1. **Natural Flow**: Don't be robotic. If you have the info, move on.
    2. **Locations**: If user gives a vague place (e.g., "Marina"), accept it. We define it later.
    3. **Zero Bags**: "No luggage" = 0.
    4. **Any Car**: "Whatever" or "Standard" = "Lexus ES".
    5. **Confirmation**: Once you have all 5 items, summarize and ask to confirm.
    
    OUTPUT JSON:
    {{
        "response_text": "What you say to user",
        "extracted_slots": {{ "key": "value" }},  <-- Only NEW/UPDATED info
        "action": "continue" | "lookup_locations" | "finalize"
    }}
    """
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system}] + history[-8:],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(completion.choices[0].message.content)
    except Exception:
        return {"response_text": "Could you say that again?", "extracted_slots": {}, "action": "continue"}

# ✅ ROUTE
@app.route('/handle', methods=['POST'])
def handle():
    call_sid = request.values.get('CallSid')
    speech = request.values.get('SpeechResult', '')
    
    # 1. Load/Init State
    conn = get_db()
    state = {}
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM call_state WHERE call_sid = %s", (call_sid,))
            row = cur.fetchone()
            state = row['data'] if row else {"history": [], "slots": {}}
    
    # 2. Greeting (First Run)
    if not speech and not state['history']:
        resp = VoiceResponse()
        gather = resp.gather(input='speech', action='/handle', timeout=4)
        gather.say("Welcome to Star Skyline. I am Bareerah. May I have your name?", voice='Polly.Joanna-Neural')
        save_state(call_sid, state, conn)
        return str(resp)
    
    # 3. Update History
    state['history'].append({"role": "user", "content": speech})
    
    # 4. AI Thinking
    decision = consult_brain(state['history'], state['slots'])
    
    # 5. Process Updates
    new_slots = decision.get("extracted_slots", {})
    state['slots'].update(new_slots)
    action = decision.get("action", "continue")
    ai_reply = decision.get("response_text", "I understand.")
    
    # 6. Execute Actions
    if action == "lookup_locations":
        # Validate addresses if they changed
        p = state['slots'].get('pickup')
        d = state['slots'].get('dropoff')
        if p: state['slots']['pickup'] = google_geocode(p)
        if d: state['slots']['dropoff'] = google_geocode(d)
        
    elif action == "finalize":
        # Calc Price & Confirm
        p = state['slots'].get('pickup', 'Dubai')
        d = state['slots'].get('dropoff', 'Dubai')
        dist = google_distance(p, d)
        fare = int(80 + (dist * 3.5)) # Base logic
        
        state['slots']['fare'] = str(fare)
        state['slots']['distance'] = dist
        
        # Save to Dashboard Table
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bookings (customer_name, phone, pickup, dropoff, fare, status)
                    VALUES (%s, %s, %s, %s, %s, 'CONFIRMED')
                """, (
                    state['slots'].get('customer_name'),
                    request.values.get('From'),
                    p, d, str(fare)
                ))
                conn.commit()
        
        # Send Email
        body = f"<h2>New Booking</h2><p>Name: {state['slots'].get('customer_name')}</p><p>Route: {p} to {d}</p><p>Fare: AED {fare}</p>"
        send_email_via_resend("New Booking Confirmed", body)
        
        ai_reply = f"I've confirmed your booking from {p} to {d}. The fare is {fare} Dirhams. A text is on its way. Goodbye!"
        state['history'].append({"role": "assistant", "content": ai_reply})
        save_state(call_sid, state, conn)
        
        resp = VoiceResponse()
        resp.say(ai_reply, voice='Polly.Joanna-Neural')
        resp.hangup()
        return str(resp)

    # 7. Standard Reply
    state['history'].append({"role": "assistant", "content": ai_reply})
    save_state(call_sid, state, conn)
    
    resp = VoiceResponse()
    gather = resp.gather(input='speech', action='/handle', timeout=4)
    gather.say(ai_reply, voice='Polly.Joanna-Neural')
    # Loop safeguard if silence
    resp.redirect('/handle')
    
    return str(resp)

def save_state(sid, data, conn):
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO call_state (call_sid, data) VALUES (%s, %s)
                    ON CONFLICT (call_sid) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                """, (sid, json.dumps(data)))
            conn.commit()
            conn.close()
        except Exception:
            pass

# Init tables on load
init_tables()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000))
