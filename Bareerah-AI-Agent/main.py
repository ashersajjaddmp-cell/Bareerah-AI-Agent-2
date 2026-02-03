import os
import json
import logging
import traceback
import threading
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import googlemaps
from datetime import datetime, timezone, timedelta
import resend

# ✅ 1. LOAD ENVIRONMENT VARIABLES
load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ✅ 2. CONFIGURATION & CLIENTS
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
NOTIFICATION_EMAIL = "ashersajjad.dmp@gmail.com"  # ✅ User's explicit request

client = OpenAI(api_key=OPENAI_API_KEY)
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# ✅ 3. DATABASE HELPERS (PostgreSQL)
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logging.error(f"DB Connection Failed: {e}")
        return None

def init_db():
    """Ensure table exists"""
    conn = get_db_connection()
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
            conn.commit()
            print("✅ DB Init Success")
        except Exception as e:
            print(f"❌ DB Init Failed: {e}")
        finally:
            conn.close()

def load_state(call_sid):
    conn = get_db_connection()
    if not conn: return {}
    try:
        cur = conn.cursor()
        cur.execute("SELECT data FROM call_state WHERE call_sid = %s", (call_sid,))
        row = cur.fetchone()
        return row['data'] if row else {}
    except Exception:
        return {}
    finally:
        conn.close()

def save_state(call_sid, data):
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO call_state (call_sid, data, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (call_sid) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW();
        """, (call_sid, json.dumps(data)))
        conn.commit()
    except Exception as e:
        logging.error(f"Save State Error: {e}")
    finally:
        conn.close()

# ✅ 4. LOGIC TOOLS (Distance, Email)
def calculate_distance(origin, destination):
    """Get driving distance in KM via Google Maps"""
    try:
        matrix = gmaps.distance_matrix(origins=[origin], destinations=[destination], mode="driving")
        if matrix['rows'][0]['elements'][0]['status'] == 'OK':
            dist_text = matrix['rows'][0]['elements'][0]['distance']['text']
            dist_val = matrix['rows'][0]['elements'][0]['distance']['value']
            return dist_val / 1000.0  # Meters to KM
    except Exception as e:
        logging.error(f"GMaps Error: {e}")
    return 25.0  # Fallback avg distance in Dubai

def calculate_fare(distance_km, vehicle_type="sedan"):
    """Simple Formula: Base + (KM * Rate). Can be expanded."""
    base = 50
    rate = 3.5  # AED per km
    
    if "suv" in vehicle_type.lower() or "land cruiser" in vehicle_type.lower():
        base = 80
        rate = 5.0
    elif "lexus" in vehicle_type.lower():
        base = 60
        rate = 4.0
        
    return int(base + (distance_km * rate))

def send_booking_email(booking_details):
    """Send confirmation to ashersajjad.dmp@gmail.com"""
    if not RESEND_API_KEY:
        print("❌ No Resend API Key found.")
        return

    html_content = f"""
    <h2>New Booking Confirmed (Star Skyline)</h2>
    <p><strong>Customer:</strong> {booking_details.get('customer_name', 'Unknown')}</p>
    <p><strong>Phone:</strong> {booking_details.get('phone', 'Unknown')}</p>
    <hr>
    <ul>
        <li><strong>Pickup:</strong> {booking_details.get('pickup')}</li>
        <li><strong>Dropoff:</strong> {booking_details.get('dropoff')}</li>
        <li><strong>Date/Time:</strong> {booking_details.get('datetime')}</li>
        <li><strong>Car:</strong> {booking_details.get('vehicle', 'Standard Sedan')}</li>
        <li><strong>Est. Fare:</strong> AED {booking_details.get('fare', 'TBD')}</li>
    </ul>
    """
    
    try:
        r = resend.Emails.send({
            "from": "Star Skyline <bookings@starskyline.ae>", # Replace with verified domain if needed or use 'onboarding@resend.dev' for testing
            "to": [NOTIFICATION_EMAIL],
            "subject": f"🚖 New Booking: {booking_details.get('customer_name')}",
            "html": html_content
        })
        print(f"✅ Email Sent: {r}")
    except Exception as e:
        print(f"❌ Email Failed: {e}")

# ✅ 5. AI BRAIN (The Core - FLUID LOGIC)
def get_ai_decision(history, state):
    """
    Ask GPT-4o to decide the next step based on conversation history and current slots.
    Goal: Eliminate hardcoded flow loops.
    """
    system_prompt = f"""
    You are Bareerah, an intelligent booking agent for 'Star Skyline' Limousines in Dubai.
    
    YOUR GOAL: Collect 5 pieces of info locally (Name, Pickup, Dropoff, Date/Time, Car Preference) 
    and then Confirm the booking.
    
    CURRENT STATE:
    {json.dumps(state, indent=2)}
    
    RULES:
    1. **Be Fluid**: Do not follow a rigid script. If the user gives all info at once, accept it.
    2. **No Loops**: If you have a value in CURRENT STATE, DO NOT ask for it again unless the user explicitly changes it.
    3. **Smart Defaults**: 
       - If user says 'Luggage' is 0 or 'No bags', accept it.
       - If user says 'Any car', set preference to 'Standard'.
    4. **Output JSON**:
       {{
         "response_text": "Strings to speak to user",
         "updated_slots": {{key: value}},  <-- Only fields that changed/new
         "next_action": "continue" | "calculate_price" | "confirm_booking" | "end_call"
       }}
    
    ACTIONS:
    - **continue**: Keep asking questions.
    - **calculate_price**: When you have Pickup + Dropoff + Car Preference, trigger this to get a fare quotes.
    - **confirm_booking**: When user agrees to the price/details.
    - **end_call**: Only if user hangs up or says goodbye.
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
    ] + history[-10:] # Keep last 10 turns context
    
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return {
            "response_text": "I'm sorry, I'm having trouble connecting. Could you say that again?",
            "updated_slots": {},
            "next_action": "continue"
        }

# ✅ 6. FLASK ROUTE (Twilio Webhook)
@app.route('/handle', methods=['POST'])
def handle_call():
    call_sid = request.values.get('call_sid') or request.values.get('CallSid')
    user_speech = request.values.get('SpeechResult', '').strip()
    caller_phone = request.values.get('From')
    
    # 1. Load context
    state = load_state(call_sid)
    if not state:
        state = {
            "slots": {}, 
            "history": [], 
            "status": "active"
        }
        # Initial greeting is handled by Twilio's 'gather' logic usually, 
        # but if this is the FIRST hit (Start of call), we might just return a greeting.
        if not user_speech: 
            resp = VoiceResponse()
            gather = resp.gather(input='speech', action='/handle', speechTimeout='auto')
            gather.say("Hello, this is Bareerah from Star Skyline Limo. Can I have your name?", voice='Polly.Joanna-Neural')
            return str(resp)

    # 2. Update History
    if user_speech:
        state['history'].append({"role": "user", "content": user_speech})
    
    # 3. Consult AI Brain
    decision = get_ai_decision(state['history'], state['slots'])
    
    # 4. Process Decision
    ai_response = decision.get('response_text', "can you repeat?")
    slots_update = decision.get('updated_slots', {})
    next_action = decision.get('next_action', 'continue')
    
    # Merge slots
    state['slots'].update(slots_update)
    
    # 5. Handle Specialized Actions
    if next_action == "calculate_price":
        # AI wants to pitch price. Use Tools.
        p_up = state['slots'].get('pickup', 'Dubai')
        d_off = state['slots'].get('dropoff', 'Dubai')
        car = state['slots'].get('vehicle_preference', 'sedan')
        
        dist = calculate_distance(p_up, d_off)
        fare = calculate_fare(dist, car)
        
        state['slots']['fare'] = fare
        state['slots']['distance_km'] = dist
        
        # Inject this info back to AI to construct the pitch sentence
        ai_response = f"The estimated distance is {int(dist)} kilometers. For a {car}, the fare is AED {fare}. Shall I confirm this booking?"
        state['history'].append({"role": "assistant", "content": ai_response}) 
        
    elif next_action == "confirm_booking":
        # Finalize
        booking_data = {
            "customer_name": state['slots'].get('customer_name'),
            "phone": caller_phone,
            "pickup": state['slots'].get('pickup'),
            "dropoff": state['slots'].get('dropoff'),
            "datetime": state['slots'].get('datetime'),
            "vehicle": state['slots'].get('vehicle_preference'),
            "fare": state['slots'].get('fare')
        }
        
        # Async email sending
        threading.Thread(target=send_booking_email, args=(booking_data,)).start()
        
        ai_response = "Great! Your ride is booked. I've sent the confirmation to our dispatch team. Thank you for choosing Star Skyline."
        state['history'].append({"role": "assistant", "content": ai_response})
        state['status'] = 'completed'
    
    else:
        # Standard conversation
        state['history'].append({"role": "assistant", "content": ai_response})

    # 6. Save State
    save_state(call_sid, state)

    # 7. Generate TwiML
    resp = VoiceResponse()
    if next_action == "end_call" or state.get('status') == 'completed':
        resp.say(ai_response, voice='Polly.Joanna-Neural')
        resp.hangup()
    else:
        # Continue gathering
        gather = resp.gather(input='speech', action='/handle', speechTimeout='auto')
        gather.say(ai_response, voice='Polly.Joanna-Neural')
        # If no input, re-prompt lightly
        resp.say("Are you still there?", voice='Polly.Joanna-Neural')
        resp.redirect('/handle')
        
    return str(resp)

@app.route('/', methods=['GET', 'POST'])
def index():
    return "Bareerah AI Backend is Running 🚀"

# Init DB thread
threading.Thread(target=init_db).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
