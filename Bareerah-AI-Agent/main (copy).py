from flask import Flask, request, Response, jsonify, render_template, send_file
from twilio.twiml.voice_response import VoiceResponse
import os
import requests
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool, sql
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import uuid
from uuid import uuid4
import threading
import re
import hashlib
from openai import OpenAI
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
import tempfile

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bareerah-secret-key')

OPENAI_CLIENT = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
WEBSITE_URL = os.environ.get("WEBSITE_URL", "")
BASE_API_URL = "https://5ef5530c-38d9-4731-b470-827087d7bc6f-00-2j327r1fnap1d.sisko.replit.dev:8000/api"

# ✅ COST + SPEED OPTIMIZATION: Production mode flag
PRODUCTION_MODE = os.environ.get("PRODUCTION_MODE", "true").lower() == "true"
DEBUG_LOGGING = os.environ.get("DEBUG_LOGGING", "false").lower() == "true"

os.makedirs('public', exist_ok=True)

db_pool = None
_tts_prewarmed = False
call_contexts = {}
offline_bookings = []
utterance_count = {}  # Track utterance count per call for language detection
slot_retry_count = {}  # ✅ Track slot retry attempts (max 2)
consecutive_failures = {}  # ✅ Track consecutive fatal failures (max 2)

# ✅ Pre-generated static TTS cache (line 26-27)
STATIC_TTS_CACHE = {
    "greeting": None,
    "hold_message": None,
    "no_speech": None,
    "confirm_pickup": None,
    "confirm_dropoff": None
}

EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

# ✅ STT LANGUAGE DETECTION: Keywords for Urdu/Arabic
URDU_KEYWORDS = {"meri", "mera", "mein", "hoon", "hain", "dubai", "marina", "airport", "malik", "sahab", "acha", "theek", "bilkul"}
ARABIC_KEYWORDS = {"alhijra", "almarina", "dubai", "masr", "ahal", "tayyib", "sahih", "almaer", "hawaya"}

def detect_language_from_speech(text: str, current_language: str) -> str:
    """
    Detect if user is speaking Urdu or Arabic from keywords.
    Returns detected language or current_language.
    """
    text_lower = text.lower()
    
    # Count keyword matches
    urdu_count = sum(1 for kw in URDU_KEYWORDS if kw in text_lower)
    arabic_count = sum(1 for kw in ARABIC_KEYWORDS if kw in text_lower)
    
    if urdu_count > 0:
        return "ur"
    if arabic_count > 0:
        return "ar"
    
    return current_language

def transcribe_with_whisper(audio_file_path: str, language: str = "en") -> str:
    """
    Use OpenAI Whisper for multi-language transcription (Urdu/Arabic support).
    Language mapping: en, ur (Urdu), ar (Arabic)
    """
    if not OPENAI_API_KEY:
        return None
    
    try:
        with open(audio_file_path, 'rb') as audio_file:
            # Whisper language codes
            lang_codes = {"en": "en", "ur": "ur", "ar": "ar"}
            whisper_lang = lang_codes.get(language, "en")
            
            if DEBUG_LOGGING:
                    print(f"[WHISPER] Transcribing with language={whisper_lang}", flush=True)
            
            transcript = OPENAI_CLIENT.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=whisper_lang,
                timeout=10
            )
            
            text = transcript.text.strip()
            if DEBUG_LOGGING:
                    print(f"[WHISPER] ✅ Transcribed ({language}): {text}", flush=True)
            return text
    except Exception as e:
        if DEBUG_LOGGING:
                print(f"[WHISPER] ❌ Failed: {e}", flush=True)
        return None
GENERIC_LOCATION_TERMS = ["location", "here", "there", "airport", "mall", "home"]

# ✅ MISSION CRITICAL: Confidence gates (Req #2)
CONFIDENCE_GATES = {
    "pickup": 0.75,
    "dropoff": 0.75,
    "name": 0.80,
    "phone": 0.90,
    "email": 0.95,
    "passengers": 0.80,
    "luggage": 0.80
}

# ✅ MISSION CRITICAL: Negative token hard blocks (Req #3)
NEGATIVE_TOKENS_EN = {"is", "no", "yes", "ok", "okay", "right", "here", "there", "that", "this", "sure", "please", "again", "maybe", "yeah", "uh", "um", "hmm", "alright", "fine", "done", "go", "ahead"}
NEGATIVE_TOKENS_UR = {"haan", "nahi", "theek", "acha", "bas", "yahan", "wahan", "woh", "yeh"}
NEGATIVE_TOKENS_AR = {"نعم", "لا", "هنا", "هناك", "تمام", "حسنا"}

# ✅ Geo-semantic markers (Req #4)
GEO_MARKERS = {"airport", "mall", "tower", "street", "road", "avenue", "hotel", "terminal", "marina", "downtown", "city"}

# ✅ PATCH: Hard-block generic/garbage words (Req #1)
GENERIC_WORDS_EN = {"location", "airport", "mall", "here", "there", "this", "that", "yes", "no", "ok", "okay", "right", "sure", "maybe"}
GENERIC_WORDS_UR = {"yahan", "wahan", "haan", "nahi", "theek", "bas", "acha"}
GENERIC_WORDS_AR = {"هنا", "هناك", "نعم", "لا", "تمام"}

# ✅ PATCH: Filler words to strip (Req #8)
FILLER_WORDS_EN = {"is", "am", "a", "the"}
FILLER_WORDS_UR = {"hai", "ho", "hun", "mera", "meri", "my"}
FILLER_WORDS_AR = {"من", "في", "على"}

# ✅ PATCH: Explicit correction keywords (Req #3)
CORRECTION_KEYWORDS_EN = {"change", "correct", "wrong", "no not", "nope", "nah"}
CORRECTION_KEYWORDS_UR = {"galat", "wrong", "nahi", "correction", "badal"}
CORRECTION_KEYWORDS_AR = {"خطأ", "لا", "تصحيح"}

# ✅ Numeric conversion (Req #5)
SPOKEN_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
}

FLEET_INVENTORY = [
    {"id": "VEH001", "vehicle": "Toyota Camry", "plate": "Dubai G 54821", "driver_name": "Ahmed Raza", "driver_phone": "055 823 1124", "type": "Sedan", "hourly_rate": 75, "per_km_rate": 3.50},
    {"id": "VEH002", "vehicle": "Toyota Corolla", "plate": "Dubai R 22914", "driver_name": "Bilal Hussain", "driver_phone": "056 993 4410", "type": "Sedan", "hourly_rate": 75, "per_km_rate": 3.50},
    {"id": "VEH003", "vehicle": "Honda Civic", "plate": "Dubai L 78102", "driver_name": "Imran Shah", "driver_phone": "050 662 2287", "type": "Sedan", "hourly_rate": 75, "per_km_rate": 3.50},
    {"id": "VEH004", "vehicle": "Lexus ES350", "plate": "Dubai A 99211", "driver_name": "Muhammad Kashif", "driver_phone": "052 771 6621", "type": "Luxury", "hourly_rate": 150, "per_km_rate": 6.50},
    {"id": "VEH005", "vehicle": "GMC Yukon", "plate": "Dubai J 33487", "driver_name": "Sufyan Ali", "driver_phone": "055 118 9934", "type": "SUV", "hourly_rate": 90, "per_km_rate": 4.50},
    {"id": "VEH006", "vehicle": "Toyota Previa", "plate": "Dubai S 55901", "driver_name": "Usman Tariq", "driver_phone": "050 331 9002", "type": "Van", "hourly_rate": 90, "per_km_rate": 4.50},
    {"id": "VEH007", "vehicle": "Chevrolet Tahoe", "plate": "Dubai C 41022", "driver_name": "Salman Yousaf", "driver_phone": "054 909 7733", "type": "SUV", "hourly_rate": 90, "per_km_rate": 4.50},
    {"id": "VEH008", "vehicle": "Nissan Altima", "plate": "Dubai K 77120", "driver_name": "Daniyal Ahmed", "driver_phone": "055 288 4421", "type": "Sedan", "hourly_rate": 75, "per_km_rate": 3.50},
    {"id": "VEH009", "vehicle": "Honda Accord", "plate": "Dubai T 44719", "driver_name": "Zeeshan Sharif", "driver_phone": "056 119 0301", "type": "Sedan", "hourly_rate": 75, "per_km_rate": 3.50},
    {"id": "VEH010", "vehicle": "Mercedes Viano", "plate": "Dubai Y 92014", "driver_name": "Farhan Saleem", "driver_phone": "052 812 5512", "type": "Luxury Van", "hourly_rate": 150, "per_km_rate": 6.50},
]

def init_db_pool():
    global db_pool
    try:
        db_pool = pool.SimpleConnectionPool(minconn=1, maxconn=20, dsn=DATABASE_URL)
        print("[DB] ✅ Connection pool initialized", flush=True)
    except Exception as e:
        print(f"[DB] ❌ Pool error: {e}", flush=True)

def get_db_conn():
    if not db_pool:
        init_db_pool()
    return db_pool.getconn()

def return_db_conn(conn):
    if db_pool:
        db_pool.putconn(conn)

executor = ThreadPoolExecutor(max_workers=10)

def backend_login_with_retry():
    for attempt in range(2):
        try:
            r = requests.post(f"{BASE_API_URL}/auth/login",
                              json={"username":"admin","password":"admin123"},
                              timeout=5)
            if r.status_code == 200:
                try:
                    token = r.json().get("token")
                    if token:
                        print(f"[AUTH] ✅ Login successful", flush=True)
                        return token
                except:
                    pass
        except:
            pass
        if attempt < 1:
            time.sleep(1)
    return None

def backend_api(method, path, data=None, jwt_token=None):
    """✅ OPTIMIZED: Max 1 retry, timeout 1.5s"""
    for attempt in range(2):
        try:
            headers = {"Content-Type": "application/json"}
            if jwt_token:
                headers["Authorization"] = f"Bearer {jwt_token}"
            
            url = f"{BASE_API_URL}{path}"
            
            if method == "POST":
                r = requests.post(url, json=data, headers=headers, timeout=1.5)
            else:
                r = requests.get(url, headers=headers, timeout=1.5)
            
            if r.status_code in [200, 201]:
                try:
                    return r.json()
                except:
                    return {"success": True}
            
            if r.status_code == 400:
                if DEBUG_LOGGING:
                        print(f"[API] ❌ 400 Error on {path}: {r.text[:100]}", flush=True)
                return None
            
        except:
            pass
        
        if attempt < 1:
            time.sleep(0.5)  # Reduced wait
    
    return None

# ✅ MISSION CRITICAL VALIDATION FUNCTIONS (Req #1-7)

def is_negative_token(text: str, language: str = "en") -> bool:
    """Hard-block negative tokens that should never be extracted"""
    if not text:
        return True
    text_normalized = text.lower().strip()
    if language == "ur":
        return text_normalized in NEGATIVE_TOKENS_UR
    elif language == "ar":
        return text_normalized in NEGATIVE_TOKENS_AR
    else:
        return text_normalized in NEGATIVE_TOKENS_EN

def has_geo_marker(text: str) -> bool:
    """Check if location contains at least one geo-semantic marker"""
    if not text or len(text) < 4:
        return False
    text_lower = text.lower()
    return any(marker in text_lower for marker in GEO_MARKERS)

def normalize_numeric_values(text: str) -> int:
    """
    Extract and normalize numeric values:
    - Convert spoken numbers (one=1, six=6, etc.)
    - Sum all quantities in text (6 bags + 2 hand = 8)
    - Return total count
    """
    if not text:
        return 0
    
    text_lower = text.lower()
    total = 0
    
    # Convert spoken numbers
    for word, num in SPOKEN_NUMBERS.items():
        if word in text_lower:
            total += num
            text_lower = text_lower.replace(word, "")
    
    # Extract digits
    import re
    digits = re.findall(r'\d+', text_lower)
    for digit_str in digits:
        total += int(digit_str)
    
    # Block ambiguous cases
    ambiguous = {"many", "lot", "few", "couple", "lots", "several"}
    if any(amb in text_lower for amb in ambiguous):
        return None  # Force re-ask
    
    return total if total > 0 else 0

def force_urdu_for_hindi(language: str) -> str:
    """Req #1: Hard-disable Hindi, force Urdu"""
    if language == "hi" or language == "hi-IN":
        return "ur"
    return language

def validate_location(text: str, confidence: float) -> bool:
    """Req #4: Validate pickup/dropoff with strict geo-semantic checks"""
    if not text or confidence < 0.75:
        return False
    if is_negative_token(text):
        return False
    if is_generic_location(text):
        return False
    if not has_geo_marker(text):
        return False
    if len(text.strip()) < 4:
        return False
    
    # Reject if it's only a verb
    verb_only = {"go", "come", "need", "want", "take"}
    if text.lower().strip() in verb_only:
        return False
    
    return True

def validate_confidence(value, entity_type: str, confidence: float) -> bool:
    """Req #2: Global confidence gates - reject if below threshold"""
    if entity_type not in CONFIDENCE_GATES:
        return confidence >= 0.70
    return confidence >= CONFIDENCE_GATES[entity_type]

def is_generic_location(text: str) -> bool:
    text_lower = text.lower().strip()
    return text_lower in GENERIC_LOCATION_TERMS

def is_generic_word(text: str, language: str = "en") -> bool:
    """✅ PATCH: Hard-block generic/garbage words (Req #1)"""
    if not text:
        return True
    text_normalized = text.lower().strip()
    
    if language == "ur":
        return text_normalized in GENERIC_WORDS_UR
    elif language == "ar":
        return text_normalized in GENERIC_WORDS_AR
    else:
        return text_normalized in GENERIC_WORDS_EN

def strip_filler_words(text: str, language: str = "en") -> str:
    """✅ PATCH: Strip filler words before validation (Req #8)"""
    if not text:
        return text
    
    text_lower = text.lower()
    
    if language == "ur":
        for filler in FILLER_WORDS_UR:
            text_lower = text_lower.replace(f" {filler} ", " ").replace(f"{filler} ", "")
    elif language == "ar":
        for filler in FILLER_WORDS_AR:
            text_lower = text_lower.replace(filler, "")
    else:
        for filler in FILLER_WORDS_EN:
            text_lower = text_lower.replace(f" {filler} ", " ").replace(f"{filler} ", "")
    
    return text_lower.strip()

def validate_location_structure(text: str, language: str = "en", confidence: float = 0.75) -> bool:
    """
    ✅ PATCH: Minimum structure for location lock (Req #2)
    Requirements:
    - confidence >= 0.75
    - token_count >= 2
    - Contains at least 1 geo-keyword
    - Not in generic word blocklist
    """
    if not text or confidence < 0.75:
        return False
    
    # Strip filler words
    cleaned = strip_filler_words(text, language)
    
    if is_generic_word(cleaned, language):
        return False
    
    # Token count
    tokens = cleaned.split()
    if len(tokens) < 2:
        return False
    
    # Geo-keyword check
    if not has_geo_marker(cleaned):
        return False
    
    return True

def has_explicit_correction(text: str, language: str = "en") -> bool:
    """✅ PATCH: Check for explicit correction keywords (Req #3)"""
    if not text:
        return False
    
    text_lower = text.lower()
    
    if language == "ur":
        return any(kw in text_lower for kw in CORRECTION_KEYWORDS_UR)
    elif language == "ar":
        return any(kw in text_lower for kw in CORRECTION_KEYWORDS_AR)
    else:
        return any(kw in text_lower for kw in CORRECTION_KEYWORDS_EN)

def get_gather_params(call_sid: str, stt_language: str = None, utterance_num: int = 0) -> dict:
    """
    ✅ Language-aware gather parameters.
    - Utterance 1-2: English (phone_call) to establish connection
    - Utterance 3+: Detected language (Urdu/Arabic) via 'default' (Whisper)
    """
    if stt_language is None:
        stt_language = call_contexts.get(call_sid, {}).get("stt_language", "en")
    
    params = {
        "num_digits": 0,
        "action": f"/handle?call_sid={call_sid}",
        "method": 'POST',
        "input": 'speech',
        "speech_timeout": 2,
        "max_speech_time": 30,
        "timeout": 30,
        "enhanced": True
    }
    
    # ✅ Switch STT model after first 2 utterances
    if utterance_num < 2:
        params["speech_model"] = "phone_call"  # English-only, fast
    else:
        if stt_language in ["ur", "ar"]:
            params["speech_model"] = "default"  # Triggers Whisper multi-lang
        else:
            params["speech_model"] = "phone_call"
    
    return params

def normalize_spoken_email(text: str) -> str:
    if not text:
        return ""
    t = text.lower().strip()
    t = t.replace(" at the rate ", "@")
    t = t.replace(" at rate ", "@")
    t = t.replace(" at ", "@")
    t = t.replace(" underscore ", "_")
    t = t.replace(" dash ", "-")
    t = t.replace(" hyphen ", "-")
    t = t.replace(" dot ", ".")
    t = t.replace(" dotcom", ".com")
    t = t.replace(" gmail com", "gmail.com")
    t = t.replace(" yahoo com", "yahoo.com")
    t = t.replace(" ", "")
    return t

def suggest_vehicle(passengers: int, luggage: int) -> tuple:
    """
    REQ #6: STRICT vehicle selection with hard capacity enforcement.
    Reads ONLY from LOCKED SLOTS. Must NOT use defaults.
    
    Returns: (vehicle_type, error_msg or None)
    """
    try:
        passengers = int(passengers) if passengers else None
        luggage = int(luggage) if luggage else None
    except:
        passengers = None
        luggage = None
    
    # HARD FAIL if any slot missing (Req #6)
    if passengers is None or luggage is None:
        return None, "Missing passenger or luggage count"
    
    # HARD FAIL on zero values (Req #5)
    if passengers <= 0 or luggage < 0:
        return None, "Invalid passenger/luggage values"
    
    # HARD BLOCK: Sedan forbidden if luggage >= 4 (any case) or passengers >= 4 AND luggage >= 4
    if luggage >= 4:
        if passengers > 4:
            return "van", None
        return "suv", None
    
    # Van needed for high passenger count
    if passengers > 6 or luggage > 6:
        return "van", None
    
    # SUV needed if exceeds sedan capacity
    if passengers > 4 or luggage > 3:
        return "suv", None
    
    # Sedan is eligible
    return "sedan", None

def detect_booking_type(pickup: str, dropoff: str) -> str:
    airport_keywords = ["airport", "dxb", "international", "terminal"]
    pickup_lower = pickup.lower()
    dropoff_lower = dropoff.lower()
    
    if any(kw in pickup_lower for kw in airport_keywords) or any(kw in dropoff_lower for kw in airport_keywords):
        return "airport_transfer"
    return "point_to_point"

def normalize_airport(location: str) -> str:
    if "airport" in location.lower():
        if "terminal" not in location.lower():
            return "Dubai International Airport Terminal 1"
        return location
    return location

def ensure_booking_state(context):
    if "booking" not in context or not context["booking"]:
        context["booking"] = {
            "full_name": None,
            "name_locked": False,
            "caller_number": None,
            "confirmed_contact_number": None,
            "phone_locked": False,
            "phone_confirm_count": 0,
            "email": None,
            "email_attempts": 0,
            "email_locked": False,
            "pickup": None,
            "pickup_locked": False,
            "pickup_confirm_pending": False,
            "dropoff": None,
            "dropoff_locked": False,
            "dropoff_confirm_pending": False,
            "datetime": None,
            "datetime_locked": False,
            "datetime_confirm_pending": False,
            "passengers": None,
            "passengers_locked": False,
            "luggage_count": None,
            "luggage_locked": False,
            "vehicle_type": None,
            "vehicle_locked": False,
            "vehicle_confirm_pending": False,
            "distance_km": None,
            "fare": None,
            "fare_locked": False,
            "booking_type": None,
            "confirmed": False,
            "booking_reference": None
        }
        context["flow_step"] = "greeting"
        context["language"] = "en"
        context["language_locked"] = False
        context["call_initialized"] = False

def prewarm_elevenlabs_tts():
    global _tts_prewarmed
    if _tts_prewarmed or not ELEVENLABS_API_KEY:
        return
    try:
        voice_id = "EXAVITQu4vr4xnSDxMaL"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        payload = {"text": "Hi", "voice_settings": {"stability": 0.3, "similarity_boost": 0.7}}
        requests.post(url, json=payload, headers=headers, timeout=5)
        _tts_prewarmed = True
    except:
        pass

def generate_tts(text, call_sid, lang="en"):
    if not text or len(text) == 0:
        return None
    
    text_chunk = text[:240]
    text_hash = hashlib.md5(text_chunk.encode()).hexdigest()
    filename = f"tts_{text_hash}.mp3"
    filepath = f"./public/{filename}"
    
    if os.path.exists(filepath):
        return f"/public/{filename}"
    
    try:
        voice_id = "EXAVITQu4vr4xnSDxMaL"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        payload = {
            "text": text_chunk,
            "voice_settings": {"stability": 0.3, "similarity_boost": 0.7}
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
        
        with open(filepath, "wb") as f:
            f.write(response.content)
        
        return f"/public/{filename}"
    except:
        return None

def calculate_distance_google_maps(pickup: str, dropoff: str) -> float:
    """Calculate distance using Google Maps API (required - backend doesn't calculate)"""
    if not GOOGLE_MAPS_API_KEY or not pickup or not dropoff:
        return None
    
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": pickup,
            "destinations": dropoff,
            "key": GOOGLE_MAPS_API_KEY,
            "mode": "driving"
        }
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("rows") and len(data["rows"]) > 0:
                if data["rows"][0].get("elements") and len(data["rows"][0]["elements"]) > 0:
                    distance_meters = data["rows"][0]["elements"][0].get("distance", {}).get("value", 0)
                    distance_km = distance_meters / 1000
                    return round(distance_km, 2)
    except:
        pass
    
    return None

def calculate_fare_api(distance_km, vehicle_type, booking_type, jwt_token):
    """
    PRODUCTION API: Send ONLY distance_km, vehicle_type, booking_type
    Do NOT send: pickup, dropoff, passengers, luggage
    """
    if not distance_km or distance_km <= 0:
        return None
    
    result = backend_api("POST", "/bookings/calculate-fare", {
        "distance_km": distance_km,
        "vehicle_type": vehicle_type,
        "booking_type": booking_type
    }, jwt_token)
    
    if result and "fare_aed" in result:
        fare = result.get("fare_aed")
        return fare
    
    return None

def is_valid_email(email):
    return re.match(EMAIL_REGEX, email) is not None

def translate_to_urdu(text):
    try:
        response = OPENAI_CLIENT.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Translate to natural, conversational Urdu. ONLY return the Urdu text, no explanation."},
                {"role": "user", "content": f"Translate: {text}"}
            ],
            max_tokens=100,
            timeout=5
        )
        return response.choices[0].message.content.strip()
    except:
        return text

def extract_nlu(text, context=None):
    try:
        system_prompt = """You are Bareerah's NLU Engine for limousine booking in Dubai.

ALWAYS return JSON with these keys:
{
 "intent": "",
 "confidence": 0.0,
 "pickup": "",
 "dropoff": "",
 "datetime": "",
 "passengers": "",
 "luggage": "",
 "yes_no": "",
 "full_name": "",
 "email": "",
 "phone": "",
 "language_switch": ""
}

INTENT RULES:
1. If user says yes/confirm → yes_no = "yes"
2. If user says no/reject → yes_no = "no"
3. If user asks for Urdu → language_switch = "urdu"
4. If unclear → intent = "unknown"

Always extract entities as clean strings."""

        user_prompt = f"""Customer said: "{text}"
Extract ONLY valid JSON with confidence score."""

        response = OPENAI_CLIENT.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            timeout=5
        )
        
        try:
            nlu = json.loads(response.choices[0].message.content)
            if "confidence" not in nlu:
                nlu["confidence"] = 0.5
        except:
            nlu = {"intent":"unknown","confidence":0.0,"full_name":None,"email":None,"pickup":None,"dropoff":None,"datetime":None,"passengers":None,"luggage":None,"yes_no":None,"language_switch":None,"phone":None}
        
        return nlu
    except:
        return {"intent":"unknown","confidence":0.0,"full_name":None,"email":None,"pickup":None,"dropoff":None,"datetime":None,"passengers":None,"luggage":None,"yes_no":None,"language_switch":None,"phone":None}

def speak_static_tts(response_obj, message_key, call_sid, lang="en"):
    """✅ OPTIMIZED: Serve pre-generated static TTS from cache"""
    static_messages = {
        "greeting": "Hello, this is Bareerah from Star Skyline Limousine. I will help you book your ride. Please tell me your pickup location.",
        "hold_message": "Thank you for waiting. Let me process your request.",
        "no_speech": "I didn't catch that. Please repeat.",
        "confirm_pickup": "Just to confirm, you want pickup from {{location}}, correct?",
        "confirm_dropoff": "Just to confirm, dropoff at {{location}}, correct?"
    }
    
    text = static_messages.get(message_key, "")
    if not text:
        return
    
    if lang == "ur":
        text = translate_to_urdu(text)
    
    if DEBUG_LOGGING:
            print(f"[BAREERAH] 🎤 {text}", flush=True)
    
    tts_url = generate_tts(text, call_sid, lang)
    if tts_url:
        response_obj.play(tts_url)
        response_obj.pause(length=1)

def speak_text(response_obj, text, call_sid, lang="en"):
    if not text:
        return
    
    if lang == "ur":
        text = translate_to_urdu(text)
    
    if DEBUG_LOGGING:
            print(f"[BAREERAH] 🎤 {text}", flush=True)
    
    tts_url = generate_tts(text, call_sid, lang)
    if tts_url:
        response_obj.play(tts_url)
        response_obj.pause(length=1)

@app.before_request
def init_app():
    global db_pool
    if db_pool is None:
        init_db_pool()
    threading.Thread(target=prewarm_elevenlabs_tts, daemon=True).start()

@app.route('/', methods=['GET'])
def index():
    return "Bareerah Voice AI - Ready for calls"

@app.route('/voice', methods=['POST'])
@app.route('/incoming', methods=['POST'])
def incoming_call():
    """
    ✅ OPTIMIZED STT CONFIGURATION:
    - Urdu/Arabic speakers bypass phone_call entirely
    - Direct to Whisper (no wasted dual-STT calls)
    - English speakers use phone_call (faster, cheaper)
    """
    call_sid = request.values.get('CallSid')
    caller_phone = request.values.get('Caller', 'unknown')
    
    if DEBUG_LOGGING:
            print(f"[CALL] Incoming: {call_sid} from {caller_phone}", flush=True)
    
    if call_sid not in call_contexts:
        call_contexts[call_sid] = {
            "turns": deque(maxlen=10),
            "booking": None,
            "flow_step": "greeting",
            "language": "en",
            "stt_language": "en",
            "language_locked": False,
            "jwt_token": None,
            "call_initialized": False,
            "failure_count": 0  # ✅ Track consecutive failures
        }
    
    if call_sid not in utterance_count:
        utterance_count[call_sid] = 0
    if call_sid not in slot_retry_count:
        slot_retry_count[call_sid] = {}
    
    ensure_booking_state(call_contexts[call_sid])
    call_contexts[call_sid]["booking"]["caller_number"] = caller_phone
    call_contexts[call_sid]["jwt_token"] = backend_login_with_retry()
    
    ctx = call_contexts[call_sid]
    response = VoiceResponse()
    
    if not ctx.get("call_initialized"):
        ctx["call_initialized"] = True
        speak_static_tts(response, "greeting", call_sid, "en")
        if DEBUG_LOGGING:
                print(f"[GREETING] Delivered", flush=True)
    
    # ✅ OPTIMIZED: Detect language immediately, use direct STT
    stt_lang = ctx.get("stt_language", "en")
    gather_params = {
        "num_digits": 0,
        "action": f"/handle?call_sid={call_sid}",
        "method": 'POST',
        "input": 'speech',
        "speech_timeout": 3,  # ✅ OPTIMIZED: Max 3 seconds
        "max_speech_time": 30,
        "timeout": 30,
        "enhanced": True
    }
    
    # ✅ OPTIMIZED: Urdu/Arabic bypass phone_call, go direct to Whisper
    if stt_lang in ["ur", "ar"]:
        gather_params["speech_model"] = "default"  # Direct to Whisper
        if DEBUG_LOGGING:
                print(f"[STT] Direct to Whisper ({stt_lang})", flush=True)
    else:
        gather_params["speech_model"] = "phone_call"  # English: use fast phone_call
    
    # ✅ OPTIMIZED: Max 3 second timeout
    gather_params["speech_timeout"] = 3
    
    response.gather(**gather_params)
    return str(response)

@app.route('/handle', methods=['POST'])
def handle_call():
    call_sid = request.values.get('call_sid', 'unknown')
    speech_result = request.values.get('SpeechResult', '').strip()
    
    if speech_result:
        print(f"[CUSTOMER] 🎧 {speech_result}", flush=True)
    
    if call_sid not in call_contexts:
        call_contexts[call_sid] = {
            "turns": deque(maxlen=10),
            "booking": None,
            "flow_step": "pickup",
            "language": "en",
            "stt_language": "en",  # ✅ Track STT language
            "language_locked": False,
            "jwt_token": backend_login_with_retry(),
            "call_initialized": True
        }
    
    if call_sid not in utterance_count:
        utterance_count[call_sid] = 0
    
    ensure_booking_state(call_contexts[call_sid])
    
    ctx = call_contexts[call_sid]
    booking = ctx["booking"]
    response = VoiceResponse()
    
    # ✅ Increment utterance counter
    utterance_count[call_sid] = utterance_count.get(call_sid, 0) + 1
    
    if not speech_result:
        # ✅ OPTIMIZED: Track retry attempts (max 2 per slot)
        current_slot = booking.get("flow_step", "pickup")
        if current_slot not in slot_retry_count[call_sid]:
            slot_retry_count[call_sid][current_slot] = 0
        slot_retry_count[call_sid][current_slot] += 1
        
        if slot_retry_count[call_sid][current_slot] > 2:
            ctx["failure_count"] += 1
            if ctx["failure_count"] >= 2:
                # ✅ OPTIMIZED: End call after 2 consecutive failures
                speak_static_tts(response, "hold_message", call_sid, ctx["language"])
                print(f"[FATAL] Ending call after {ctx['failure_count']} consecutive failures", flush=True)
                return str(response)
        
        speak_static_tts(response, "no_speech", call_sid, ctx["language"])
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
        return str(response)
    
    # ✅ LANGUAGE DETECTION: Check if Urdu/Arabic in speech
    detected_lang = detect_language_from_speech(speech_result, ctx.get("stt_language", "en"))
    if detected_lang != ctx.get("stt_language"):
        ctx["stt_language"] = detected_lang
        if DEBUG_LOGGING:
                print(f"[STT LANGUAGE SWITCH] {ctx.get('stt_language', 'en')} → {detected_lang}", flush=True)
    
    if DEBUG_LOGGING:
            print(f"[UTTERANCE #{utterance_count[call_sid]}] 🎧 STT({ctx.get('stt_language', 'en')}): {speech_result}", flush=True)
    
    nlu = extract_nlu(speech_result, ctx)
    
    if (nlu.get("language_switch") == "urdu" or "urdu" in speech_result.lower()) and not ctx.get("language_locked"):
        ctx["language"] = "ur"
        ctx["language_locked"] = True
        if DEBUG_LOGGING:
                print(f"[LANGUAGE] Switched to Urdu", flush=True)
    
    if not booking.get("pickup_locked"):
        if booking.get("pickup_confirm_pending"):
            # ✅ PATCH: Check for "No + correction" (Req #3)
            if nlu.get("yes_no") == "yes":
                booking["pickup_locked"] = True
                booking["pickup_confirm_pending"] = False
                if DEBUG_LOGGING:
                        print(f"[BOOKING] ✓ Pickup confirmed and locked: {booking['pickup']}", flush=True)
                reply_en = "Great. Now, where would you like to go?"
                speak_text(response, reply_en, call_sid, ctx["language"])
            elif has_explicit_correction(speech_result, ctx.get("stt_language", "en")):
                # ✅ PATCH: User said "No, my pickup is [corrected value]"
                # Extract new value from same utterance
                correction_text = nlu.get("pickup") or speech_result
                # Remove "no", "nahi" from beginning
                correction_text = re.sub(r"^(no|nahi|nope|لا|خطأ)\s+", "", correction_text, flags=re.IGNORECASE)
                correction_text = strip_filler_words(correction_text, ctx.get("stt_language", "en"))
                
                if is_generic_word(correction_text, ctx.get("stt_language", "en")):
                    if DEBUG_LOGGING:
                            print(f"[GUARD] Rejected generic pickup value after 'No': {correction_text}", flush=True)
                    reply_en = "Please tell me the exact pickup location, like a mall or area name."
                    speak_text(response, reply_en, call_sid, ctx["language"])
                    booking["pickup"] = None
                    booking["pickup_confirm_pending"] = False
                elif not validate_location_structure(correction_text, ctx.get("stt_language", "en"), 0.75):
                    if DEBUG_LOGGING:
                            print(f"[GUARD] Pickup rejected due to low semantic structure: {correction_text}", flush=True)
                    reply_en = "Please tell me the exact pickup location, like 'Dubai Marina Mall' or 'Airport Terminal 3'."
                    speak_text(response, reply_en, call_sid, ctx["language"])
                    booking["pickup"] = None
                    booking["pickup_confirm_pending"] = False
                else:
                    # ✅ PATCH: Clear old and set new
                    if DEBUG_LOGGING:
                            print(f"[GUARD] Overwriting pickup due to explicit correction", flush=True)
                    booking["pickup"] = correction_text
                    booking["pickup_confirm_pending"] = True
                    if DEBUG_LOGGING:
                            print(f"[BOOKING] Pickup locked (after correction): {booking['pickup']}", flush=True)
                    # ✅ PATCH: Confirm ONLY the new value, don't re-ask
                    reply_en = f"I understood your pickup as {booking['pickup']}. Is that correct?"
                    speak_text(response, reply_en, call_sid, ctx["language"])
            else:
                booking["pickup"] = None
                booking["pickup_confirm_pending"] = False
                reply_en = "Understood. Please tell me the exact pickup location."
                speak_text(response, reply_en, call_sid, ctx["language"])
        else:
            pickup_text = nlu.get("pickup") or speech_result
            
            # ✅ PATCH: Strip filler words (Req #8)
            pickup_text = strip_filler_words(pickup_text, ctx.get("stt_language", "en"))
            if DEBUG_LOGGING:
                    print(f"[GUARD] Stripped filler: {nlu.get('pickup') or speech_result} → {pickup_text}", flush=True)
            
            # ✅ PATCH: Hard-block generic words (Req #1)
            if is_generic_word(pickup_text, ctx.get("stt_language", "en")):
                if DEBUG_LOGGING:
                        print(f"[GUARD] Rejected generic pickup value: {pickup_text}", flush=True)
                reply_en = "Please tell me the exact pickup location, like a mall, airport terminal, or area name."
                speak_text(response, reply_en, call_sid, ctx["language"])
            # ✅ PATCH: Validate location structure (Req #2)
            elif not validate_location_structure(pickup_text, ctx.get("stt_language", "en"), 0.75):
                if DEBUG_LOGGING:
                        print(f"[GUARD] Pickup rejected due to low semantic structure", flush=True)
                reply_en = "Please tell me the exact pickup location, like 'Dubai Marina', 'Airport Terminal', or a specific area."
                speak_text(response, reply_en, call_sid, ctx["language"])
            else:
                booking["pickup"] = pickup_text
                booking["pickup_confirm_pending"] = True
                print(f"[BOOKING] Pickup locked: {booking['pickup']}", flush=True)
                # ✅ PATCH: Confirm in clean English (Req #5)
                reply_en = f"I understood your pickup as {booking['pickup']}. Is that correct?"
                speak_text(response, reply_en, call_sid, ctx["language"])
        
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    elif not booking.get("dropoff_locked"):
        if booking.get("dropoff_confirm_pending"):
            # ✅ PATCH: Check for "No + correction" (Req #3)
            if nlu.get("yes_no") == "yes":
                booking["dropoff_locked"] = True
                booking["dropoff_confirm_pending"] = False
                booking["booking_type"] = detect_booking_type(booking["pickup"], booking["dropoff"])
                print(f"[BOOKING] ✓ Dropoff confirmed and locked: {booking['dropoff']}", flush=True)
                reply_en = "Perfect. What date and time do you need the ride?"
                speak_text(response, reply_en, call_sid, ctx["language"])
            elif has_explicit_correction(speech_result, ctx.get("stt_language", "en")):
                # ✅ PATCH: User said "No, my dropoff is [corrected value]"
                correction_text = nlu.get("dropoff") or speech_result
                correction_text = re.sub(r"^(no|nahi|nope|لا|خطأ)\s+", "", correction_text, flags=re.IGNORECASE)
                correction_text = strip_filler_words(correction_text, ctx.get("stt_language", "en"))
                
                # ✅ PATCH: Pickup vs dropoff protection (Req #7)
                if correction_text.lower() == booking.get("pickup", "").lower():
                    if DEBUG_LOGGING:
                        print(f"[GUARD] Rejected: Pickup and dropoff are the same", flush=True)
                    reply_en = "Pickup and drop-off cannot be the same location. Please confirm your drop-off location."
                    speak_text(response, reply_en, call_sid, ctx["language"])
                    booking["dropoff"] = None
                    booking["dropoff_confirm_pending"] = False
                elif is_generic_word(correction_text, ctx.get("stt_language", "en")):
                    if DEBUG_LOGGING:
                        print(f"[GUARD] Rejected generic dropoff value after 'No': {correction_text}", flush=True)
                    reply_en = "Please tell me the exact drop-off location, like an area or building name."
                    speak_text(response, reply_en, call_sid, ctx["language"])
                    booking["dropoff"] = None
                    booking["dropoff_confirm_pending"] = False
                elif not validate_location_structure(correction_text, ctx.get("stt_language", "en"), 0.75):
                    if DEBUG_LOGGING:
                        print(f"[GUARD] Dropoff rejected due to low semantic structure: {correction_text}", flush=True)
                    reply_en = "Please tell me the exact drop-off location, like 'Dubai Airport', 'Downtown Dubai', or an address."
                    speak_text(response, reply_en, call_sid, ctx["language"])
                    booking["dropoff"] = None
                    booking["dropoff_confirm_pending"] = False
                else:
                    if DEBUG_LOGGING:
                        print(f"[GUARD] Overwriting dropoff due to explicit correction", flush=True)
                    if "airport" in correction_text.lower():
                        correction_text = normalize_airport(correction_text)
                    booking["dropoff"] = correction_text
                    booking["dropoff_confirm_pending"] = True
                    print(f"[BOOKING] Dropoff locked (after correction): {booking['dropoff']}", flush=True)
                    reply_en = f"I understood your drop-off as {booking['dropoff']}. Is that correct?"
                    speak_text(response, reply_en, call_sid, ctx["language"])
            else:
                booking["dropoff"] = None
                booking["dropoff_confirm_pending"] = False
                reply_en = "Understood. Please tell me the exact drop-off location."
                speak_text(response, reply_en, call_sid, ctx["language"])
        else:
            dropoff_text = nlu.get("dropoff") or speech_result
            
            # ✅ PATCH: Strip filler words (Req #8)
            dropoff_text = strip_filler_words(dropoff_text, ctx.get("stt_language", "en"))
            print(f"[GUARD] Stripped filler: {nlu.get('dropoff') or speech_result} → {dropoff_text}", flush=True)
            
            # ✅ PATCH: Pickup vs dropoff protection (Req #7)
            if dropoff_text.lower() == booking.get("pickup", "").lower():
                if DEBUG_LOGGING:
                        print(f"[GUARD] Rejected: Pickup and dropoff are the same", flush=True)
                reply_en = "Pickup and drop-off cannot be the same location. Please confirm your drop-off location."
                speak_text(response, reply_en, call_sid, ctx["language"])
            # ✅ PATCH: Hard-block generic words (Req #1)
            elif is_generic_word(dropoff_text, ctx.get("stt_language", "en")):
                if DEBUG_LOGGING:
                        print(f"[GUARD] Rejected generic dropoff value: {dropoff_text}", flush=True)
                reply_en = "Please tell me the exact drop-off location, like an airport, mall, or area name."
                speak_text(response, reply_en, call_sid, ctx["language"])
            # ✅ PATCH: Validate location structure (Req #2)
            elif not validate_location_structure(dropoff_text, ctx.get("stt_language", "en"), 0.75):
                if DEBUG_LOGGING:
                        print(f"[GUARD] Dropoff rejected due to low semantic structure", flush=True)
                reply_en = "Please tell me the exact drop-off location, like 'Dubai Airport Terminal', 'Downtown Dubai', or an address."
                speak_text(response, reply_en, call_sid, ctx["language"])
            else:
                if "airport" in dropoff_text.lower():
                    dropoff_text = normalize_airport(dropoff_text)
                
                booking["dropoff"] = dropoff_text
                booking["dropoff_confirm_pending"] = True
                print(f"[BOOKING] Dropoff locked: {booking['dropoff']}", flush=True)
                # ✅ PATCH: Confirm in clean English (Req #5)
                reply_en = f"I understood your drop-off as {booking['dropoff']}. Is that correct?"
                speak_text(response, reply_en, call_sid, ctx["language"])
        
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    elif not booking.get("datetime_locked"):
        if booking.get("datetime_confirm_pending"):
            if nlu.get("yes_no") == "yes":
                booking["datetime_locked"] = True
                booking["datetime_confirm_pending"] = False
                print(f"[BOOKING] ✓ DateTime confirmed and locked: {booking['datetime']}", flush=True)
                reply_en = "How many passengers?"
                speak_text(response, reply_en, call_sid, ctx["language"])
            else:
                booking["datetime"] = None
                booking["datetime_confirm_pending"] = False
                reply_en = "What date and time do you need the ride?"
                speak_text(response, reply_en, call_sid, ctx["language"])
        else:
            booking["datetime"] = speech_result
            booking["datetime_confirm_pending"] = True
            print(f"[BOOKING] DateTime received: {booking['datetime']}", flush=True)
            reply_en = f"So, {booking['datetime']}, correct?"
            speak_text(response, reply_en, call_sid, ctx["language"])
        
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    elif not booking.get("passengers_locked"):
        # REQ #5: Normalize numeric values
        if is_negative_token(speech_result, ctx["language"]):
            reply_en = "Please tell me the number of passengers."
            speak_text(response, reply_en, call_sid, ctx["language"])
            response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
            return str(response)
        
        passengers_count = normalize_numeric_values(speech_result)
        if passengers_count is None:  # Ambiguous
            reply_en = "Please tell me the exact number: 1, 2, 3, or more?"
            speak_text(response, reply_en, call_sid, ctx["language"])
            response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
            return str(response)
        
        booking["passengers"] = passengers_count
        booking["passengers_locked"] = True
        print(f"[BOOKING] Passengers locked: {passengers_count}", flush=True)
        reply_en = "How many suitcases or bags will you have?"
        speak_text(response, reply_en, call_sid, ctx["language"])
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    elif not booking.get("luggage_locked"):
        # REQ #5: Normalize numeric values (6 bags + 2 hand carries = 8)
        if is_negative_token(speech_result, ctx["language"]):
            reply_en = "Please tell me how many bags or suitcases."
            speak_text(response, reply_en, call_sid, ctx["language"])
            response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
            return str(response)
        
        luggage_count = normalize_numeric_values(speech_result)
        if luggage_count is None:  # Ambiguous
            reply_en = "Please tell me the exact number of bags: 1, 2, 3, or how many?"
            speak_text(response, reply_en, call_sid, ctx["language"])
            response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
            return str(response)
        
        booking["luggage_count"] = luggage_count
        booking["luggage_locked"] = True
        print(f"[BOOKING] Luggage locked: {luggage_count}", flush=True)
        
        # REQ #6: Vehicle selection from LOCKED SLOTS ONLY (never use defaults)
        passengers = booking.get("passengers")
        luggage = booking.get("luggage_count")
        
        if passengers is None or luggage is None:
            # HARD FAIL - should not reach here if flow is correct
            reply_en = "I need to confirm your passenger and luggage count first."
            speak_text(response, reply_en, call_sid, ctx["language"])
            response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
            return str(response)
        
        vehicle_type, error_msg = suggest_vehicle(passengers, luggage)
        
        if error_msg or vehicle_type is None:
            # Auto-correction or hard fail
            reply_en = f"I need to verify your details. Let me ask again about luggage."
            print(f"[BOOKING] Vehicle selection failed: {error_msg}", flush=True)
            booking["luggage_locked"] = False
            booking["luggage_count"] = None
            speak_text(response, reply_en, call_sid, ctx["language"])
            response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
            return str(response)
        
        booking["vehicle_type"] = vehicle_type
        booking["vehicle_confirm_pending"] = True
        print(f"[BOOKING] Vehicle suggested: {vehicle_type} (P:{passengers}, L:{luggage})", flush=True)
        
        reply_en = f"Based on {passengers} passengers and {luggage} luggage, the best vehicle for you is a {vehicle_type}. Is that okay?"
        speak_text(response, reply_en, call_sid, ctx["language"])
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    elif not booking.get("vehicle_locked"):
        if nlu.get("yes_no") == "yes":
            booking["vehicle_locked"] = True
            booking["vehicle_confirm_pending"] = False
            print(f"[BOOKING] ✓ Vehicle confirmed and locked: {booking['vehicle_type']}", flush=True)
            
            reply_en = "Let me calculate your fare."
            speak_text(response, reply_en, call_sid, ctx["language"])
            response.pause(length=2)
            
            # Calculate distance using Google Maps (REQUIRED - backend doesn't do this)
            distance_km = calculate_distance_google_maps(booking["pickup"], booking["dropoff"])
            
            if distance_km:
                booking["distance_km"] = distance_km
                fare = calculate_fare_api(distance_km, booking["vehicle_type"], booking["booking_type"], ctx["jwt_token"])
                
                if fare:
                    booking["fare"] = fare
                    booking["fare_locked"] = True
                    fare_reply = f"Your estimated fare is AED {fare:.0f}."
                    print(f"[BOOKING] Fare locked: Distance {distance_km}km, AED {fare:.0f}", flush=True)
                    speak_text(response, fare_reply, call_sid, ctx["language"])
                else:
                    # REQ #8: Graceful degradation - keep booking alive, don't end call
                    fallback_reply = "I'm unable to fetch the exact fare right now, but your booking details are saved. Our team will contact you shortly with the final price. Would you like me to proceed?"
                    print(f"[BOOKING] Fare calculation failed - graceful degradation", flush=True)
                    speak_text(response, fallback_reply, call_sid, ctx["language"])
                    booking["fare"] = 0  # Placeholder - backend will calculate
                    booking["fare_locked"] = True
            else:
                reply_en = "I'm having trouble calculating the distance. Our team will call you back shortly."
                print(f"[BOOKING] Distance calculation failed - ending", flush=True)
                speak_text(response, reply_en, call_sid, ctx["language"])
                response.hangup()
                return str(response)
            
            reply_en = "What is your full name as it should appear on the booking?"
            speak_text(response, reply_en, call_sid, ctx["language"])
        else:
            booking["vehicle_type"] = None
            booking["vehicle_confirm_pending"] = False
            
            try:
                passengers = int(booking.get("passengers", "1"))
                luggage = int(booking.get("luggage_count", "0"))
            except:
                passengers = 1
                luggage = 0
            
            vehicle_type = suggest_vehicle(passengers, luggage)
            booking["vehicle_type"] = vehicle_type
            booking["vehicle_confirm_pending"] = True
            
            reply_en = f"Based on your {passengers} passengers and {luggage} luggage, the best vehicle for you is a {vehicle_type}. Is that okay?"
            speak_text(response, reply_en, call_sid, ctx["language"])
        
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    elif not booking.get("name_locked"):
        booking["full_name"] = speech_result
        booking["name_locked"] = True
        print(f"[BOOKING] Name confirmed: {booking['full_name']}", flush=True)
        
        reply_en = f"I have your name as {booking['full_name']}. You are calling from {booking['caller_number']}. Do you want us to use this same number for your booking, or a different contact number?"
        speak_text(response, reply_en, call_sid, ctx["language"])
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    elif not booking.get("phone_locked"):
        if nlu.get("yes_no") == "yes" or "same" in speech_result.lower():
            booking["confirmed_contact_number"] = booking["caller_number"]
            print(f"[BOOKING] Phone confirmed (same): {booking['confirmed_contact_number']}", flush=True)
            reply_en = f"Perfect, we will use {booking['confirmed_contact_number']}. What is your email address? Please spell it slowly."
            speak_text(response, reply_en, call_sid, ctx["language"])
            booking["phone_locked"] = True
        else:
            booking["confirmed_contact_number"] = speech_result
            booking["phone_confirm_count"] = booking.get("phone_confirm_count", 0) + 1
            print(f"[BOOKING] Phone provided (different): {booking['confirmed_contact_number']}", flush=True)
            
            if booking["phone_confirm_count"] == 1:
                reply_en = f"So your contact number is {booking['confirmed_contact_number']}, correct?"
                speak_text(response, reply_en, call_sid, ctx["language"])
            else:
                booking["phone_locked"] = True
                reply_en = f"Thank you. We will use {booking['confirmed_contact_number']}. What is your email address? Please spell it slowly."
                speak_text(response, reply_en, call_sid, ctx["language"])
        
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    elif booking.get("phone_confirm_count", 0) == 1 and not booking.get("phone_locked"):
        if nlu.get("yes_no") == "yes":
            booking["phone_locked"] = True
            print(f"[BOOKING] ✓ Phone confirmed and locked: {booking['confirmed_contact_number']}", flush=True)
            reply_en = "What is your email address? Please spell it slowly."
            speak_text(response, reply_en, call_sid, ctx["language"])
        else:
            booking["confirmed_contact_number"] = None
            booking["phone_confirm_count"] = 0
            reply_en = "Please provide the contact number we should use."
            speak_text(response, reply_en, call_sid, ctx["language"])
        
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    elif not booking.get("email_locked"):
        normalized = normalize_spoken_email(speech_result)
        
        if is_valid_email(normalized):
            booking["email"] = normalized
            booking["email_locked"] = True
            print(f"[BOOKING] Email locked: {booking['email']}", flush=True)
            
            confirmation_script = f"Please confirm: Pickup from {booking['pickup']}, drop-off at {booking['dropoff']}, on {booking['datetime']}, {booking['passengers']} passengers, {booking['luggage_count']} luggage, {booking['vehicle_type']}, AED {booking['fare']:.0f}, name {booking['full_name']}, phone {booking['confirmed_contact_number']}, email {booking['email']}. Shall I confirm and create this booking now?"
            speak_text(response, confirmation_script, call_sid, ctx["language"])
        else:
            booking["email_attempts"] = booking.get("email_attempts", 0) + 1
            if booking["email_attempts"] >= 2:
                booking["email"] = None
                booking["email_locked"] = True
                print(f"[BOOKING] Email skipped after 2 attempts", flush=True)
                
                confirmation_script = f"Please confirm: Pickup from {booking['pickup']}, drop-off at {booking['dropoff']}, on {booking['datetime']}, {booking['passengers']} passengers, {booking['luggage_count']} luggage, {booking['vehicle_type']}, AED {booking['fare']:.0f}, name {booking['full_name']}, phone {booking['confirmed_contact_number']}. Shall I confirm and create this booking now?"
                speak_text(response, confirmation_script, call_sid, ctx["language"])
            else:
                reply_en = "Please spell your email using 'A for Apple, B for Ball, C for Cat' and use 'at' and 'dot'."
                speak_text(response, reply_en, call_sid, ctx["language"])
        
        response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    elif not booking.get("confirmed"):
        if nlu.get("yes_no") == "yes":
            if not booking.get("pickup") or not booking.get("dropoff") or not booking.get("datetime") or not booking.get("passengers") or not booking.get("luggage_count") or not booking.get("confirmed_contact_number") or not booking.get("fare"):
                print(f"[BOOKING] Validation failed - missing fields", flush=True)
                reply_en = "There seems to be an issue. Let me verify your details."
                speak_text(response, reply_en, call_sid, ctx["language"])
                response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
                return str(response)
            
            # PRODUCTION SCHEMA - Exact fields required by backend
            booking_payload = {
                "customer_name": booking.get("full_name", "Customer"),
                "customer_phone": booking.get("confirmed_contact_number"),
                "customer_email": booking.get("email") or None,
                "pickup_location": booking["pickup"],
                "dropoff_location": booking["dropoff"],
                "distance_km": booking.get("distance_km", 0),
                "fare_aed": booking.get("fare", 0),
                "vehicle_type": booking.get("vehicle_type", "sedan"),
                "booking_type": booking.get("booking_type", "point_to_point"),
                "passengers_count": int(booking.get("passengers", 1)) if booking.get("passengers") else 1,
                "luggage_count": int(booking.get("luggage_count", 0)) if booking.get("luggage_count") else 0,
                "caller_number": booking.get("caller_number"),
                "confirmed_contact_number": booking.get("confirmed_contact_number"),
                "payment_method": "cash"
            }
            
            result = backend_api("POST", "/bookings/create-booking", booking_payload, ctx["jwt_token"])
            
            if result and result.get("success"):
                ref_num = str(uuid4())[:8].upper()
                booking["booking_reference"] = ref_num
                booking["confirmed"] = True
                print(f"[BOOKING] ✅ SUCCESS | Ref: {ref_num} | Name: {booking['full_name']} | Phone: {booking['confirmed_contact_number']} | Email: {booking['email']} | Vehicle: {booking['vehicle_type']} | Fare: AED {booking['fare']:.0f}", flush=True)
                confirm_reply = f"Your booking is confirmed. Our driver will contact you shortly. Thank you for choosing us."
                speak_text(response, confirm_reply, call_sid, ctx["language"])
            else:
                result = backend_api("POST", "/bookings/create-booking", booking_payload, ctx["jwt_token"])
                if result and result.get("success"):
                    ref_num = str(uuid4())[:8].upper()
                    booking["booking_reference"] = ref_num
                    booking["confirmed"] = True
                    print(f"[BOOKING] ✅ SUCCESS (retry) | Ref: {ref_num}", flush=True)
                    confirm_reply = f"Your booking is confirmed. Our driver will contact you shortly. Thank you for choosing us."
                    speak_text(response, confirm_reply, call_sid, ctx["language"])
                else:
                    confirm_reply = "Our team will call you back shortly to finalize your booking."
                    booking["confirmed"] = True
                    print(f"[BOOKING] ⚠️ Offline | Phone: {booking['confirmed_contact_number']}", flush=True)
                    speak_text(response, confirm_reply, call_sid, ctx["language"])
                    offline_bookings.append(booking_payload)
            
            response.hangup()
        else:
            reply_en = "No problem. What would you like to change?"
            speak_text(response, reply_en, call_sid, ctx["language"])
            response.gather(num_digits=0, action=f"/handle?call_sid={call_sid}", method='POST', input='speech', speech_timeout=3, max_speech_time=30, timeout=30, enhanced=True)
    
    else:
        final_reply = "Thank you for choosing Star Skyline Limousine!"
        speak_text(response, final_reply, call_sid, ctx["language"])
        response.hangup()
    
    return str(response)

@app.route('/public/<filename>', methods=['GET'])
def serve_tts(filename):
    try:
        return send_file(f'public/{filename}', mimetype='audio/mpeg')
    except:
        return "File not found", 404

if __name__ == '__main__':
    init_db_pool()
    threading.Thread(target=prewarm_elevenlabs_tts, daemon=True).start()
    print("Starting Bareerah (Professional Booking Assistant)...", flush=True)
    app.run(host='0.0.0.0', port=5000, debug=False)
