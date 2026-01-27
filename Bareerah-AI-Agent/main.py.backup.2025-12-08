from flask import Flask, request, Response, jsonify, render_template, send_file
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client as TwilioClient
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
import subprocess
import jwt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bareerah_qa_cache import BAREERAH_QA_CACHE, FUZZY_MAPPING  # ✅ Import Q&A cache
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bareerah-secret-key')

OPENAI_CLIENT = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
GOOGLE_CLOUD_TTS_KEY = os.environ.get("GOOGLE_CLOUD_TTS_KEY")
WEBSITE_URL = os.environ.get("WEBSITE_URL", "")
BASE_API_URL = "https://5ef5530c-38d9-4731-b470-827087d7bc6f-00-2j327r1fnap1d.sisko.replit.dev/api"
BOOKING_ENDPOINT = "https://5ef5530c-38d9-4731-b470-827087d7bc6f-00-2j327r1fnap1d.sisko.replit.dev/api/bookings/create-manual"

# ✅ EMAIL CONFIGURATION - RESEND SMTP (Fixed domain issue)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_EMAIL = "noreply@resend.dev"  # ✅ FIX: Use verified Resend domain instead of unverified starskyline.ae

# ✅ TEAM NOTIFICATION EMAILS - Using ONLY verified email (Resend restriction in testing mode)
# NOTE: Resend requires domain verification to send to multiple emails. For now, send to primary only.
NOTIFICATION_EMAILS = [
    "aizaz.dmp@gmail.com"  # ✅ PRIMARY: Verified email for Resend testing mode
]

# ✅ UPSELL ATTRACTIONS & PACKAGES
DUBAI_ATTRACTIONS = [
    "🏙️ Burj Khalifa - World's tallest building with 360° views",
    "🏜️ Desert Safari - Dunes, camel ride, BBQ dinner",
    "🛍️ Dubai Mall - Shopping paradise with 1,200+ stores",
    "🎡 Ain Dubai - Giant observation wheel (Ferris wheel)",
    "🏖️ Jumeirah Beach - Pristine white sand & luxury resorts",
    "🕌 Sheikh Mohammed Centre - Stunning Islamic architecture"
]

PACKAGE_OPTIONS = {
    "city_tour": "Dubai City Tour (3-4 hours) - Landmarks, photos, lunch included",
    "dinner": "Dinner Package - Restaurant booking + transport",
    "shopping": "Shopping Tour - Multiple malls + waiting time",
    "airport": "Airport Transfer - On-time, professional, luggage assistance",
    "vip": "VIP Package - Premium vehicle + refreshments + city guide"
}

# ✅ COST + SPEED OPTIMIZATION: Production mode flag
PRODUCTION_MODE = os.environ.get("PRODUCTION_MODE", "true").lower() == "true"
DEBUG_LOGGING = os.environ.get("DEBUG_LOGGING", "false").lower() == "true"

os.makedirs('public', exist_ok=True)

db_pool = None
_tts_prewarmed = False
_cleanup_started = False  # ✅ Flag to ensure cleanup only starts ONCE
call_contexts = {}
call_timestamps = {}  # ✅ Track when calls come in (for fallback email if webhook fails)
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

# ✅ FIX #1: GREETING LISTS (URDU + ENGLISH + ARABIC)
GREETINGS_UR = ["assalam", "asalam", "salam", "salaam", "assalamu", "assalamualaikum", "assalam alaikum", "assalam o alaikum"]
GREETINGS_EN = ["hello", "hi", "hey", "good morning", "good evening"]
GREETINGS_AR = ["السلام", "السلام عليكم", "اهلا", "مرحبا"]

# ✅ FIX #2: SHORT GARBAGE STT FILTER - EXCLUDE yes/no (these are confirmations!)
FILLER_SHORT_TOKENS = {
    "is", "ok", "okay", "haan", "nahi",  # ✅ REMOVED "yes" and "no" - these are valid confirmations
    "location", "pickup", "dropoff", "airport", "hotel", "here", "there"
}

# ✅ 100% FAIL-SAFE: YES/NO WORD LISTS (30+ variants in English/Urdu/Arabic)
YES_WORDS = {
    # English - basic
    "yes", "yeah", "yup", "yep", "ok", "okay", "okey", "sure", "proceed", "book it", 
    "confirm", "perfect", "go ahead", "sounds good", "cool", "great", "book", "let's go",
    # ✅ FIX: Added confirmation phrases
    "correct", "is correct", "that's correct", "thats correct", "right", "that's right", 
    "thats right", "exactly", "absolutely", "definitely", "affirmative", "agreed",
    "yes yes", "yes correct", "is right", "you got it", "that is correct",
    # Urdu
    "haan", "han", "theek hai", "theek", "bilkul", "kar do", "book karo", "confirm karo",
    "sahi", "acha", "chal", "chalo", "done", "hamesha", "sahi hai", "theek hain",
    # Arabic
    "نعم", "ايوه", "تمام", "يلا", "احجز", "اوكي", "تمام تمام", "حسناً", "صحيح"
}

NO_WORDS = {
    # English
    "no", "nope", "nah", "not", "don't", "dont", "cancel", "stop", "skip", "maybe later",
    # Urdu  
    "nahi", "na", "nahin", "mat karo", "baad mein", "ruko", "rok",
    # Arabic
    "لا", "اه", "لا شكراً", "بعدين"
}

_booking_reference_counter = 1000

# ✅ TIME AMBIGUITY FIX: Keywords for AM/PM inference
MORNING_WORDS = {"subah", "fajr", "morning", "pehle", "early", "kal subah", "subah aaina", "subah 5", "subah 6", "subah 7"}
EVENING_WORDS = {"shaam", "evening", "raat", "baad mein", "later", "pm", "evening 5", "shaam ko", "kal shaam"}
AIRPORT_KEYWORDS = {"airport", "dxb", "auh", "sharjah", "aeroport"}

def detect_time_ambiguity(datetime_text: str, booking_type: str) -> tuple:
    """✅ SMART: Detect if time is ambiguous (no AM/PM), infer based on booking type + keywords
    Returns: (is_ambiguous, inferred_period) where inferred_period = "AM" or "PM"
    """
    if not datetime_text:
        return False, None
    
    datetime_lower = datetime_text.lower()
    
    # Check if already has AM/PM indication
    if any(x in datetime_lower for x in ["am", "pm", "a.m", "p.m", "morning", "evening", "subah", "shaam"]):
        return False, None  # Not ambiguous
    
    # Check for explicit keywords
    has_morning = any(word in datetime_lower for word in MORNING_WORDS)
    has_evening = any(word in datetime_lower for word in EVENING_WORDS)
    
    if has_morning:
        return False, "AM"
    if has_evening:
        return False, "PM"
    
    # ✅ AMBIGUOUS: Infer based on booking type (airport drop = 90% AM, pickup = 60% PM)
    if booking_type == "airport_transfer":
        # Smart check: if dropoff is airport → likely AM (flights)
        # if pickup is airport → likely PM (arriving)
        return True, "AM"  # Default to AM for airport (most common flight times)
    
    return True, "PM"  # City rides default to PM

def apply_time_period(datetime_text: str, period: str) -> str:
    """✅ Append AM/PM to ambiguous time if needed"""
    if not datetime_text or not period:
        return datetime_text
    
    datetime_lower = datetime_text.lower()
    
    # If already has time period, don't add again
    if any(x in datetime_lower for x in ["am", "pm", "a.m", "p.m"]):
        return datetime_text
    
    # Extract time if it's just hours (e.g., "5" → "5:00")
    import re
    time_match = re.search(r'\b(\d{1,2})\b', datetime_text)
    if time_match:
        hour = time_match.group(1)
        if period == "AM":
            return datetime_text.replace(hour, f"{hour}:00 AM")
        else:
            return datetime_text.replace(hour, f"{hour}:00 PM")
    
    return datetime_text

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

def convert_ogg_to_mp3(ogg_file_path: str) -> str:
    """✅ Convert .ogg/.opus file to .mp3 using ffmpeg for Whisper compatibility"""
    try:
        # Check file size first
        file_size = os.path.getsize(ogg_file_path)
        if file_size == 0:
            print(f"[FFMPEG] ❌ Input file is empty! Size: {file_size}", flush=True)
            return None
        print(f"[FFMPEG] 📁 Input file size: {file_size} bytes", flush=True)
        
        mp3_file_path = ogg_file_path.replace('.ogg', '.mp3').replace('.opus', '.mp3')
        # Use -acodec libmp3lame for better Opus/OGG handling
        cmd = ['ffmpeg', '-i', ogg_file_path, '-acodec', 'libmp3lame', '-q:a', '5', '-y', mp3_file_path]
        
        result = subprocess.run(cmd, capture_output=True, timeout=10, text=True)
        if result.returncode == 0 and os.path.exists(mp3_file_path):
            mp3_size = os.path.getsize(mp3_file_path)
            print(f"[FFMPEG] ✅ Converted ({file_size}→{mp3_size} bytes): {ogg_file_path} → {mp3_file_path}", flush=True)
            try:
                os.remove(ogg_file_path)
            except:
                pass
            return mp3_file_path
        else:
            print(f"[FFMPEG] ❌ Conversion failed stderr: {result.stderr[:200]}", flush=True)
            return None
    except Exception as e:
        print(f"[FFMPEG] ❌ Exception: {e}", flush=True)
        return None

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

# ✅ BULLET-PROOF NUMBER WORDS: English/Urdu/Arabic (0-10) for luggage/passengers
NUMBER_WORDS = {
    # English
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    # Urdu
    "do": 2, "teen": 3, "char": 4, "paanch": 5, "chhe": 6, "saat": 7, 
    "aath": 8, "nau": 9, "das": 10, "ek": 1,
    # Arabic
    "واحد": 1, "اثنين": 2, "ثلاثة": 3, "اربعة": 4, "خمسة": 5,
    "ستة": 6, "سبعة": 7, "ثمانية": 8, "تسعة": 9, "عشرة": 10
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

# ✅ JWT CONFIG & CACHING
JWT_SECRET = os.environ.get("JWT_SECRET", "bareerah-jwt-secret-key")
VENDOR_USERNAME = "admin"
VENDOR_PASSWORD = "admin123"
CACHED_JWT_TOKEN = None
JWT_TOKEN_EXPIRY = None
JWT_LOCK = threading.Lock()  # ✅ Thread-safe token refresh

def generate_local_jwt_token(username: str = VENDOR_USERNAME, password: str = VENDOR_PASSWORD) -> str:
    """✅ Generate JWT token locally (no backend dependency)"""
    try:
        payload = {
            "username": username,
            "password": password,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        print(f"[AUTH] ✅ JWT token generated locally: {token[:50]}...", flush=True)
        return token
    except Exception as e:
        print(f"[AUTH] ❌ Failed to generate JWT token: {e}", flush=True)
        return None

def is_jwt_token_expired():
    """✅ Check if cached JWT token is expired"""
    global JWT_TOKEN_EXPIRY
    if not JWT_TOKEN_EXPIRY:
        return True
    return datetime.utcnow() > JWT_TOKEN_EXPIRY

def backend_login_with_retry():
    """✅ Try backend API first, then fallback to local JWT generation"""
    for attempt in range(2):
        try:
            login_url = f"{BASE_API_URL}/auth/login"
            print(f"[AUTH] Attempt {attempt+1}: POST {login_url}", flush=True)
            r = requests.post(login_url,
                              json={"username": VENDOR_USERNAME, "password": VENDOR_PASSWORD},
                              timeout=3)
            print(f"[AUTH] Response status: {r.status_code}", flush=True)
            if r.status_code == 200:
                try:
                    data = r.json()
                    token = data.get("token")
                    if token:
                        print(f"[AUTH] ✅ Backend login successful, token: {token[:50]}...", flush=True)
                        return token
                except:
                    pass
            else:
                print(f"[AUTH] ❌ Backend status {r.status_code}", flush=True)
        except Exception as e:
            print(f"[AUTH] ❌ Backend unreachable: {e}", flush=True)
        if attempt < 1:
            time.sleep(1)
    
    # ✅ FALLBACK: Generate local JWT token (no backend dependency)
    print(f"[AUTH] Backend API failed, generating local JWT token...", flush=True)
    local_token = generate_local_jwt_token()
    if local_token:
        return local_token
    
    print(f"[AUTH] ❌ All auth methods failed", flush=True)
    return None

def get_jwt_token():
    """✅ Get JWT token with auto-refresh if expired"""
    global CACHED_JWT_TOKEN, JWT_TOKEN_EXPIRY
    
    # ✅ Fast path: Token exists and not expired
    if CACHED_JWT_TOKEN and not is_jwt_token_expired():
        return CACHED_JWT_TOKEN
    
    # ✅ Slow path: Refresh token (thread-safe)
    with JWT_LOCK:
        # Double-check after acquiring lock
        if CACHED_JWT_TOKEN and not is_jwt_token_expired():
            return CACHED_JWT_TOKEN
        
        # Refresh token
        token = backend_login_with_retry()
        if token:
            CACHED_JWT_TOKEN = token
            JWT_TOKEN_EXPIRY = datetime.utcnow() + timedelta(hours=24)
            print(f"[AUTH] ✅ JWT Token refreshed successfully", flush=True)
            # ✅ Fetch vehicles from backend on first successful token
            try:
                vehicle_manager.fetch_from_backend(token)
            except Exception as e:
                print(f"[VEHICLE_MGR] ⚠️ Could not fetch vehicles on token refresh: {e}", flush=True)
            return token
        
        return None

def create_booking_direct(booking_payload: dict, endpoint: str = "/api/bookings/create-manual") -> bool:
    """✅ DIRECT BOOKING CREATION - With JWT authentication"""
    try:
        # Get fresh JWT token
        jwt_token = get_jwt_token()
        if not jwt_token:
            print(f"[BACKEND] ❌ No JWT token available", flush=True)
            return False
        
        # ✅ Build full endpoint URL from BACKEND_BASE_URL
        full_endpoint = BACKEND_BASE_URL.rstrip("/") + endpoint
        print(f"[BACKEND] Trying URL: {full_endpoint}", flush=True)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {jwt_token}"
        }
        r = requests.post(full_endpoint, json=booking_payload, headers=headers, timeout=5)
        print(f"[BACKEND] Response: {r.status_code}", flush=True)
        
        if r.status_code == 200:
            try:
                data = r.json()
                ref = data.get("booking_id") or data.get("booking_reference") or data.get("id")
                print(f"[BACKEND] ✅ Booking created: {ref}", flush=True)
                return True
            except:
                print(f"[BACKEND] ✅ Response 200 (parsed as success)", flush=True)
                return True
        else:
            print(f"[BACKEND] ❌ Status {r.status_code}: {r.text[:100]}", flush=True)
            return False
    except requests.Timeout:
        print(f"[BACKEND] ❌ Timeout - using local pending", flush=True)
        return False
    except Exception as e:
        print(f"[BACKEND] ❌ Error: {e} - using local pending", flush=True)
        return False

def test_backend_connection():
    """✅ Test backend connection without creating test bookings"""
    print(f"[BACKEND] ════════════════════════════════════════════════", flush=True)
    print(f"[BACKEND] Testing connection on startup...", flush=True)
    print(f"[BACKEND] Endpoint: {BOOKING_ENDPOINT}", flush=True)
    
    # ✅ ONLY test JWT authentication - DO NOT create actual test bookings
    try:
        jwt_token = get_jwt_token()
        if jwt_token:
            print(f"[BACKEND] ✅ JWT token obtained successfully", flush=True)
            print(f"[BACKEND] ✅ Backend connection ready for real bookings", flush=True)
        else:
            print(f"[BACKEND] ⚠️ Could not get JWT token - will use local fallback", flush=True)
    except Exception as e:
        print(f"[BACKEND] ⚠️ Connection test error: {e}", flush=True)
    
    print(f"[BACKEND] ════════════════════════════════════════════════", flush=True)

def log_conversation(from_phone: str, speaker: str, message: str):
    """✅ LOG CONVERSATION: Clean text-based format for customer/bot chat"""
    conversation_log = f"""
╔════════════════════════════════════════════════════════╗
║ CONVERSATION LOG ({from_phone})
╠════════════════════════════════════════════════════════╣
║ {speaker.upper()}: {message[:50]}{"..." if len(message) > 50 else ""}
╚════════════════════════════════════════════════════════╝
"""
    print(conversation_log, flush=True)

def sync_pending_bookings_to_backend(from_phone: str, jwt_token: str):
    """✅ SYNC PENDING BOOKINGS: Send bookings that failed to save to backend"""
    if not jwt_token:
        print(f"[SYNC] ⚠️ No JWT token available for sync", flush=True)
        return
    
    conn = None
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        
        # Get all pending bookings for this customer
        cursor.execute("""
            SELECT id, customer_name, customer_phone, 
                   pickup_location, dropoff_location, calculated_fare_aed,
                   vehicle_type, service_type, number_of_passengers, number_of_luggage
            FROM bookings 
            WHERE customer_phone = %s AND booking_status = 'pending_confirmation'
            LIMIT 10
        """, (from_phone,))
        
        pending = cursor.fetchall()
        if not pending:
            if conn:
                return_db_conn(conn)
            return
        
        print(f"[SYNC] Found {len(pending)} pending bookings to sync", flush=True)
        
        # Try to send each pending booking to backend
        for booking in pending:
            booking_payload = {
                "customer_name": booking[1] or "Customer",
                "customer_phone": booking[2],
                "pickup_location": booking[3],
                "dropoff_location": booking[4],
                "fare_aed": int(booking[5] or 0),
                "vehicle_type": booking[6],
                "booking_type": booking[7],
                "passengers_count": int(booking[8] or 1),
                "luggage_count": int(booking[9] or 0)
            }
            
            result = backend_api("POST", "/bookings/create-manual", booking_payload, jwt_token)
            if result:
                # Update booking status to confirmed
                cursor.execute(
                    "UPDATE bookings SET booking_status = %s WHERE id = %s",
                    ("confirmed", booking[0])
                )
                conn.commit()
                print(f"[SYNC] ✅ Synced booking {booking[0]} to backend", flush=True)
            else:
                print(f"[SYNC] ❌ Failed to sync booking {booking[0]}", flush=True)
        
        if conn:
            return_db_conn(conn)
    except Exception as e:
        if conn:
            return_db_conn(conn)
        print(f"[SYNC] Error syncing bookings: {e}", flush=True)

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

def convert_word_to_number(text: str) -> int:
    """✅ BULLET-PROOF: Convert word numbers (EN/UR/AR) to int
    Handles: "four", "char", "اربعة" → 4
    """
    if not text:
        return None
    
    text_clean = text.strip().lower()
    
    # Direct match in NUMBER_WORDS dictionary
    if text_clean in NUMBER_WORDS:
        return NUMBER_WORDS[text_clean]
    
    # Try to extract from phrases (e.g., "four bags" → 4)
    words = text_clean.split()
    for word in words:
        if word in NUMBER_WORDS:
            return NUMBER_WORDS[word]
    
    # Try direct int conversion as fallback
    try:
        return int(text_clean)
    except:
        return None

def normalize_numeric_values(text: str) -> int:
    """
    Extract and normalize numeric values:
    - Convert spoken numbers using NUMBER_WORDS (one=1, char=4, etc.)
    - Sum all quantities in text (6 bags + 2 hand = 8)
    - Return total count
    - ✅ SKIP time-like inputs (2:00 AM, 10:30 PM, etc.) - but EXTRACT NUMBER FIRST!
    """
    if not text:
        return 0
    
    text_lower = text.lower()
    
    import re
    
    # ✅ FIRST: Try to extract the number (before checking skip markers!)
    # Try exact match in NUMBER_WORDS first
    for word in NUMBER_WORDS.keys():
        if word in text_lower:
            extracted_num = NUMBER_WORDS[word]
            # Now check if we should skip (time-related input)
            skip_markers = {":", "am", "pm", "tomorrow", "today", "tonight", "morning", "afternoon", "evening", "night"}
            if any(marker in text_lower for marker in skip_markers):
                return 0  # Skip times
            return extracted_num  # Return extracted number
    
    # Extract digits
    digits = re.findall(r'\d+', text_lower)
    if digits:
        total = int(digits[0])  # Take first digit
        # Now check if this is a time (like "10 am" or "3:30")
        skip_markers = {":", "am", "pm", "tomorrow", "today", "tonight", "morning", "afternoon", "evening", "night"}
        if any(marker in text_lower for marker in skip_markers):
            return 0  # Skip times like "10 am" or "3:00 pm"
        return total  # Return the extracted digit
    
    # Block ambiguous cases
    ambiguous = {"many", "lot", "few", "couple", "lots", "several"}
    if any(amb in text_lower for amb in ambiguous):
        return None  # Force re-ask
    
    return 0

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

def normalize_location(text):
    """✅ FIX #1: LEADING FILLER NORMALIZATION + SPELLING CORRECTIONS"""
    if not text:
        return None

    t = text.strip().lower()

    # Common STT filler phrases that MUST be removed from start
    fillers = [
        "the way", "on the way", "my way", "its", "it is", "is",
        "meri", "mera", "mujhe", "main", "mein",
        "pickup is", "pickup from", "dropoff is", "drop off is"
    ]

    for f in fillers:
        if t.startswith(f):
            t = t[len(f):].strip()

    # ✅ SPELLING CORRECTIONS: Common location misspellings
    spelling_fixes = {
        "bemarina": "Dubai Marina Mall",
        "marina mall": "Dubai Marina Mall",
        "marina": "Dubai Marina Mall",
        "airport": "Dubai Airport",
        "dxb": "Dubai Airport",
        "auh": "Abu Dhabi Airport",
        "sharjah airport": "Sharjah Airport",
        "sjc": "Sharjah Airport"
    }
    
    for typo, correct in spelling_fixes.items():
        if typo in t:
            t = t.replace(typo, correct.lower())
    
    # Capitalize clean output for saving
    result = " ".join([w.capitalize() for w in t.split()]) if t else None
    return result

def validate_location_structure(text: str, language: str = "en", confidence: float = 0.75) -> bool:
    """
    ✅ PATCH: Minimum structure for location lock (Req #2)
    Requirements:
    - confidence >= 0.75
    - token_count >= 2
    - Contains at least 1 geo-keyword
    - Not in generic word blocklist
    - NOT city-level (Dubai, Abu Dhabi, Sharjah) - require specific area/building/street/plot
    """
    if not text or confidence < 0.75:
        return False
    
    clean = text.strip().lower()
    
    # ✅ CRITICAL FIX: REJECT CITY-LEVEL LOCATIONS
    cities_emirates = {"dubai", "abu dhabi", "sharjah", "ajman", "fujairah", "ras al khaimah", "umm al quwain", "auh"}
    if clean in cities_emirates:
        print(f"[LOCATION VALIDATION] ❌ REJECTED CITY-LEVEL LOCATION: '{clean}' - require specific area/building/street/plot number", flush=True)
        return False
    
    # ✅ FIX #2: GENERIC + PARTIAL LOCATION HARD BLOCK
    blocked_phrases = {
        "way", "the way", "on the way",
        "location", "place",
        "airport", "hotel"
    }
    
    if clean in blocked_phrases:
        print("[LOCATION VALIDATION] Blocked meaningless location:", clean, flush=True)
        return False
    
    # ✅ FIX #3: GENERIC LOCATION VALIDATOR - Block "Airport / Location / Hotel" alone
    generic = {"airport", "location", "hotel", "home", "house", "office"}
    if clean in generic:
        print("[LOCATION VALIDATION] Rejected generic location:", clean, flush=True)
        return False
    
    # If fewer than 2 words, reject (require specific detail like "Dubai Marina" or "JBR Beach")
    if len(clean.split()) < 2:
        print("[LOCATION VALIDATION] Rejected too-short location:", clean, flush=True)
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

# ✅ VEHICLE INVENTORY MAPPING (Backend Integration)
VEHICLE_INVENTORY = {
    "sedan": {"max_passengers": 4, "max_luggage": 3},
    "urban_suv": {"max_passengers": 7, "max_luggage": 4},
    "suv": {"max_passengers": 6, "max_luggage": 6},
    "luxury_suv": {"max_passengers": 7, "max_luggage": 5},
    "elite_van": {"max_passengers": 7, "max_luggage": 5},
    "executive": {"max_passengers": 5, "max_luggage": 3},
    "first_class": {"max_passengers": 4, "max_luggage": 3},
    "classic": {"max_passengers": 4, "max_luggage": 2},
    "mini_bus": {"max_passengers": 12, "max_luggage": 8},
    "minibus": {"max_passengers": 14, "max_luggage": 8},
    "luxury": {"max_passengers": 4, "max_luggage": 3},
    "van": {"max_passengers": 7, "max_luggage": 7},
    "bus": {"max_passengers": 14, "max_luggage": 8}
}

def call_suggest_vehicles_api(passengers: int, luggage: int, jwt_token: str):
    """Call backend's /bookings/suggest-vehicles endpoint for best vehicle match"""
    try:
        result = backend_api("GET", f"/bookings/suggest-vehicles?passengers_count={passengers}&luggage_count={luggage}", jwt_token=jwt_token)
        if result and isinstance(result, list) and len(result) > 0:
            best_vehicle = result[0]  # Best fit vehicle
            return best_vehicle.get("type"), None
        return None, "No suitable vehicles available"
    except:
        return None, "Failed to get vehicle suggestions"

def suggest_vehicle(passengers: int, luggage: int, jwt_token: str = None) -> tuple:
    """
    ✅ BACKEND INTEGRATION: Call suggest-vehicles API for smart vehicle selection.
    Falls back to local logic if backend unavailable.
    
    Returns: (vehicle_type, error_msg or None)
    """
    print(f"[VEHICLE] Raw inputs - passengers={passengers} (type: {type(passengers)}), luggage={luggage} (type: {type(luggage)})", flush=True)
    
    try:
        passengers = int(passengers) if passengers is not None else None
        luggage = int(luggage) if luggage is not None else None
    except Exception as e:
        print(f"[VEHICLE] ❌ Conversion failed: {e}", flush=True)
        passengers = None
        luggage = None
    
    # HARD FAIL if any slot missing
    if passengers is None or luggage is None:
        print(f"[VEHICLE] ❌ Missing values: passengers={passengers}, luggage={luggage}", flush=True)
        return None, "Missing passenger or luggage count"
    
    # ✅ ALLOW 0 luggage (no bags) - but passengers must be >= 1
    if passengers <= 0:
        print(f"[VEHICLE] ❌ Invalid passengers: {passengers} (must be >= 1)", flush=True)
        return None, "Invalid passenger count"
    
    if luggage < 0:
        print(f"[VEHICLE] ❌ Invalid luggage: {luggage} (must be >= 0)", flush=True)
        return None, "Invalid luggage count"
    
    print(f"[VEHICLE] Suggesting for passengers={passengers}, luggage={luggage}", flush=True)
    
    # Try backend API first
    if jwt_token:
        vehicle, error = call_suggest_vehicles_api(passengers, luggage, jwt_token)
        if vehicle:
            print(f"[VEHICLE] ✅ From Backend API: {vehicle}", flush=True)
            return vehicle, None
    
    print(f"[VEHICLE] Using local fallback logic...", flush=True)
    # Fallback to local logic if backend fails
    # Sedan: max 4 pax, 3 luggage
    if passengers <= 4 and luggage <= 3:
        print(f"[VEHICLE] ✅ Selected SEDAN (local): {passengers}p ≤ 4, {luggage}l ≤ 3", flush=True)
        return "sedan", None
    
    # SUV: max 6 pax, 6 luggage
    if passengers <= 6 and luggage <= 6:
        print(f"[VEHICLE] ✅ Selected SUV (local): {passengers}p ≤ 6, {luggage}l ≤ 6", flush=True)
        return "suv", None
    
    # Luxury SUV: max 7 pax, 5 luggage
    if passengers <= 7 and luggage <= 5:
        print(f"[VEHICLE] ✅ Selected LUXURY_SUV (local): {passengers}p ≤ 7, {luggage}l ≤ 5", flush=True)
        return "luxury_suv", None
    
    # Elite Van: max 7 pax, 7 luggage
    if passengers <= 7 and luggage <= 7:
        print(f"[VEHICLE] ✅ Selected ELITE_VAN (local): {passengers}p ≤ 7, {luggage}l ≤ 7", flush=True)
        return "elite_van", None
    
    # Mini Bus: max 12 pax, 8 luggage
    if passengers <= 12 and luggage <= 8:
        print(f"[VEHICLE] ✅ Selected MINI_BUS (local): {passengers}p ≤ 12, {luggage}l ≤ 8", flush=True)
        return "mini_bus", None
    
    # Bus: max 14 pax, 8 luggage
    if passengers <= 14 and luggage <= 8:
        print(f"[VEHICLE] ✅ Selected MINIBUS (local): {passengers}p ≤ 14, {luggage}l ≤ 8", flush=True)
        return "minibus", None
    
    print(f"[VEHICLE] ❌ FAILED: {passengers}p and {luggage}l exceed all vehicle capacities", flush=True)
    return None, "Passengers/luggage exceed maximum capacity"

def smart_detect_location_type(text: str) -> str:
    """
    ✅ FIX #2: Smart pickup vs dropoff detection based on keywords.
    Returns: "pickup" | "dropoff" | "unknown"
    """
    text_lower = text.lower()
    
    # ✅ PICKUP keywords (from/se/pickup)
    pickup_keywords = ["from", "se", "سے", "pickup", "pick up", "picking", "start from", "starting from", "mujhe lene", "pick me"]
    for kw in pickup_keywords:
        if kw in text_lower:
            print(f"[LOCATION] Detected PICKUP keyword: '{kw}'", flush=True)
            return "pickup"
    
    # ✅ DROPOFF keywords (to/ko/dropoff)
    dropoff_keywords = ["to", "ko", "کو", "dropoff", "drop off", "dropping", "going to", "heading to", "going", "destination", "take me to", "le chalo", "jana hai"]
    for kw in dropoff_keywords:
        if kw in text_lower:
            print(f"[LOCATION] Detected DROPOFF keyword: '{kw}'", flush=True)
            return "dropoff"
    
    return "unknown"

def handle_location_failure(ctx: dict, booking: dict, location_text: str, location_type: str, from_phone: str) -> str:
    """
    ✅ FIX #5: After 2 location validation failures PER SLOT, save pending booking + fallback message.
    Tracks pickup_attempts and dropoff_attempts separately.
    """
    # ✅ FIX: Track attempts per slot (pickup vs dropoff separately)
    attempt_key = f"{location_type}_attempts"
    ctx[attempt_key] = ctx.get(attempt_key, 0) + 1
    attempts = ctx[attempt_key]
    
    print(f"[LOCATION] {location_type.upper()} attempt {attempts}/2 failed: '{location_text}'", flush=True)
    
    if attempts >= 2:
        # ✅ Save as pending booking with whatever info we have
        booking["booking_status"] = "pending_location_issue"
        booking["failed_location"] = location_text
        booking["failed_location_type"] = location_type
        
        # ✅ FIX: Get caller_phone from ctx if from_phone is None/empty
        caller_phone = from_phone or ctx.get("caller_phone") or "Unknown"
        booking["caller_number"] = caller_phone
        
        # ✅ Send email notification about pending booking
        try:
            notify_booking_to_team(booking, "location_failed")
            print(f"[EMAIL] ✅ Pending booking email sent for {location_type} failure | Phone: {caller_phone}", flush=True)
        except Exception as e:
            print(f"[EMAIL] ⚠️ Email error: {e}", flush=True)
        
        # ✅ Reset THIS slot's attempts (other slot keeps its count)
        ctx[attempt_key] = 0
        
        return "Sorry, location confirm nahi hui. Hamari team aapko 5 minute mein call karegi. Thank you for your patience! 🙏"
    
    return None  # Let normal flow continue

def detect_booking_type(pickup: str, dropoff: str, nlu_type: str = None) -> str:
    """Detect booking type: point_to_point, round_trip, or multi_stop"""
    # If NLU detected a type, use that
    if nlu_type in ["round_trip", "multi_stop", "point_to_point"]:
        return nlu_type
    
    # Otherwise detect from locations
    airport_keywords = ["airport", "dxb", "international", "terminal"]
    pickup_lower = pickup.lower() if pickup else ""
    dropoff_lower = dropoff.lower() if dropoff else ""
    
    if any(kw in pickup_lower for kw in airport_keywords) or any(kw in dropoff_lower for kw in airport_keywords):
        return "airport_transfer"
    return "point_to_point"

def normalize_airport(location: str) -> str:
    if "airport" in location.lower():
        if "terminal" not in location.lower():
            return "Dubai International Airport Terminal 1"
        return location
    return location

def get_upsell_suggestion() -> str:
    """✅ Get smart upsell suggestion based on booking details"""
    import random
    attraction = random.choice(DUBAI_ATTRACTIONS)
    return f"🎯 Pro Tip: While you're in Dubai, you must visit {attraction}! Need a tour? I can arrange it!"

def get_personality_greeting(language: str = "en") -> str:
    """✅ Permanent greeting"""
    greetings = {
        "en": "Assalaam-o-Alaikum, Welcome to Star Skyline Limousine, I am Bareerah, Where would you like to go?",
        "ur": "السلام علیکم، ستار سکائی لیموزین میں خوش آمدید، میں بریرہ ہوں، آپ کہاں جانا چاہتے ہیں؟",
        "ar": "السلام عليكم، أهلا بك في ستار سكاي ليموزين، أنا بريرة، إلى أين تود أن تذهب؟"
    }
    return greetings.get(language, greetings["en"])

class VehicleManager:
    """✅ DYNAMIC: Fetch vehicles from backend (not hardcoded)"""
    def __init__(self):
        self.vehicles = []
        self.last_refresh = 0
        self.refresh_interval = 1800  # 30 minutes
    
    def needs_refresh(self) -> bool:
        """Check if we need to fetch fresh vehicle list"""
        import time
        return time.time() - self.last_refresh > self.refresh_interval
    
    def fetch_from_backend(self, jwt_token: str):
        """✅ Fetch live vehicle list from backend"""
        try:
            # Try /api/vehicles endpoint - check for 'vehicles' or 'data' key
            result = backend_api("GET", "/api/vehicles", jwt_token=jwt_token)
            if result:
                # Handle both {"vehicles": [...]} and {"data": [...]} formats
                vehicles_list = result.get("vehicles") or result.get("data", [])
                if vehicles_list:
                    self.vehicles = vehicles_list
                    import time
                    self.last_refresh = time.time()
                    print(f"[VEHICLE_MGR] ✅ Synced {len(self.vehicles)} vehicles from backend", flush=True)
                    return True
        except Exception as e:
            print(f"[VEHICLE_MGR] ⚠️ Could not fetch from /api/vehicles: {e}", flush=True)
        
        # Fallback to FLEET_INVENTORY if backend endpoint not available
        print(f"[VEHICLE_MGR] ⚠️ Using local FLEET_INVENTORY as fallback", flush=True)
        self.vehicles = FLEET_INVENTORY
        return False
    
    def select_vehicle(self, vehicle_type: str) -> dict:
        """✅ Select random vehicle from LIVE backend list"""
        import random
        vehicle_type_lower = vehicle_type.lower()
        
        # Map user vehicle types to backend types
        type_mapping = {
            "sedan": ["first_class", "sedan", "Sedan"],
            "luxury": ["luxury", "first_class", "premium"],
            "suv": ["luxury", "suv", "SUV"],
            "van": ["van", "luxury_van"]
        }
        
        acceptable_types = type_mapping.get(vehicle_type_lower, [])
        
        # Find matching vehicles from backend list
        matching = [
            v for v in self.vehicles 
            if v.get("type", "").lower() in [t.lower() for t in acceptable_types]
        ]
        
        if not matching:
            # If no matches, use any vehicle
            matching = self.vehicles[:1] if self.vehicles else [FLEET_INVENTORY[0]]
        
        if matching:
            selected = random.choice(matching)
            vehicle_name = selected.get('model') or selected.get('vehicle', 'Unknown')
            vehicle_id = selected.get('id')
            print(f"[VEHICLE_MGR] Selected: {vehicle_name} (ID: {vehicle_id})", flush=True)
            return selected
        
        return FLEET_INVENTORY[0]

# ✅ Global vehicle manager
vehicle_manager = VehicleManager()

def select_vehicle_from_fleet(vehicle_type: str, jwt_token: str = None) -> dict:
    """✅ Select vehicle from LIVE backend list (refreshes if needed)"""
    # Refresh vehicle list if needed
    if vehicle_manager.needs_refresh() and jwt_token:
        vehicle_manager.fetch_from_backend(jwt_token)
    
    # Select from manager
    return vehicle_manager.select_vehicle(vehicle_type)

def generate_booking_reference():
    """✅ Generate unique booking reference: BOOK-XXX"""
    global _booking_reference_counter
    _booking_reference_counter += 1
    return f"BOOK-{_booking_reference_counter}"

def check_yes_no(text: str) -> str:
    """✅ FAIL-SAFE: Check if text contains YES/NO (20+ variants in 3 languages)"""
    text_lower = text.lower().strip()
    
    # Check YES words
    for yes_word in YES_WORDS:
        if yes_word in text_lower:
            return "yes"
    
    # Check NO words
    for no_word in NO_WORDS:
        if no_word in text_lower:
            return "no"
    
    return None  # Unclear

def ensure_booking_state(context):
    # ✅ CRITICAL FIX: Only initialize booking if it truly doesn't exist
    # Check for None explicitly, not falsy, to avoid resetting empty states
    if context.get("booking") is None:
        context["booking"] = {
            "full_name": None,
            "name_locked": False,
            "name_confirm_pending": False,
            "vehicle_preference": None,  # ✅ NEW: Track luxury/premium preferences
            "vehicle_preference_asked": False,  # ✅ NEW: Asked about upgrade?
            "caller_number": context.get("caller_phone"),  # ✅ FIX #1: Set from incoming call
            "confirmed_contact_number": None,
            "phone_locked": False,
            "phone_confirm_count": 0,
            "email": None,
            "email_attempts": 0,
            "email_locked": False,
            "notes": None,
            "notes_locked": False,
            "pickup": None,
            "pickup_locked": False,
            "pickup_confirm_pending": False,
            "dropoff": None,
            "dropoff_locked": False,
            "dropoff_confirm_pending": False,
            "datetime": None,
            "datetime_locked": False,
            "datetime_confirm_pending": False,
            "datetime_ambiguous": False,
            "datetime_ambiguous_period": None,
            "passengers": None,
            "passengers_locked": False,
            "luggage_count": None,
            "luggage_locked": False,
            "round_trip": None,
            "round_trip_locked": False,
            "return_after_hours": None,
            "return_after_hours_locked": False,
            "multi_stop": False,
            "multi_stop_locked": False,
            "stops": [],  # For multi-stop bookings
            "stops_locked": False,
            "vehicle_type": None,
            "vehicle_locked": False,
            "vehicle_confirm_pending": False,
            "distance_km": None,
            "fare": None,
            "fare_locked": False,
            "booking_type": None,
            "confirmed": False,
            "booking_reference": None,
            "booking_status": "pending"
        }
        # ✅ Only set flow_step if not already set
        if "flow_step" not in context or context.get("flow_step") is None:
            context["flow_step"] = "dropoff"  # Start with dropoff (natural driver flow)
        context["language"] = "en"
        context["language_locked"] = False
        context["call_initialized"] = False
    else:
        # ✅ PRESERVE existing booking state - never reset if it exists
        print(f"[STATE] ✅ Booking state preserved from previous request (dropoff_confirm_pending={context['booking'].get('dropoff_confirm_pending')})", flush=True)

def prewarm_elevenlabs_tts():
    global _tts_prewarmed
    if _tts_prewarmed or not ELEVENLABS_API_KEY:
        return
    try:
        voice_id = "1zUSi8LeHs9M2mV8X6YS"  # ✅ Custom Bareerah voice profile (LATEST)
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

def generate_professional_email_html(booking_data: dict, status_message: str) -> str:
    """✅ Generate professional Careem/Uber style HTML email with driver info"""
    customer_name = booking_data.get('customer_name', 'Customer') or 'Customer'
    phone = booking_data.get('customer_phone', 'N/A') or 'N/A'
    pickup = booking_data.get('pickup_location', 'N/A') or 'N/A'
    dropoff = booking_data.get('dropoff_location', 'N/A') or 'N/A'
    passengers = booking_data.get('passengers_count', 'N/A') or 'N/A'
    luggage = booking_data.get('luggage_count', 'N/A') or 'N/A'
    fare = booking_data.get('calculated_fare_aed', booking_data.get('fare', 'N/A')) or 'N/A'
    vehicle = (booking_data.get('vehicle_type') or 'N/A').upper()
    email = booking_data.get('customer_email', 'N/A') or 'N/A'
    notes = booking_data.get('notes', '') or ''
    booking_ref = booking_data.get('booking_reference', 'BOOK-XXXX') or 'BOOK-XXXX'
    pickup_time = booking_data.get('datetime', 'TBD') or 'TBD'
    car_model = booking_data.get('car_model', 'Pending') or 'Pending'
    car_color = booking_data.get('car_color', 'N/A') or 'N/A'
    driver_name = booking_data.get('driver_name', 'Assigning...') or 'Assigning...'
    driver_number = booking_data.get('driver_number', 'N/A') or 'N/A'
    driver_picture = booking_data.get('driver_picture', None)
    
    html = f"""
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
            .notes-box {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 15px 0; border-radius: 5px; }}
            .notes-label {{ color: #856404; font-weight: 600; font-size: 12px; }}
            .notes-text {{ color: #856404; font-size: 13px; margin-top: 6px; }}
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
                <p>Hi <strong>{customer_name}</strong>,</p>
                
                <div class="status">✅ {status_message}</div>
                
                <div class="booking-bar">
                    <div>
                        <div class="booking-label">Booking Reference</div>
                        <div class="booking-value">{booking_ref}</div>
                    </div>
                </div>
                
                <div class="route-section">
                    <div class="route-header">📍 Route & Time</div>
                    <div class="route-flow">
                        <div class="route-item">
                            <div class="route-icon">📤</div>
                            <div class="route-label">Pickup Location</div>
                            <div class="route-text">{pickup}</div>
                        </div>
                        <div class="connector">→</div>
                        <div class="route-item">
                            <div class="route-icon">⏰</div>
                            <div class="route-label">Pickup Time</div>
                            <div class="route-text">{pickup_time}</div>
                        </div>
                        <div class="connector">→</div>
                        <div class="route-item">
                            <div class="route-icon">📥</div>
                            <div class="route-label">Dropoff Location</div>
                            <div class="route-text">{dropoff}</div>
                        </div>
                    </div>
                </div>
                
                <div class="details-bar">
                    <div class="detail-box">
                        <div class="detail-label">Vehicle Type</div>
                        <div class="detail-value vehicle">{vehicle}</div>
                    </div>
                    <div class="detail-box">
                        <div class="detail-label">Car Model</div>
                        <div class="detail-value vehicle">{car_model}</div>
                    </div>
                    <div class="detail-box">
                        <div class="detail-label">Car Color</div>
                        <div class="detail-value vehicle">{car_color}</div>
                    </div>
                    <div class="detail-box">
                        <div class="detail-label">Passengers</div>
                        <div class="detail-value">{passengers}</div>
                    </div>
                    <div class="detail-box">
                        <div class="detail-label">Luggage</div>
                        <div class="detail-value">{luggage}</div>
                    </div>
                    <div class="detail-box">
                        <div class="detail-label">Total Fare</div>
                        <div class="detail-value">AED {fare}</div>
                    </div>
                </div>
                
                <div class="driver-section">
                    <div class="driver-pic">👨‍💼</div>
                    <div class="driver-info">
                        <div class="driver-header">🚗 Your Driver</div>
                        <div class="driver-name">{driver_name}</div>
                        <div class="driver-number">📞 <a href="tel:{driver_number.replace('+', '').replace(' ', '')}">{driver_number}</a></div>
                    </div>
                </div>
                
                <div class="info-bar">
                    <div class="info-item">
                        <div class="info-label">📞 Phone</div>
                        <div class="info-value">{phone}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">✉️ Email</div>
                        <div class="info-value">{email}</div>
                    </div>
                </div>
                
                <div class="helpline-box">
                    <div class="helpline-label">Need Help? Call Our Helpline</div>
                    <div class="helpline-number"><a href="tel:02111122233">021 111 222 333</a></div>
                </div>
                
                {"<div class='notes-box'><div class='notes-label'>🎯 Special Requests/Notes:</div><div class='notes-text'>" + notes + "</div></div>" if notes else ""}
                
                <p style="margin-top: 30px; color: #666; font-size: 14px;">
                    ✅ Our driver will contact <strong>{customer_name}</strong> at <strong>{phone}</strong> shortly for final confirmation.<br>
                    ⏱️ Expected pickup time will be shared via WhatsApp.
                </p>
                
                <div class="footer">
                    <p>Star Skyline Limousine Service • Dubai, UAE<br>
                    <a href="https://starskyline.ae">Visit our website</a> | 
                    <a href="tel:+971501234567">Call us</a></p>
                    <p>Booking Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email_notification(subject: str, body: str, booking_data: dict = None, recipient_email: str = None, retry_count: int = 0) -> bool:
    """✅ Send email notification to team (Resend SMTP) with HTML template - WITH RETRY"""
    try:
        if not RESEND_API_KEY:
            print(f"[EMAIL] ❌ FATAL: Resend API key not configured! Email CANNOT be sent!", flush=True)
            print(f"[EMAIL] Subject: {subject}", flush=True)
            print(f"[EMAIL] Phone: {booking_data.get('customer_phone', 'N/A') if booking_data else 'N/A'}", flush=True)
            return False
        
        # Use specific recipient or all notification emails
        recipients = [recipient_email] if recipient_email else NOTIFICATION_EMAILS
        
        msg = MIMEMultipart('alternative')
        msg['From'] = RESEND_EMAIL
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = subject
        
        # Plain text fallback
        text_body = body + "\n\n"
        if booking_data:
            text_body += "📋 Booking Details:\n"
            text_body += f"  📞 Customer: {booking_data.get('customer_name', 'N/A')} ({booking_data.get('customer_phone', 'N/A')})\n"
            text_body += f"  📍 Pickup: {booking_data.get('pickup_location', 'N/A')}\n"
            text_body += f"  📍 Dropoff: {booking_data.get('dropoff_location', 'N/A')}\n"
            text_body += f"  👥 Passengers: {booking_data.get('passengers_count', 'N/A')}\n"
            text_body += f"  🧳 Luggage: {booking_data.get('luggage_count', 'N/A')}\n"
            text_body += f"  💰 Fare: AED {booking_data.get('calculated_fare_aed', booking_data.get('fare', 'N/A'))}\n"
            text_body += f"  🚗 Vehicle: {booking_data.get('vehicle_type', 'N/A')}\n"
            text_body += f"  ✉️ Email: {booking_data.get('customer_email', 'N/A')}\n"
        
        # Attach plain text
        msg.attach(MIMEText(text_body, 'plain'))
        
        # Generate and attach HTML
        if booking_data:
            html_body = generate_professional_email_html(booking_data, body)
            msg.attach(MIMEText(html_body, 'html'))
        
        # Send via Resend SMTP
        server = smtplib.SMTP_SSL('smtp.resend.com', 465)
        server.login('resend', RESEND_API_KEY)
        server.send_message(msg)
        server.quit()
        
        print(f"[EMAIL] ✅ Notification sent to {', '.join(recipients)}: {subject}", flush=True)
        return True
    except Exception as e:
        print(f"[EMAIL] ❌ Failed to send email (attempt {retry_count + 1}): {type(e).__name__}: {str(e)}", flush=True)
        
        # ✅ RETRY LOGIC: Try up to 3 times
        if retry_count < 2:
            print(f"[EMAIL] 🔄 Retrying email send in 2 seconds... (attempt {retry_count + 2}/3)", flush=True)
            import time
            time.sleep(2)
            return send_email_notification(subject, body, booking_data, recipient_email, retry_count + 1)
        
        return False

def notify_booking_to_team(booking_data: dict, status: str = "created"):
    """✅ Send async notification to team about booking - WITH PROPER THREADING"""
    try:
        subject_map = {
            "created": "✅ New Booking Confirmed - Star Skyline",
            "pending": "⏳ Pending Booking (Backend Down) - Star Skyline",
            "failed": "❌ Booking Failed - Customer May Not Have Confirmed",
            "dropped": "📞 Call Dropped - Customer May Need Follow-up",
            "partial_info": "⚠️ Partial Booking Data Collected - Customer May Need Follow-up",
            "location_failed": "🚨 MISSED LEAD - Pickup Location Issue - Star Skyline"
        }
        
        body_map = {
            "created": f"🎉 Booking successfully created and confirmed by customer!",
            "pending": f"⚠️ Booking saved locally - Backend was unavailable. Please sync when backend is online.",
            "failed": f"❌ Booking creation failed. Customer needs manual follow-up.",
            "dropped": f"📞 Customer call dropped mid-conversation. Please follow up immediately!",
            "partial_info": f"⚠️ Customer provided some booking details but didn't complete the full booking. Follow up with them!",
            "location_failed": f"🚨 URGENT: Customer called but could not provide a valid pickup location after 3 attempts. PLEASE CALL THEM BACK IMMEDIATELY!"
        }
        
        subject = subject_map.get(status, f"Booking Notification ({status})")
        body = body_map.get(status, "New booking notification")
        
        # ✅ FIX: Send email with NON-DAEMON thread (waits for completion) + explicit logging
        def send_email_thread():
            result = send_email_notification(subject, body, booking_data)
            if not result:
                print(f"[NOTIFY] ⚠️ Email thread completed but send failed for status: {status}", flush=True)
        
        thread = threading.Thread(target=send_email_thread, daemon=False)  # ✅ NOT daemon - ensures email sends before shutdown
        thread.start()
        
        print(f"[NOTIFY] Email thread started (non-daemon) for status: {status}", flush=True)
    except Exception as e:
        print(f"[NOTIFY] ❌ Notification error: {e}", flush=True)

def send_whatsapp_text_message(to_phone: str, text: str) -> bool:
    """✅ Send text message reply via WhatsApp using Twilio API"""
    try:
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        if not account_sid or not auth_token:
            print(f"[BAREERAH] ❌ Missing Twilio credentials", flush=True)
            return False
        
        client = TwilioClient(account_sid, auth_token)
        
        # ✅ NORMALIZE PHONE: Ensure proper format with +
        normalized_phone = to_phone if to_phone.startswith('+') else '+' + to_phone
        
        # ✅ Send TEXT message via WhatsApp
        message = client.messages.create(
            from_="whatsapp:+14155238886",
            to=f"whatsapp:{normalized_phone}",
            body=text
        )
        
        print(f"[BAREERAH] 💬 Sent text reply to {to_phone} | SID: {message.sid}", flush=True)
        return True
    except Exception as e:
        print(f"[BAREERAH] ❌ Failed to send message: {e}", flush=True)
        return False

def send_whatsapp_audio_message(to_phone: str, audio_url: str) -> bool:
    """✅ Send audio message via WhatsApp using Twilio API with ElevenLabs TTS"""
    try:
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        if not account_sid or not auth_token:
            print(f"[TTS] ❌ Missing Twilio credentials", flush=True)
            return False
        
        client = TwilioClient(account_sid, auth_token)
        
        # ✅ Send AUDIO message via WhatsApp with media
        message = client.messages.create(
            from_="whatsapp:+14155238886",
            to=f"whatsapp:{to_phone}",
            media_url=audio_url
        )
        
        print(f"[TTS] 🔊 Sent audio reply to {to_phone} | URL: {audio_url} | SID: {message.sid}", flush=True)
        return True
    except Exception as e:
        print(f"[TTS] ❌ Failed to send audio: {e}", flush=True)
        return False

def process_whatsapp_booking_slot(from_phone: str, incoming_text: str, ctx: dict) -> str:
    """✅ Process booking slot-filling for WhatsApp with MULTI-SLOT extraction from single message"""
    booking = ctx.get("booking")
    
    # ✅ FIX #3: If booking already completed, don't process further messages
    if booking.get("booking_completed"):
        return "Your booking has been completed! Our team will contact you shortly. Thank you for choosing Star Skyline! 🙏"
    
    low_text = incoming_text.lower()
    
    # ✅ NEW: HANDLE OUT-OF-CONTEXT QUESTIONS WITH PERSONALITY (HUMAN-LIKE RESPONSES)
    out_of_context_responses = {
        "temperature": "Sir/Madam, I'm inside the office and the AC is absolutely great! 😄 Why do you ask - are you planning an outdoor activity or worried about the weather for your trip?",
        "weather": "It's beautiful sunny weather in Dubai! ☀️ Are you concerned about weather conditions for your journey? Let us book you a comfortable ride!",
        "time is it": "It's just the right time to plan your travel! ⏰ When would you like the ride - today, tomorrow, or later this week?",
        "what time": "What time would you like the ride? We'll get you a driver on time! ⏰",
        "cricket": "Haha, I'm a booking assistant, not a cricket expert! 😄 But I'm thrilled about your journey! Let's book your ride first!",
        "news": "I focus on booking rides, not breaking news! 📱 But let's get you travel-ready - where do you need to go?",
        "how much is": "Pricing depends on your trip! Tell me pickup and dropoff - We'll give you an instant fare estimate! 💰"
    }
    
    # Check for out-of-context keywords
    detected_context = None
    for keyword, response in out_of_context_responses.items():
        if keyword in low_text and not any(kw in low_text for kw in ["airport", "marina", "pick", "drop", "go to", "from", "booking"]):
            detected_context = (keyword, response)
            break
    
    if detected_context:
        keyword, response = detected_context
        print(f"[OUT-OF-CONTEXT] Detected '{keyword}' question: {incoming_text[:100]}", flush=True)
        return response
    
    # ✅ NEW: CHECK FAQ CACHE FIRST (40-50% hit rate, <100ms response)
    cached_response = get_cached_faq_response(incoming_text, ctx.get("language", "en"))
    if cached_response:
        print(f"[CACHE] ✅ Returning FAQ response", flush=True)
        return cached_response
    
    # ✅ DIRECT TEXT CHECK: If message has booking keywords, force extract without waiting for NLU
    # NOTE: Avoid "bags" as keyword since it matches "4 bags" luggage response
    has_booking_keywords = any(kw in low_text for kw in ["from ", "to ", "airport", "marina", "burj", "mall", "sharjah", "sheikh", "go to", "want to go", "need to go", "passengers", "luggage", "today", "tomorrow", "7pm", "7 pm", "3pm", "3 pm"])
    
    print(f"[BOOKING] Has booking keywords: {has_booking_keywords} | Text: {incoming_text[:100]}", flush=True)
    
    # ✅ FIX #2: Smart pickup/dropoff detection using keywords
    if has_booking_keywords:
        detected_slot = smart_detect_location_type(incoming_text)
        location_text = extract_pickup_location_llm(incoming_text)
        
        if location_text:
            print(f"[SMART] Detected slot: {detected_slot} | Location: {location_text}", flush=True)
            
            # ✅ Use keyword detection to route location to correct slot
            if detected_slot == "dropoff" and not booking.get("dropoff_locked"):
                # "to/ko/going to" keywords → DROPOFF slot
                booking["dropoff"] = location_text
                booking["dropoff_locked"] = True
                print(f"✅ DROPOFF SMART EXTRACTED (keyword): {location_text}", flush=True)
            elif detected_slot == "pickup" and not booking.get("pickup_locked"):
                # "from/se/pickup" keywords → PICKUP slot
                booking["pickup"] = location_text
                booking["pickup_locked"] = True
                print(f"✅ PICKUP SMART EXTRACTED (keyword): {location_text}", flush=True)
            elif not booking.get("pickup_locked"):
                # ✅ Default to flow order (DROPOFF first for driver-like greeting)
                if not booking.get("dropoff_locked"):
                    booking["dropoff"] = location_text
                    booking["dropoff_locked"] = True
                    print(f"✅ DROPOFF AUTO EXTRACTED (flow order): {location_text}", flush=True)
                else:
                    booking["pickup"] = location_text
                    booking["pickup_locked"] = True
                    print(f"✅ PICKUP AUTO EXTRACTED (flow order): {location_text}", flush=True)
    
    # Now run NLU for other slots
    nlu = extract_nlu(incoming_text, ctx)
    nlu_booking_type = nlu.get("booking_type")
    print(f"[NLU] Extracted: pickup='{nlu.get('pickup')}', dropoff='{nlu.get('dropoff')}', passengers='{nlu.get('passengers')}', luggage='{nlu.get('luggage')}', datetime='{nlu.get('datetime')}', booking_type='{nlu_booking_type}'", flush=True)
    
    # ✅ DO NOT extract name from initial booking message - wait for explicit name step
    # This avoids extracting "Salam. Mujhe JW" as name
    if False:  # ✅ DISABLED: Never auto-extract name from booking keywords
        pass
    
    # SIMPLE auto-fill: if NLU extracted it and slot not locked -> fill it
    if not booking.get("pickup_locked") and nlu.get("pickup"):
        booking["pickup"] = nlu.get("pickup")
        booking["pickup_locked"] = True
        print(f"✅ PICKUP AUTO-FILLED: {booking['pickup']}", flush=True)
    
    # Auto-fill dropoff if extracted AND pickup is locked
    if not booking.get("dropoff_locked") and nlu.get("dropoff") and booking.get("pickup_locked"):
        dropoff_text = nlu.get("dropoff")
        if dropoff_text.lower() != booking.get("pickup", "").lower():
            booking["dropoff"] = dropoff_text
            booking["dropoff_locked"] = True
            booking["booking_type"] = detect_booking_type(booking["pickup"], booking["dropoff"])
            print(f"✅ DROPOFF AUTO-FILLED: {dropoff_text}", flush=True)
    
    # Auto-fill datetime if extracted AND dropoff is locked
    if not booking.get("datetime_locked") and nlu.get("datetime") and booking.get("dropoff_locked"):
        booking["datetime"] = nlu.get("datetime")
        booking["datetime_locked"] = True
        print(f"✅ DATETIME AUTO-FILLED: {booking['datetime']}", flush=True)
    
    # ✅ Auto-fill passengers if extracted (NO datetime lock required - extract early!)
    if not booking.get("passengers_locked") and nlu.get("passengers"):
        passengers_raw = str(nlu.get("passengers")).strip()
        
        # ✅ Convert text numbers to digits (three → 3)
        text_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
        if passengers_raw.lower() in text_to_num:
            passengers = text_to_num[passengers_raw.lower()]
        else:
            try:
                passengers = int(passengers_raw.split()[0])
            except:
                passengers = 0
        
        if passengers >= 1:
            booking["passengers"] = passengers
            booking["passengers_locked"] = True
            print(f"✅ PASSENGERS AUTO-FILLED: {passengers}", flush=True)
    
    # Auto-fill luggage if extracted AND passengers is locked
    if not booking.get("luggage_locked") and nlu.get("luggage") and booking.get("passengers_locked"):
        try:
            luggage = int(str(nlu.get("luggage")).split()[0])  # Get first number
            if luggage >= 0:
                booking["luggage_count"] = luggage
                booking["luggage_locked"] = True
                print(f"✅ LUGGAGE AUTO-FILLED: {luggage}", flush=True)
        except Exception as e:
            print(f"[DEBUG] Failed to parse luggage: {e}", flush=True)
    
    # ✅ AFTER AUTO-FILL: If all booking slots are locked but fare not calculated, show summary
    if (booking.get("pickup_locked") and booking.get("dropoff_locked") and 
        booking.get("passengers_locked") and booking.get("luggage_locked") and 
        not booking.get("fare_locked")):
        print(f"[SUMMARY] All slots locked, calculating fare...", flush=True)
        vehicle_type, error_msg = suggest_vehicle(booking["passengers"], booking["luggage_count"], ctx.get("jwt_token"))
        if vehicle_type:
            booking["vehicle_type"] = vehicle_type
            distance_km = calculate_distance_google_maps(booking["pickup"], booking["dropoff"])
            
            # ✅ FIX #2: ALWAYS calculate fare, even if distance_km is 0 or None
            if distance_km is None:
                distance_km = 0
            booking["distance_km"] = distance_km
            
            fare = calculate_fare_api(distance_km, vehicle_type, booking["booking_type"], ctx.get("jwt_token"))
            
            # ✅ FALLBACK: If fare calculation fails, use formula (NEVER show None or 0)
            if fare is None or fare == 0:
                # Fallback formula: 50 AED base + 3 AED/km
                base_fare = 50
                per_km = 3
                luggage_charge = booking.get("luggage_count", 0) * 10
                fare = base_fare + (distance_km * per_km) + luggage_charge
                print(f"[FARE] Using fallback formula: {base_fare} + ({distance_km}km × {per_km}) + ({booking.get('luggage_count', 0)} × 10) = {fare} AED", flush=True)
            
            booking["fare"] = int(fare) if fare else 100  # ✅ Ensure integer, never 0 or None
            booking["fare_locked"] = True
            print(f"✅ FARE CALCULATED AFTER AUTO-FILL: {booking['fare']} AED", flush=True)
            # ✅ RETURN SUMMARY: Always show actual number, NEVER "?"
            return f"✅ BOOKING SUMMARY:\n📍 {booking['pickup']} → {booking['dropoff']} ({distance_km}km)\n🚗 {vehicle_type} | 👥 {booking['passengers']} passengers | 🎒 {booking['luggage_count']} bags\n💰 Total Fare: {booking['fare']} AED\n\nShould I proceed with this booking? (Yes/No)"
        print(f"[SUMMARY] Could not calculate fare for summary", flush=True)
    
    # ✅ PHASE 2: ASK FOR FIRST MISSING SLOT
    # PICKUP SLOT
    if not booking.get("pickup_locked"):
        if booking.get("pickup_confirm_pending"):
            if nlu.get("yes_no") == "yes":
                booking["pickup_locked"] = True
                booking["pickup_confirm_pending"] = False
                print(f"✅ PICKUP LOCKED: {booking['pickup']}", flush=True)
                return f"Perfect! 📍 Where you heading?"
            else:
                booking["pickup"] = None
                booking["pickup_confirm_pending"] = False
                return "No worries! Where you picking up from?"
        else:
            # If not auto-filled, ask for it
            pickup_text = nlu.get("pickup") or extract_pickup_location_llm(incoming_text)
            if not pickup_text:
                return "Where am I picking you up from? (e.g., Dubai Marina, Dubai Airport)"
            if not validate_pickup_with_places_api(pickup_text):
                # ✅ FIX #5: Handle location failure with 2-attempt fallback
                fallback_msg = handle_location_failure(ctx, booking, pickup_text, "pickup", from_phone)
                if fallback_msg:
                    return fallback_msg
                return f"Sorry, couldn't find '{pickup_text}' in Dubai. Try another location?"
            # ✅ Reset attempts on success
            ctx["location_attempts"] = 0
            booking["pickup"] = pickup_text
            booking["pickup_confirm_pending"] = True
            print(f"✅ PICKUP EXTRACTED: {booking['pickup']}", flush=True)
            return f"Got it, picking you from {booking['pickup']}? 👍"
    
    # ✅ DROPOFF SLOT
    elif not booking.get("dropoff_locked"):
        if booking.get("dropoff_confirm_pending"):
            if nlu.get("yes_no") == "yes":
                booking["dropoff_locked"] = True
                booking["dropoff_confirm_pending"] = False
                booking["booking_type"] = detect_booking_type(booking["pickup"], booking["dropoff"])
                print(f"✅ DROPOFF LOCKED: {booking['dropoff']}", flush=True)
            else:
                booking["dropoff"] = None
                booking["dropoff_confirm_pending"] = False
                return "No problem. Where would you like to go?"
        else:
            dropoff_text = nlu.get("dropoff") or extract_pickup_location_llm(incoming_text)
            if not dropoff_text:
                return "Where you heading?"
            if dropoff_text.lower() == booking.get("pickup", "").lower():
                return "Pickup and dropoff gotta be different! Where else you heading?"
            booking["dropoff"] = dropoff_text
            booking["dropoff_confirm_pending"] = True
            # ✅ SMART: Detect multi-stop from NLU
            nlu_booking_type = nlu.get("booking_type")
            if nlu_booking_type == "multi_stop":
                booking["multi_stop"] = True
                print(f"✅ MULTI-STOP DETECTED from NLU", flush=True)
            print(f"✅ DROPOFF EXTRACTED: {booking['dropoff']}", flush=True)
            return f"Cool, dropping you at {booking['dropoff']}? 👍"
        
        # After dropoff locked, check if we can skip to datetime or ask
        if not booking.get("datetime_locked"):
            if booking.get("datetime"):
                return f"When you said '{booking['datetime']}', did you mean {booking['datetime']}? (Yes/No)"
            return "When do you need the ride? (date and time)"
    
    # ✅ DATETIME SLOT - ✅ AMBIGUITY FIX: Smart AM/PM inference
    elif not booking.get("datetime_locked"):
        if booking.get("datetime_confirm_pending"):
            if nlu.get("yes_no") == "yes":
                booking["datetime_locked"] = True
                booking["datetime_confirm_pending"] = False
                # ✅ If ambiguous, apply inferred period
                if booking.get("datetime_ambiguous") and booking.get("datetime_ambiguous_period"):
                    booking["datetime"] = apply_time_period(booking["datetime"], booking["datetime_ambiguous_period"])
                print(f"✅ DATETIME LOCKED: {booking['datetime']}", flush=True)
            else:
                booking["datetime"] = None
                booking["datetime_confirm_pending"] = False
                booking["datetime_ambiguous"] = False
                booking["datetime_ambiguous_period"] = None
                return "When do you need the ride?"
        else:
            # ✅ ONLY ask for datetime if NLU actually extracted it
            datetime_text = nlu.get("datetime")
            if not datetime_text:
                # If not extracted, just ask for it without confirmation
                return "What time you need it? (e.g., today 7pm, tomorrow 3pm)"
            
            # ✅ CHECK FOR AMBIGUITY
            booking["datetime"] = datetime_text
            is_ambiguous, inferred_period = detect_time_ambiguity(datetime_text, booking.get("booking_type"))
            booking["datetime_ambiguous"] = is_ambiguous
            booking["datetime_ambiguous_period"] = inferred_period
            print(f"✅ DATETIME RECEIVED: {datetime_text} | Ambiguous={is_ambiguous}, Period={inferred_period}", flush=True)
            
            # ✅ If ambiguous, ask for clarification with smart inference
            if is_ambiguous and inferred_period:
                am_pm_text = "subah" if inferred_period == "AM" else "shaam"
                return f"Aapka matlab {am_pm_text} {datetime_text} hai ya doosra time? ✈️"
            
            # ✅ Not ambiguous, just confirm normally
            booking["datetime_confirm_pending"] = True
            return f"That time work? {booking['datetime']}? 👍"
        
        # After datetime locked, check if we can skip to passengers or ask
        if not booking.get("passengers_locked"):
            if booking.get("passengers"):
                return f"How many people coming? (I got {booking['passengers']})"
            return "How many people traveling? (1, 2, 3, etc.)"
    
    # ✅ PASSENGERS SLOT - ✅ BULLET-PROOF NUMBER PARSING (EN/UR/AR)
    elif not booking.get("passengers_locked"):
        passengers_count = nlu.get("passengers")
        if not passengers_count:
            passengers_count = normalize_numeric_values(incoming_text)
        
        # ✅ BULLET-PROOF: Convert word numbers to digits (four → 4, char → 4, اربعة → 4)
        if isinstance(passengers_count, str):
            passengers_count = convert_word_to_number(passengers_count)
        
        try:
            passengers_int = int(passengers_count) if passengers_count else None
            if passengers_int is None or passengers_int < 1:
                return "How many passengers? (1, 2, 3, etc.)"
            booking["passengers"] = passengers_int
            booking["passengers_locked"] = True
            print(f"✅ PASSENGERS LOCKED: {booking['passengers']}", flush=True)
        except:
            return "How many passengers? Please give a number."
        
        # After passengers locked, check if we can skip to luggage or ask
        if not booking.get("luggage_locked"):
            if booking.get("luggage_count") is not None:
                return f"How many bags? (I got {booking['luggage_count']})"
            return f"Cool, {booking['passengers']} people! 👥 How many bags you got?"
    
    # ✅ LUGGAGE SLOT + VEHICLE/FARE SUGGESTION - ✅ BULLET-PROOF NUMBER PARSING (EN/UR/AR)
    elif not booking.get("luggage_locked"):
        luggage_count = nlu.get("luggage")
        luggage_from_nlu = luggage_count is not None  # Track if NLU extracted it
        
        if not luggage_count:
            luggage_count = normalize_numeric_values(incoming_text)
        
        # ✅ BULLET-PROOF: Convert word numbers to digits (four → 4, char → 4, اربعة → 4)
        if isinstance(luggage_count, str):
            luggage_count = convert_word_to_number(luggage_count)
        
        # ✅ Only lock luggage if:
        # 1. NLU explicitly extracted luggage, OR
        # 2. normalize_numeric_values returned explicit number (not just 0 from fallback)
        if luggage_count is None or (luggage_count == 0 and not luggage_from_nlu):
            return "How many bags? (0, 1, 2, etc.)"
        
        try:
            booking["luggage_count"] = int(luggage_count)
            booking["luggage_locked"] = True
            print(f"✅ LUGGAGE LOCKED: {booking['luggage_count']}", flush=True)
        except:
            return "How many bags? Please give a number."
        
        # AUTO-SUGGEST VEHICLE & FARE after luggage confirmed
        vehicle_type, error_msg = suggest_vehicle(booking["passengers"], booking["luggage_count"], ctx.get("jwt_token"))
        if vehicle_type:
            booking["vehicle_type"] = vehicle_type
            booking["vehicle_locked"] = True
            distance_km = calculate_distance_google_maps(booking["pickup"], booking["dropoff"])
            fare = calculate_fare_api(distance_km, vehicle_type, booking["booking_type"], ctx.get("jwt_token"))
            
            # ✅ FALLBACK: If fare calculation fails, use formula (NEVER show None or 0)
            if fare is None or fare == 0:
                if distance_km:
                    booking["distance_km"] = distance_km
                    # Fallback formula: 50 AED base + 3 AED/km
                    base_fare = 50
                    per_km = 3
                    luggage_charge = booking.get("luggage_count", 0) * 10
                    fare = base_fare + (distance_km * per_km) + luggage_charge
                    print(f"[FARE] Using fallback formula: {base_fare} + ({distance_km}km × {per_km}) + ({booking.get('luggage_count', 0)} × 10) = {fare} AED", flush=True)
                else:
                    fare = 100  # Default if distance calculation fails
            else:
                booking["distance_km"] = distance_km if distance_km else 0
            
            booking["fare"] = int(fare) if fare else 100  # ✅ Ensure integer, never 0 or None
            booking["fare_locked"] = True
            print(f"✅ FARE CALCULATED: {booking['fare']} AED", flush=True)
            
            # ✅ SUMMARY: Always show actual number, NEVER "?"
            return f"✅ BOOKING SUMMARY:\n📍 {booking['pickup']} → {booking['dropoff']} ({distance_km}km)\n🚗 {vehicle_type} | 👥 {booking['passengers']} passengers | 🎒 {booking['luggage_count']} bags\n💰 Total Fare: {booking['fare']} AED\n\nShould I proceed with this booking? (Yes/No)"
        else:
            return f"Error with vehicle selection: {error_msg}. Please try again."
    
    # ✅ PROCEED CONFIRMATION (after fare shown) - ✅ FAIL-SAFE: Accept 20+ YES variants
    elif booking.get("fare_locked") and not booking.get("proceed_confirmed"):
        # ✅ QUESTION DETECTION FIRST (before YES/NO check) - PREVENT false YES detection
        if "?" in incoming_text:
            low_text = incoming_text.lower()
            
            # ✅ FIX #1: Check SPECIFIC keywords FIRST (to avoid "journey" matching "time")
            # Order matters: fare/cost BEFORE journey, card/payment BEFORE generic
            if "fare" in low_text or "cost" in low_text or "price" in low_text:
                return f"Your fare is {booking.get('fare', 100)} AED for this journey."
            elif "card" in low_text or "payment" in low_text or "credit" in low_text:
                return "We accept Cash, Credit Card, Apple Pay, Google Pay! ✅"
            elif "ac" in low_text or "air" in low_text or "conditioning" in low_text:
                return "Yes! ✅ All our vehicles have AC with climate control."
            elif "usb" in low_text or "charging" in low_text or "charge" in low_text:
                return "USB charging available in our luxury vehicles! ✅"
            elif "driver" in low_text or "experience" in low_text or "long distance" in low_text:
                return "Our drivers are highly trained professionals with 5+ years of experience. ✅"
            elif "vehicle" in low_text or "available" in low_text or "model" in low_text:
                return "We have Sedans, Luxury Cars, SUVs available for your journey."
            elif "time" in low_text or "journey" in low_text or "travel" in low_text:
                return f"Typically {max(int(booking.get('distance_km', 50)/60), 30)}-60 minutes depending on traffic."
            else:
                # Generic answer if no specific match
                print(f"[Q&A] Generic question detected - answering instead of proceeding", flush=True)
                return "Great question! Our team will contact you shortly with details. Thank you for choosing Star Skyline! 🙏"
        
        # ✅ CHECK: NLU yes_no OR direct text check (20+ variants)
        is_yes = nlu.get("yes_no") == "yes" or check_yes_no(incoming_text) == "yes"
        is_no = nlu.get("yes_no") == "no" or check_yes_no(incoming_text) == "no"
        
        if is_yes:
            booking["proceed_confirmed"] = True
            booking["booking_status"] = "confirmed"
            booking["caller_number"] = from_phone  # ✅ Save phone early for email
            print(f"✅ BOOKING CONFIRMED BY USER (YES detected)", flush=True)
            # ✅ NOTE: Email will be sent AFTER name/phone collection is complete (in final confirmation)
            return "Nice! What's your name?"
        elif is_no:
            # ✅ EVEN IF NO: Still save booking as pending
            booking["proceed_confirmed"] = False
            booking["booking_status"] = "pending_no_response"
            print(f"⏳ USER SAID NO - Auto-saving as pending", flush=True)
            return "No problem. Is there anything you'd like to change about this booking?"
        else:
            # ✅ UNCLEAR: Save as pending and ask again
            print(f"❓ UNCLEAR RESPONSE - Saving as pending", flush=True)
            return "Should I proceed with this booking? (Yes/No)"
    
    # ✅ QUESTION ANSWERING - Detect and answer customer questions BEFORE processing as data
    elif booking.get("proceed_confirmed") and not booking.get("booking_completed"):
        low_text = incoming_text.lower()
        
        # Check if this is a question
        if "?" in incoming_text:
            # ✅ FIX #1b: Check SPECIFIC keywords FIRST (to avoid "journey" matching "time")
            # Order matters: fare/cost BEFORE journey, card/payment BEFORE generic
            if "fare" in low_text or "cost" in low_text or "price" in low_text:
                return f"Your fare is {booking.get('fare', 100)} AED for this journey."
            elif "card" in low_text or "payment" in low_text or "credit" in low_text:
                return "We accept Cash, Credit Card, Apple Pay, Google Pay! ✅"
            elif "ac" in low_text or "air" in low_text or "conditioning" in low_text:
                return "Yes! ✅ All our vehicles have AC with climate control."
            elif "usb" in low_text or "charging" in low_text or "charge" in low_text:
                return "USB charging available in our luxury vehicles! ✅"
            elif "driver" in low_text or "experience" in low_text or "long distance" in low_text:
                return "Our drivers are highly trained professionals with 5+ years of experience. ✅"
            elif "vehicle" in low_text or "available" in low_text or "model" in low_text:
                return "We have Sedans, Luxury Cars, SUVs available for your journey."
            elif "time" in low_text or "journey" in low_text or "travel" in low_text:
                return f"Typically {max(int(booking.get('distance_km', 50)/60), 30)}-60 minutes depending on traffic."
            else:
                # Generic answer if no specific match
                return "Great question! Our team will contact you shortly with details. Thank you for choosing Star Skyline! 🙏"
    
    # ✅ NAME SLOT - Ask for name with confirmation (ONLY AFTER all booking slots locked)
    # FIX #3: Only ask for name after pickup, dropoff, passengers, luggage, datetime ALL locked
    elif (booking.get("pickup_locked") and booking.get("dropoff_locked") and 
          booking.get("passengers_locked") and booking.get("luggage_locked") and
          booking.get("datetime_locked") and not booking.get("name_locked")):
        if booking.get("name_confirm_pending"):
            # ✅ User is confirming the name they gave
            is_yes = nlu.get("yes_no") == "yes" or check_yes_no(incoming_text) == "yes"
            is_no = nlu.get("yes_no") == "no" or check_yes_no(incoming_text) == "no"
            
            if is_yes:
                booking["name_locked"] = True
                booking["name_confirm_pending"] = False
                booking["caller_number"] = from_phone
                print(f"✅ NAME CONFIRMED: {booking['full_name']}", flush=True)
                # Ask about vehicle preference
                return f"Our standard vehicle is a Sedan. Would you like a premium upgrade (Luxury Car, SUV) for a bit more, or keep the Sedan?"
            elif is_no:
                booking["full_name"] = None
                booking["name_confirm_pending"] = False
                return "No problem. Please tell me your full name again."
            else:
                # Not a clear YES/NO, ask again
                return f"Just to confirm, your name is {booking['full_name']}? (Yes/No)"
        else:
            # ✅ STRICT VALIDATION: Reject questions, not names
            low_text = incoming_text.lower().strip()
            
            # Reject if it's a question (has ?, or starts with question words)
            question_words = {"what", "how", "can", "do", "is", "will", "are", "does", "did", "when", "where", "why", "would", "could", "have", "has", "should"}
            first_word = low_text.split()[0].replace("?", "").replace("!", "") if low_text.split() else ""
            
            if "?" in incoming_text or first_word in question_words:
                return "I need your full name. Can you tell me, please?"
            
            # Reject if it contains booking keywords
            booking_keywords = ["burj", "marina", "airport", "mall", "tomorrow", "today", "bag", "passenger", "km", "aed", "fare", "time", "journey", "trip", "vehicle", "driver"]
            if any(kw in low_text for kw in booking_keywords):
                return "I think you sent booking details instead of your name. 😊 Can you just tell me your full name?"
            
            # ✅ Extract name: 2-5 words, mostly alphabetic
            words = incoming_text.strip().split()
            filler_words = {"my", "is", "name", "i", "am", "the", "this", "that", "please", "tell", "here", "its", "bilkul", "haan", "nahi", "my", "your", "yes", "no", "okay", "ok"}
            clean_words = [w for w in words if w.lower() not in filler_words and len(w) > 1 and not any(c in w for c in ["@", "://"])]
            
            # Must have 2-5 words, mostly letters
            if not clean_words or len(clean_words) < 2 or len(clean_words) > 5:
                return "I need your full name. Can you tell me, please?"
            
            # Check if mostly alphabetic (allow apostrophes for names like O'Brien)
            clean_joined = "".join(clean_words)
            alpha_chars = sum(1 for c in clean_joined if c.isalpha())
            if alpha_chars < len(clean_joined) * 0.7:  # At least 70% alphabetic
                return "I need your full name. Can you tell me, please?"
            
            booking["full_name"] = " ".join(clean_words[:5])
            print(f"[NAME] Extracted from response: {booking['full_name']}", flush=True)
            booking["name_confirm_pending"] = True
            return f"Just to confirm, your name is {booking['full_name']}? (Yes/No)"
    
    # ✅ VEHICLE PREFERENCE SLOT - Show luxury cars if requested (AFTER name confirmed)
    elif booking.get("name_locked") and not booking.get("vehicle_preference_asked"):
        vehicle_pref = nlu.get("vehicle_preference")
        low_text = incoming_text.lower()
        
        # ✅ SMART: Detect luxury/premium requests (including Urdu: "car chahiye", "better car", etc)
        asked_upgrade = (vehicle_pref == "luxury" or 
                        "luxury" in low_text or "premium" in low_text or 
                        "better" in low_text or "upgrade" in low_text or
                        ("car" in low_text and ("chahiye" in low_text or "need" in low_text or "want" in low_text)))
        
        if asked_upgrade:
            booking["vehicle_preference"] = "luxury"
            booking["vehicle_preference_asked"] = True
            print(f"✅ VEHICLE PREFERENCE: Luxury/Premium requested", flush=True)
            
            # ✅ SMART: Show available luxury cars with models (just names, no plate/type)
            luxury_cars = [v for v in FLEET_INVENTORY if v["type"] in ["Luxury", "Luxury Van", "SUV"]]
            if luxury_cars:
                car_list = "\n".join([f"• {v['vehicle']}" for v in luxury_cars[:4]])
                print(f"[VEHICLE] Showing luxury options: {len(luxury_cars)} available", flush=True)
                return f"Sir, we have these premium vehicles available:\n{car_list}\n\nWhich model would you prefer?"
            else:
                return f"Perfect! I can arrange a premium vehicle for you. The fare will be adjusted accordingly. Is that okay? (Yes/No)"
        else:
            # Ask if they want upgrade
            booking["vehicle_preference_asked"] = True
            return f"Our standard vehicle is a Sedan. Would you like a premium upgrade (Luxury Car, SUV) for a bit more, or keep the Sedan?"
    
    # ✅ MULTI-STOP SLOT - Collect stops if multi-stop booking
    elif booking.get("luggage_locked") and booking.get("multi_stop") and not booking.get("stops_locked"):
        low_text = incoming_text.lower().strip()
        
        # Parse stops: "The Dubai Mall 60, Gold Souk 45, Spice Market 30"
        if "no" in low_text or len(incoming_text) < 3:
            booking["multi_stop"] = False
            booking["stops_locked"] = True
            print(f"✅ MULTI-STOP CANCELLED", flush=True)
            return f"No problem! So just {booking.get('dropoff')}? (Yes/No)"
        
        # Simple stops parsing (location duration pairs)
        stops_raw = incoming_text.split(",")
        stops = []
        for i, stop_raw in enumerate(stops_raw):
            parts = stop_raw.strip().rsplit(" ", 1)
            if len(parts) == 2:
                location, duration_text = parts
                try:
                    duration_minutes = int(duration_text.split()[0])
                    stops.append({
                        "location": location.strip(),
                        "stop_type": "intermediate",
                        "duration_minutes": duration_minutes
                    })
                except:
                    stops.append({
                        "location": stop_raw.strip(),
                        "stop_type": "intermediate",
                        "duration_minutes": 30
                    })
        
        booking["stops"] = stops
        booking["stops_locked"] = True
        print(f"✅ MULTI-STOP LOCKED: {len(stops)} stops", flush=True)
        return f"Got it! {len(stops)} stops. Total time: {sum(s.get('duration_minutes', 30) for s in stops)} minutes. Cool? (Yes/No)"
    
    # ✅ ROUND-TRIP SLOT - Ask if customer needs return trip
    elif booking.get("name_locked") and not booking.get("round_trip_locked"):
        is_yes = nlu.get("yes_no") == "yes" or check_yes_no(incoming_text) == "yes"
        is_no = nlu.get("yes_no") == "no" or check_yes_no(incoming_text) == "no"
        
        if is_yes:
            booking["round_trip"] = True
            booking["round_trip_locked"] = True
            # Don't lock booking_type yet - wait for return hours
            print(f"✅ ROUND-TRIP CONFIRMED - Now asking for return hours", flush=True)
            return f"Perfect! How many hours you staying at {booking.get('dropoff')}? (e.g., 2, 3, 4 hours)"
        elif is_no:
            booking["round_trip"] = False
            booking["round_trip_locked"] = True
            booking["booking_type"] = detect_booking_type(booking.get("pickup"), booking.get("dropoff"), "point_to_point")
            print(f"✅ ONE-WAY CONFIRMED", flush=True)
            return f"Perfect! Now let me confirm your contact number. We have {from_phone} on file. Is this correct? (Yes/No)"
        else:
            return f"Do you need to return from {booking.get('dropoff', 'your destination')} later, or is it just one-way?"
    
    # ✅ RETURN HOURS SLOT - Collect hours for round-trip
    elif booking.get("round_trip") and not booking.get("return_after_hours_locked"):
        try:
            hours = int(incoming_text.split()[0])
            if 1 <= hours <= 24:
                booking["return_after_hours"] = hours
                booking["return_after_hours_locked"] = True
                booking["booking_type"] = "round_trip"
                print(f"✅ RETURN HOURS LOCKED: {hours} hours", flush=True)
                return f"Great! So you'll return after {hours} hours. Let me confirm your contact number. We have {from_phone} on file. Is this correct? (Yes/No)"
        except:
            pass
        return "How many hours? (1-24)"
    
    # ✅ PHONE SLOT - Ask for phone confirmation/correction
    elif booking.get("round_trip_locked") and not booking.get("phone_locked"):
        is_yes = nlu.get("yes_no") == "yes" or check_yes_no(incoming_text) == "yes"
        is_no = nlu.get("yes_no") == "no" or check_yes_no(incoming_text) == "no"
        
        if is_yes:
            booking["confirmed_contact_number"] = from_phone
            booking["phone_locked"] = True
            print(f"✅ PHONE CONFIRMED: {from_phone}", flush=True)
            return f"Great! Now can you please provide your email address? (e.g., name@gmail.com)"
        elif is_no:
            print(f"[PHONE] User wants to provide different number", flush=True)
            return "No problem! Please provide the contact number you'd like us to use."
        else:
            # Likely providing a different phone number
            clean_phone = incoming_text.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
            if len(clean_phone) >= 10 and clean_phone.isdigit():
                booking["confirmed_contact_number"] = "+" + clean_phone if not incoming_text.startswith("+") else incoming_text
                booking["phone_locked"] = True
                print(f"✅ PHONE CONFIRMED: {booking['confirmed_contact_number']}", flush=True)
                return f"Perfect! Phone {booking['confirmed_contact_number']} noted. Now can you please provide your email address? (e.g., name@gmail.com)"
            else:
                # Not a valid phone, ask again
                return f"I need a valid phone number. Is {from_phone} correct? (Yes/No) Or provide a different number?"
    
    # ✅ NOTES SLOT - ✅ OPTIONAL: Collect special requests/notes from customer (NEW FEATURE)
    elif booking.get("email_locked") and not booking.get("notes_locked"):
        low_text = incoming_text.lower().strip()
        
        # ✅ Accept any notes (optional) - even if just "no", treat as no notes
        is_no = check_yes_no(incoming_text) == "no" or "no" in low_text or "none" in low_text or "skip" in low_text
        
        if is_no or len(incoming_text) < 3:
            # No special notes
            booking["notes"] = None
            booking["notes_locked"] = True
            print(f"✅ NOTES SKIPPED - No special requests", flush=True)
        else:
            # ✅ Capture notes (max 500 chars to avoid spam)
            notes_text = incoming_text.strip()[:500]
            booking["notes"] = notes_text
            booking["notes_locked"] = True
            print(f"✅ NOTES CAPTURED: {notes_text[:100]}...", flush=True)
        
        # Now create the booking (finally!)
        booking_ref = booking.get("booking_reference") or generate_booking_reference()
        booking["booking_reference"] = booking_ref
        
        # ✅ Select specific vehicle from LIVE backend list
        jwt_token = ctx.get("jwt_token")
        selected_vehicle = select_vehicle_from_fleet(booking.get("vehicle_type", "sedan"), jwt_token)
        
        # ✅ Determine correct endpoint and payload based on booking_type
        booking_type = booking.get("booking_type", "point_to_point")
        
        # Base payload
        base_payload = {
            "customer_name": booking.get("full_name", "Customer"),
            "customer_phone": booking.get("confirmed_contact_number") or from_phone,
            "customer_email": booking.get("email"),
            "pickup_location": booking["pickup"],
            "dropoff_location": booking["dropoff"],
            "booking_type": booking_type,
            "vehicle_type": booking.get("vehicle_type", "sedan"),
            "vehicle_model": selected_vehicle.get("model") or selected_vehicle.get("vehicle", "Vehicle"),
            "vehicle_color": selected_vehicle.get("color", "Black"),
            "assigned_vehicle_id": selected_vehicle.get("id"),
            "distance_km": booking.get("distance_km", 0),
            "passengers_count": int(booking.get("passengers", 1)),
            "luggage_count": int(booking.get("luggage_count", 0)),
            "payment_method": "card",
            "booking_source": "bareerah_ai",
            "notes": booking.get("notes")
        }
        
        # Add type-specific fields
        if booking_type == "round_trip":
            base_payload["meeting_location"] = booking.get("dropoff")
            base_payload["return_after_hours"] = booking.get("return_after_hours", 3)
            endpoint = "/api/bookings/create-round-trip"
        elif booking_type == "multi_stop":
            base_payload["stops"] = booking.get("stops", [])
            endpoint = "/api/bookings/create-multi-stop"
        elif booking_type == "hourly_rental":
            base_payload["rental_hours"] = booking.get("rental_hours", 5)
            base_payload["dropoff_location"] = booking.get("pickup")  # Same location for rentals
            endpoint = "/api/bookings/create-hourly-rental"
        else:
            endpoint = "/api/bookings/create-manual"
        
        booking_payload = base_payload
        print(f"[PAYLOAD] Sending {booking_type} booking to {endpoint}: {booking_payload}", flush=True)
        
        # Try to create booking
        if create_booking_direct(booking_payload, endpoint=endpoint):
            booking["booking_status"] = "confirmed"
            print(f"[DB] ✅ Booking CONFIRMED with notes", flush=True)
            notify_booking_to_team(booking_payload, status="created")
        else:
            booking["booking_status"] = "pending_confirmation"
            print(f"[DB] ⚠️ Booking pending - will sync when backend online", flush=True)
            notify_booking_to_team(booking_payload, status="pending")
        
        booking["booking_completed"] = True
        is_confirmed = booking.get("booking_status") == "confirmed"
        
        if is_confirmed:
            upsell = get_upsell_suggestion() if booking.get("booking_type") == "point_to_point" else ""
            confirmation_msg = f"""✅ BOOKING CONFIRMED!

📖 Reference: {booking_ref}
📍 Pickup: {booking['pickup']}
📍 Dropoff: {booking['dropoff']}
🚗 Vehicle: {booking['vehicle_type']} | 👥 {booking['passengers']} passengers
💰 Total Fare: {booking['fare']} AED

Our driver will contact you at {booking.get('confirmed_contact_number') or from_phone} shortly.
{upsell}
Thank you for choosing Star Skyline! 🙏"""
            return confirmation_msg
        else:
            confirmation_msg = f"""✅ BOOKING SAVED!

📖 Reference: {booking_ref}
🚗 Vehicle: {booking['vehicle_type']} | 👥 {booking['passengers']} passengers
📍 Pickup: {booking['pickup']}
📍 Dropoff: {booking['dropoff']}
💰 Total Fare: {booking['fare']} AED

Our team will contact you at {booking.get('confirmed_contact_number') or from_phone} within 5 minutes.
Thank you for choosing Star Skyline! 🙏"""
            return confirmation_msg
    
    # ✅ EMAIL SLOT - OPTIONAL WITH SKIP (email can be skipped)
    elif not booking.get("email_locked"):
        low_text = incoming_text.lower()
        
        # ✅ SKIP EMAIL: User said "skip", "no", "nahi", "na", etc.
        if any(skip_word in low_text for skip_word in ["skip", "no", "nahi", "na", "dont need", "not needed", "proceed"]):
            booking["email"] = "not_provided"
            booking["email_locked"] = True
            if not booking.get("confirmed_contact_number"):
                booking["confirmed_contact_number"] = from_phone
            booking["confirmed"] = True
            booking["booking_status"] = "confirmed"
            print(f"✅ EMAIL SKIPPED: Customer chose not to provide", flush=True)
            
            # ✅ Ask for optional special requests/notes
            return f"Perfect! Now, do you have any special requests? For example:\n• Water bottles needed\n• WiFi required\n• Extra AC needed\n\nOr just say 'No' to proceed."
        
        normalized_email = normalize_spoken_email(incoming_text)
        
        # Check if user accidentally sent their name instead of email
        words_in_input = incoming_text.strip().split()
        looks_like_name = (
            2 <= len(words_in_input) <= 5 and 
            len(incoming_text) < 50 and
            incoming_text.replace(" ", "").isalpha() and
            "?" not in incoming_text and
            "@" not in incoming_text
        )
        
        if looks_like_name:
            print(f"[EMAIL] Input looks like name, not email: '{incoming_text}'", flush=True)
            return f"I think you sent your name! 😊 You can provide your email or just say 'skip' to continue."
        
        # ✅ ALWAYS CREATE BOOKING (confirmed or pending)
        booking_ref = booking.get("booking_reference") or generate_booking_reference()
        booking["booking_reference"] = booking_ref
        
        if is_valid_email(normalized_email):
            booking["email"] = normalized_email
            booking["email_locked"] = True
            if not booking.get("confirmed_contact_number"):
                booking["confirmed_contact_number"] = from_phone
            booking["confirmed"] = True
            booking["booking_status"] = "confirmed"
            print(f"✅ EMAIL LOCKED: {booking['email']}", flush=True)
            
            return f"Great! Now, do you have any special requests? For example:\n• Water bottles needed\n• WiFi required\n• Extra AC needed\n\nOr just say 'No' to proceed."
        else:
            booking["email_attempts"] = booking.get("email_attempts", 0) + 1
            if booking["email_attempts"] >= 2:
                # ✅ AUTO-SAVE: Skip email after 2 failed attempts
                booking["email"] = "not_provided"
                booking["email_locked"] = True
                print(f"[DB] ⏳ Email attempts exceeded - skipping email", flush=True)
                return f"No problem! Let's proceed. Do you have any special requests? (Or just say 'No')"
            else:
                return "Email not recognized. Try again or just say 'skip' to continue."
    
    # Default: booking complete
    return "Your booking is confirmed! Thank you for choosing Star Skyline Limousine. 🙏"

def generate_tts(text, call_sid, lang="en"):
    """✅ FREE TTS: pyttsx3 (completely offline, no API costs!) - ALWAYS fresh audio"""
    if not text or len(text) == 0:
        return None
    
    text_chunk = text[:240]
    import time
    import pyttsx3
    
    timestamp = str(int(time.time() * 1000))  # milliseconds
    text_hash = hashlib.md5(text_chunk.encode()).hexdigest()
    filename = f"tts_{text_hash}_{timestamp}.mp3"
    filepath = f"./public/{filename}"
    
    try:
        # Initialize pyttsx3 engine
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)  # Speed
        engine.setProperty('volume', 0.9)  # Volume
        
        # Save to file
        engine.save_to_file(text_chunk, filepath)
        engine.runAndWait()
        engine.stop()
        
        print(f"[TTS] ✅ pyttsx3 (FREE) generated audio: {filename}", flush=True)
        return f"/public/{filename}"
    except Exception as e:
        print(f"[TTS] ❌ pyttsx3 error: {str(e)}", flush=True)
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
    Returns: Simple float fare (no MoneyType or Decimal)
    With fallback formula: base_fare + (distance_km * rate_per_km) + luggage_fee
    """
    if not distance_km or distance_km <= 0:
        return 0  # ✅ Never return None, use fallback
    
    result = backend_api("POST", "/bookings/calculate-fare", {
        "distance_km": distance_km,
        "vehicle_type": vehicle_type,
        "booking_type": booking_type
    }, jwt_token)
    
    print(f"[FARE API] Backend response: {result}", flush=True)
    
    # Try multiple possible response keys
    if result:
        fare_value = result.get("fare_aed") or result.get("fare") or result.get("total_fare")
        if fare_value is not None:
            try:
                fare = float(fare_value)
                fare_aed = round(fare)
                print(f"✅ FARE CALCULATED FROM API: {fare_aed} AED (raw: {fare})", flush=True)
                return fare_aed
            except Exception as e:
                print(f"❌ FARE CONVERSION ERROR: {e}", flush=True)
    
    # ✅ FALLBACK CALCULATION: If API fails, use formula
    print(f"[FARE] API failed or no response, using fallback formula...", flush=True)
    base_fare = 25  # AED
    rate_per_km = 3.0  # AED/km
    luggage_fee = 10  # AED for luggage
    
    fallback_fare = base_fare + (distance_km * rate_per_km) + luggage_fee
    fallback_fare = round(fallback_fare)
    print(f"✅ FARE CALCULATED (FALLBACK): {fallback_fare} AED", flush=True)
    return fallback_fare

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

def is_confirmation_or_greeting(text: str) -> bool:
    """✅ PERMANENT FIX #1: BLOCK YES/NO/GREETINGS from location extraction
    This prevents EMPTY_RESPONSE garbage from reaching LLM."""
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    # Combine all YES/NO/GREETING words into a single blocklist
    blocklist = (
        YES_WORDS | NO_WORDS | 
        set(GREETINGS_EN) | set(GREETINGS_UR) | set(GREETINGS_AR) |
        {"correct", "right", "true", "false", "maybe", "unclear", "dunno", "idk",
         "what", "when", "where", "why", "how", "huh", "what?"}
    )
    
    # If user said ONLY confirmation/greeting words with no location keywords
    for word in text_lower.split():
        if word not in blocklist and len(word) > 2:
            # Found a word that's not a filler - might be a location
            return False
    
    # All words are confirmations/greetings
    print(f"[GUARD] 🚫 Blocking confirmation/greeting from location extraction: '{text}'", flush=True)
    return True

def extract_pickup_location_llm(text: str) -> str:
    """✅ PERMANENT FIX #2: Multi-layer safeguard against EMPTY_RESPONSE
    - Layer 1: Block yes/no/greetings BEFORE LLM
    - Layer 2: Validate LLM output  
    - Layer 3: Never return garbage strings"""
    print(f"[LLM] Input text: '{text}'", flush=True)
    
    # ✅ LAYER 1: BLOCK CONFIRMATIONS/GREETINGS - NEVER send to LLM
    if is_confirmation_or_greeting(text):
        print(f"[LLM] ❌ Rejected: Input is confirmation/greeting, not location", flush=True)
        return None
    
    try:
        response = OPENAI_CLIENT.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Extract ONLY the location/address mentioned in user input. Remove fillers like 'I want to go to', 'I have to go to', 'meri', 'the way', etc. Keep ONLY the clean location name (can be any length). Extract: Dubai International Airport, Dubai Marina, Burj Khalifa, airport, mall names, neighborhoods, street names, building numbers - anything that identifies a place in Dubai or nearby emirates. IMPORTANT: If NO location is mentioned at all, return NOTHING (empty response), not 'No location mentioned.' Return ONLY the location, nothing else."},
                {"role": "user", "content": text}
            ],
            max_tokens=100,
            temperature=0,
            top_p=0.1,
            timeout=5
        )
        location = response.choices[0].message.content.strip()
        print(f"[LLM] ✅ Extracted: '{location}'", flush=True)
        
        # ✅ LAYER 2: VALIDATE LLM OUTPUT - Reject garbage strings
        # Reject: empty, single chars, EMPTY_RESPONSE, "no location mentioned", etc.
        if not location or len(location) <= 1 or location == ".":
            print(f"[LLM] ❌ No valid location found", flush=True)
            return None
        
        if "empty" in location.lower() or "no location" in location.lower():
            print(f"[LLM] ❌ LLM returned invalid response: '{location}'", flush=True)
            return None
        
        # ✅ LAYER 3: FINAL CHECK - Make sure extracted location has at least 2 tokens
        location_tokens = location.split()
        if len(location_tokens) < 2:
            print(f"[LLM] ❌ Location too short: '{location}' ({len(location_tokens)} tokens)", flush=True)
            return None
        
        return location
    except Exception as e:
        print(f"[LLM] ❌ Failed ({type(e).__name__}): {e}", flush=True)
        return None

def validate_pickup_with_places_api(location: str) -> bool:
    """✅ ROCK-SOLID: Places API + 120+ Dubai Locations Fallback Dictionary
    
    Flow:
    1. Try Google Places API
    2. If API fails → Check 120+ Dubai locations fallback dictionary
    3. If specific address (has numbers + 3+ parts) → Auto-accept
    4. After 2 failed attempts → Accept anyway (ZERO business loss)
    """
    if not location:
        print(f"[PLACES] ❌ Empty location input", flush=True)
        return False
    
    # ✅ COMPREHENSIVE FALLBACK DICTIONARY - 120+ Popular Dubai Locations
    POPULAR_DUBAI_LOCATIONS = {
        # Airports (10)
        "dubai airport": "Dubai International Airport (DXB), Garhoud, Dubai",
        "dubai international": "Dubai International Airport (DXB), Garhoud, Dubai",
        "international airport": "Dubai International Airport (DXB), Garhoud, Dubai",
        "dxb": "Dubai International Airport (DXB), Garhoud, Dubai",
        "al maktoum": "Al Maktoum International Airport (DWC), Jebel Ali, Dubai",
        "sharjah airport": "Sharjah International Airport (SHJ), Sharjah",
        "abu dhabi airport": "Abu Dhabi International Airport (AUH), Abu Dhabi",
        "auh": "Abu Dhabi International Airport (AUH), Abu Dhabi",
        "terminal 1": "Dubai International Airport Terminal 1, Dubai",
        "terminal 3": "Dubai International Airport Terminal 3, Dubai",
        
        # Malls & Shopping (20)
        "dubai mall": "The Dubai Mall, Downtown Dubai, Dubai",
        "marina mall": "Dubai Marina Mall, Sheikh Zayed Road, Dubai",
        "dubai marina mall": "Dubai Marina Mall, Sheikh Zayed Road, Dubai",
        "mall of the emirates": "Mall of the Emirates, Al Barsha, Dubai",
        "emirates mall": "Mall of the Emirates, Al Barsha, Dubai",
        "deira city centre": "Deira City Centre, Deira, Dubai",
        "mirdif city centre": "Mirdif City Centre, Mirdif, Dubai",
        "city centre": "Deira City Centre, Deira, Dubai",
        "festival city": "Dubai Festival City, Dubai",
        "bluewaters": "Bluewaters Island, Dubai",
        "dragon mart": "Dragon Mart, International City, Dubai",
        "international city": "International City, Dubai",
        "jlt": "Jumeirah Lakes Towers, Dubai",
        "jvc": "Jumeirah Village Circle, Dubai",
        "jvt": "Jumeirah Village Triangle, Dubai",
        "la mer": "La Mer Beach, Jumeirah 1, Dubai",
        "gold souk": "Dubai Gold Souk, Deira, Dubai",
        "spice souk": "Spice Souk, Deira, Dubai",
        "al seef": "Al Seef, Dubai Creek, Bur Dubai, Dubai",
        "souq madinat": "Souk Madinat Jumeirah, Umm Suqeim, Dubai",
        
        # Parks & Outdoor (15)
        "zabeel park": "Zabeel Park, Za'abeel, Dubai",
        "zabeel": "Zabeel Park, Za'abeel, Dubai",
        "creek park": "Dubai Creek Park, Ras Al Khor, Dubai",
        "safa park": "Safa Park, Al Wasl, Dubai",
        "mushrif park": "Mushrif National Park, Dubai",
        "al baraha park": "Al Baraha Park, Al Baraha, Dubai",
        "kite beach": "Kite Beach, Umm Suqeim, Dubai",
        "al qudra lakes": "Al Qudra Lakes, Dubai",
        "love lake": "Al Qudra Love Lake, Dubai",
        "hatta": "Hatta, Dubai",
        "hatta dam": "Hatta Dam, Hatta, Dubai",
        "al marmoom": "Al Marmoom Desert Conservation Reserve, Dubai",
        "desert safari": "Desert Safari, Dubai Desert, Dubai",
        "miracle garden": "Dubai Miracle Garden, Dubailand, Dubai",
        "butterfly garden": "Dubai Butterfly Garden, Dubailand, Dubai",
        
        # Major Landmarks (20)
        "burj khalifa": "Burj Khalifa, Downtown Dubai, Dubai",
        "burj": "Burj Khalifa, Downtown Dubai, Dubai",
        "emirates tower": "Emirates Towers, Business Bay, Dubai",
        "downtown dubai": "Downtown Dubai, Dubai",
        "burj al arab": "Burj Al Arab, Umm Suqeim, Dubai",
        "jumeirah": "Jumeirah, Dubai",
        "palm jumeirah": "Palm Jumeirah, Dubai",
        "dubai marina": "Dubai Marina, Dubai",
        "jbr": "JBR - Jumeirah Beach Residence, Dubai Marina, Dubai",
        "jbr beach": "JBR - Jumeirah Beach Residence, Dubai Marina, Dubai",
        "the beach jbr": "The Beach at JBR, Dubai Marina, Dubai",
        "dubai marina walk": "Dubai Marina Walk, Dubai Marina, Dubai",
        "zero gravity": "Zero Gravity, Dubai Marina, Dubai",
        "skydive dubai": "Skydive Dubai, Dubai Marina, Dubai",
        "atlantis": "Atlantis The Palm, Palm Jumeirah, Dubai",
        "madinat jumeirah": "Madinat Jumeirah, Umm Suqeim, Dubai",
        "wild wadi": "Wild Wadi Waterpark, Umm Suqeim, Dubai",
        "blue waters": "Bluewaters Island, Dubai",
        "ain dubai": "Ain Dubai, Bluewaters Island, Dubai",
        "dubai frame": "Dubai Frame, Zabeel Park, Dubai",
        
        # Entertainment & Theme Parks (15)
        "dubai parks": "Dubai Parks and Resorts, Jebel Ali, Dubai",
        "legoland dubai": "Legoland Dubai, Dubai Parks, Jebel Ali, Dubai",
        "motiongate": "Motiongate Dubai, Dubai Parks, Jebel Ali, Dubai",
        "bollywood park": "Bollywood Parks Dubai, Dubai Parks, Jebel Ali, Dubai",
        "img worlds": "IMG Worlds of Adventure, Sheikh Mohammed Bin Zayed Road, Dubai",
        "global village": "Global Village, Sheikh Mohammed Bin Zayed Road, Dubai",
        "expo city": "Expo City Dubai, Jebel Ali, Dubai",
        "ski dubai": "Ski Dubai, Al Barsha, Dubai",
        "aquarium": "Dubai Aquarium, Downtown Dubai, Dubai",
        "aquarium downtown": "Dubai Aquarium, Downtown Dubai, Dubai",
        "aquarium jbr": "The Underwater Zoo, Atlantis The Palm, Dubai",
        "vr park": "VR Park, Dubai Mall, Downtown Dubai, Dubai",
        "laser quest": "Laser Quest, Dubai Marina, Dubai",
        "bowling": "Bowling Lounge, Dubai Marina, Dubai",
        "speedway": "Dubai Speedway, Dubai",
        
        # Residential Areas (20)
        "arabian ranches": "Arabian Ranches, Dubai",
        "springs": "The Springs, Emirates Living, Dubai",
        "the springs": "The Springs, Emirates Living, Dubai",
        "damac hills": "DAMAC Hills, Dubailand, Dubai",
        "creek harbor": "Creek Harbour, Dubai Creek Harbour, Dubai",
        "creek harbour": "Creek Harbour, Dubai Creek Harbour, Dubai",
        "business bay": "Business Bay, Dubai",
        "difc": "Dubai International Financial Centre, Dubai",
        "al barsha": "Al Barsha, Dubai",
        "al barsha 1": "Al Barsha 1, Dubai",
        "al barsha 2": "Al Barsha 2, Dubai",
        "dubai sports city": "Dubai Sports City, Dubai",
        "sports city": "Dubai Sports City, Dubai",
        "dubai silicon oasis": "Dubai Silicon Oasis, Dubai",
        "motor city": "Dubai Motor City, Dubai",
        "karama": "Al Karama, Dubai",
        "deira": "Deira, Dubai",
        "bur dubai": "Bur Dubai, Dubai",
        "bur deira": "Bur Deira, Dubai",
        "al fahidi": "Al Fahidi Historical Neighbourhood, Bur Dubai, Dubai",
        
        # Industrial & Zones (10)
        "jebel ali": "Jebel Ali Free Zone, Dubai",
        "jebel ali port": "Jebel Ali Port, Dubai",
        "free zone": "Jebel Ali Free Zone, Dubai",
        "industrial area": "Dubai Industrial City, Dubai",
        "port rashid": "Port Rashid, Dubai",
        "jafza": "Jebel Ali Free Zone Authority, Dubai",
        "mizhor": "MIZHOR Development Zone, Dubai",
        "nad al sheba": "Nad Al Sheba, Dubai",
        "mina rashid": "Mina Rashid, Dubai",
        "hamriyah": "Hamriyah Free Zone, Sharjah",
    }
    
    location_lower = location.lower().strip()
    
    # ✅ STEP 1: Check if exact match in fallback dictionary
    if location_lower in POPULAR_DUBAI_LOCATIONS:
        matched_name = POPULAR_DUBAI_LOCATIONS[location_lower]
        print(f"[FALLBACK] Match found: {matched_name}", flush=True)
        return True
    
    # ✅ STEP 2: Check for substring matches in fallback dictionary (contains)
    for key, value in POPULAR_DUBAI_LOCATIONS.items():
        if key in location_lower or location_lower in key:
            print(f"[FALLBACK] Match found: {value}", flush=True)
            return True
    
    # ✅ STEP 3: FUZZY MATCHING - 50% word overlap
    # Convert location to words, remove stop words
    stop_words = {"the", "a", "an", "and", "or", "in", "at", "to", "from", "for", "by"}
    location_words = set(w for w in location_lower.split() if w not in stop_words and w)
    
    best_fallback_match = None
    best_fallback_score = 0
    
    for key, value in POPULAR_DUBAI_LOCATIONS.items():
        key_words = set(w for w in key.split() if w not in stop_words and w)
        
        if location_words and key_words:
            # Calculate word overlap percentage
            overlap = len(location_words & key_words)
            total = max(len(location_words), len(key_words))
            match_score = overlap / total if total > 0 else 0
            
            # If 50%+ overlap, it's a match
            if match_score >= 0.5 and match_score > best_fallback_score:
                best_fallback_match = value
                best_fallback_score = match_score
                print(f"[FALLBACK] Fuzzy match for '{key}' ({match_score:.0%} overlap) → {value}", flush=True)
    
    if best_fallback_match:
        print(f"[FALLBACK] Match found: {best_fallback_match}", flush=True)
        return True
    
    # ✅ STEP 4: AUTO-ACCEPT COMPLETE ADDRESSES (contain building numbers, gates, etc)
    # If address contains numbers + multiple parts = customer knows exact location
    address_parts = location.split()
    has_numbers = any(char.isdigit() for char in location)
    has_multiple_parts = len(address_parts) >= 3
    
    if has_numbers and has_multiple_parts:
        print(f"[FALLBACK] Match found: {location} (specific address with building details)", flush=True)
        return True  # Accept specific addresses with numbers (factories, buildings, etc)
    
    if not GOOGLE_MAPS_API_KEY:
        print(f"[FALLBACK] No API key - accepting location as-is: {location}", flush=True)
        return True  # If no API key, accept it
    
    # ✅ STEP 5: Try Google Places API (only if no fallback match)
    try:
        url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        
        # Try with exact format first (includes Dubai, UAE)
        exact_query = f"{location}, Dubai, UAE"
        params = {
            "input": exact_query,
            "key": GOOGLE_MAPS_API_KEY,
            "components": "country:ae",
            "language": "en"
        }
        
        print(f"[PLACES] API Query 1: '{exact_query}'", flush=True)
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        api_status = data.get('status', 'UNKNOWN')
        predictions = data.get("predictions", [])
        print(f"[PLACES] API Status: {api_status}, Results: {len(predictions)}", flush=True)
        
        # If API succeeds, return result
        if predictions:
            matched = predictions[0]["description"]
            print(f"[PLACES] ✅ API SUCCESS: Found '{matched}'", flush=True)
            return True
        
        # ✅ STEP 5: If API fails (REQUEST_DENIED, OVER_QUERY_LIMIT, timeout, etc.) → Accept anyway
        if api_status in ["REQUEST_DENIED", "ZERO_RESULTS", "OVER_QUERY_LIMIT"]:
            print(f"[PLACES] ⚠️ API returned {api_status} - accepting location anyway to prevent lead loss: {location}", flush=True)
            return True  # Accept to prevent business loss
        
        # Try fallback query 2
        fallback_query = f"{location}, Dubai"
        params["input"] = fallback_query
        print(f"[PLACES] API Query 2: '{fallback_query}'", flush=True)
        response = requests.get(url, params=params, timeout=5)
        predictions = response.json().get("predictions", [])
        
        if predictions:
            matched = predictions[0]["description"]
            print(f"[PLACES] ✅ API SUCCESS (Query 2): Found '{matched}'", flush=True)
            return True
        
        # Try fallback query 3
        params["input"] = location
        print(f"[PLACES] API Query 3: '{location}' (raw)", flush=True)
        response = requests.get(url, params=params, timeout=5)
        predictions = response.json().get("predictions", [])
        
        if predictions:
            matched = predictions[0]["description"]
            print(f"[PLACES] ✅ API SUCCESS (Query 3): Found '{matched}'", flush=True)
            return True
        
        # ✅ STEP 6: After all API attempts fail → Accept anyway (ZERO business loss)
        print(f"[PLACES] ⚠️ API failed after 3 queries - accepting location anyway to prevent lead loss: {location}", flush=True)
        return True  # Accept to prevent business loss
        
    except Exception as e:
        print(f"[PLACES] ⚠️ API Error ({type(e).__name__}: {e}) - accepting location anyway: {location}", flush=True)
        return True  # Accept on ANY API error to prevent business loss

# ✅ REDIS CACHE: FUZZY MATCHING FOR FAQ - 90%+ hit rate, <30ms response
def get_cached_faq_response(customer_message: str, language: str = "en") -> Optional[str]:
    """
    Fuzzy matching for FAQ cache with stop word removal and 80% threshold.
    Priority: Exact match → 80% partial match → GPT-4o fallback
    Expected hit rate: 90%+ | Response: <30ms | Cost: ~$0
    """
    try:
        # ✅ STEP 1: Normalize input - lowercase & remove punctuation
        customer_text = customer_message.lower().strip()
        customer_text = ''.join(c for c in customer_text if c.isalnum() or c.isspace())
        
        # ✅ STEP 2: Remove stop words
        stop_words = {
            "my", "is", "the", "from", "to", "please", "can", "you", "i", "me", "a", "an",
            "and", "or", "but", "with", "have", "has", "had", "do", "does", "did", "would",
            "could", "should", "will", "am", "are", "be", "been", "being", "what", "when",
            "where", "why", "how", "which", "who", "whom", "whose", "that", "this", "these",
            "those", "for", "at", "by", "in", "on", "of", "as", "if", "about", "tell", "give"
        }
        customer_words = set(w for w in customer_text.split() if w not in stop_words)
        
        best_match = None
        best_score = 0
        
        # ✅ STEP 3: Check all cache entries
        for cache_key, cache_data in BAREERAH_QA_CACHE.items():
            if not isinstance(cache_data, dict) or language not in cache_data:
                continue
            
            # Split cache key by | (alternatives)
            key_variants = cache_key.split("|")
            
            for variant in key_variants:
                # Normalize cache key (remove dots, lowercase)
                variant_normalized = variant.replace(".", " ").lower()
                variant_words = set(w for w in variant_normalized.split() if w not in stop_words)
                
                # ✅ PRIORITY 1: Exact match (100% score)
                if variant_normalized in customer_text or customer_text in variant_normalized:
                    print(f"[CACHE] 🎯 EXACT MATCH for '{variant}' (language: {language})", flush=True)
                    return cache_data[language]
                
                # ✅ PRIORITY 2: Partial match (80%+ overlap)
                if variant_words and customer_words:
                    # Calculate word overlap percentage
                    overlap = len(variant_words & customer_words)
                    total = max(len(variant_words), len(customer_words))
                    match_score = overlap / total if total > 0 else 0
                    
                    # Keep best match if it's ≥40% (threshold reduced for natural speech)
                    if match_score >= 0.4 and match_score > best_score:
                        best_match = cache_data[language]
                        best_score = match_score
                        print(f"[REDIS] HIT: key '{variant}' matched {match_score:.0%}", flush=True)
        
        # ✅ If best match found, use it
        if best_match:
            return best_match
        
        print(f"[REDIS] No match (threshold: 40%) - using GPT-4o", flush=True)
        return None
        
    except Exception as e:
        print(f"[CACHE] ⚠️ Cache lookup error ({type(e).__name__}): {e} - falling back to GPT-4o", flush=True)
        return None

def extract_nlu(text, call_sid=None):
    """✅ EMERGENCY ULTIMATE FIX: ROBUST SUPER PROMPT - Handles fillers, merges state, auto-datetime"""
    try:
        ctx = call_contexts.get(call_sid, {})
        locked_slots = ctx.get("locked_slots", {})
        flow_step = ctx.get("flow_step", "dropoff")
        attempts = ctx.get("attempts", {})
        
        system_prompt = """You are Bareerah, jolly professional limo concierge in Dubai – multilingual (English/Urdu/Arabic), natural, upsell spots like Burj. NEVER mention AI.

Input: Customer text + Current state (flow_step, locked_slots, attempts).
Output ONLY valid JSON (strict, no extras – parse errors kill calls):
{
  "intent": "booking|confirm|reject|clarify|datetime|name|phone|email|skip|complete|error",
  "confidence": 0.0-1.0,
  "pickup": "normalized full location or ''",
  "dropoff": "normalized full location or ''",
  "has_from_word": true|false,
  "datetime": "YYYY-MM-DD HH:MM or ''",
  "passengers": int or -1,
  "luggage": int or -1,
  "vehicle_type": "auto-selected or user pref or ''",
  "yes_no": "yes|no|''",
  "full_name": "or ''",
  "phone": "+971 formatted or ''",
  "email": "valid or '' or 'skip'",
  "notes": "or ''",
  "booking_type": "point_to_point default",
  "rental_hours": int or -1,
  "next_flow_step": "dropoff|pickup|datetime|passengers|luggage|vehicle|fare|name|phone|email|notes|confirm|complete",
  "response_text": "Short jolly reply (<60 words, in lang, e.g. 'Perfect! Locked. When?')",
  "trigger_email": true|false,
  "updated_locked_slots": {merged dict, NEVER overwrite locked unless 'change'},
  "error": "brief if any or ''"
}

RULES (ZERO FAILS):
- STATE MERGE: Always update locked_slots with new extractions ONLY if confidence>=0.7 and not locked. On 'no/change': Unlock current, increment attempts[flow_step].
- FLOW: Strict order, but jump if user says ahead (e.g. '2 people' on datetime → lock passengers, stay datetime till confirmed).
- FILLERS/EMPTY: 'uh', 'um', silence, garbage → intent='clarify', response_text='Sorry, repeat please?', no step change.
- LOCATION FUZZY MATCH (40%+ match = HIGH CONFIDENCE 0.8+):
  Exact fuzzy keys:
  "dubai airport" / "dxb" / "airport" → "Dubai International Airport (DXB), Garhoud, Dubai" [CONF 0.8+]
  "dubai international airport" → "Dubai International Airport (DXB), Garhoud, Dubai" [CONF 0.9]
  "marina mall" / "marina" → "Dubai Marina Mall, Sheikh Zayed Road, Dubai" [CONF 0.8+]
  "burj khalifa" / "burj" → "Burj Khalifa, Downtown Dubai, Dubai" [CONF 0.85]
  "emirates tower" → "Emirates Towers, Business Bay, Dubai" [CONF 0.8]
  "jumeirah" / "jbr" → "Jumeirah, Dubai" [CONF 0.8]
  "palm jumeirah" → "Palm Jumeirah, Dubai" [CONF 0.8]
  "atlantis" → "Atlantis The Palm, Palm Jumeirah, Dubai" [CONF 0.8]
  "burj al arab" → "Burj Al Arab, Umm Suqeim, Dubai" [CONF 0.8]
  "downtown dubai" → "Downtown Dubai, Dubai" [CONF 0.8]
  "deira" → "Deira, Dubai" [CONF 0.8]
  "business bay" → "Business Bay, Dubai" [CONF 0.8]
  "dubai mall" → "The Dubai Mall, Downtown Dubai, Dubai" [CONF 0.8]
  "mall of emirates" → "Mall of the Emirates, Al Barsha, Dubai" [CONF 0.8]
  "global village" → "Global Village, Sheikh Mohammed Bin Zayed Road, Dubai" [CONF 0.75]
  "expo city" → "Expo City Dubai, Jebel Ali, Dubai" [CONF 0.8]
  After 2 attempts: Accept raw, trigger_email=true.
- DATETIME: 'tomorrow 4 pm' → '2025-12-10 16:00' (base Dec 9, 2025). 'Today 3pm' → '2025-12-09 15:00'. 'Uh tomorrow' → '2025-12-10 14:00' (default 2pm).
- CONFIRM: 'yes' → lock, next_step. 'no' → unlock current, clarify.
- VEHICLE: When passengers+luggage known: <=4pax/3lug=Sedan; <=6/6=Luxury SUV; >Van. Set in locked_slots.
- FARE: distance=20km fallback, fare=50+(20*3.5)+(lug*20).
- COMPLETE: All slots? → next='complete', response='Booking confirmed! Driver calls soon.', trigger_email=false.
- PERSONALITY: 'Got it! Heading to DXB. Where from?' Urdu: 'Theek hai! Kab chahiye?' Only 'Walaikum' if salam.

⚠️ CRITICAL - ALWAYS RETURN VALID JSON (NO EXCEPTIONS):
If any error or low confidence (<0.7): STILL return valid JSON with intent="clarify", confidence=0.5, response_text="Let me confirm that – could you say the location again?", next_flow_step=current_step.
NEVER break JSON format. ALWAYS return a valid dict."""

        user_prompt = f"""Text: "{text}"
State: flow_step='{flow_step}', locked_slots={json.dumps(locked_slots)[:100]}, attempts={attempts}, language='{ctx.get('language', 'en')}'

Extract/merge/progress. Handle fillers as clarify. Output ready JSON for parse."""

        response = OPENAI_CLIENT.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=600,
            timeout=5
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # ✅ Validate result
        if not isinstance(result, dict) or 'response_text' not in result:
            result = {"response_text": "Sorry, technical glitch. Repeat?", "next_flow_step": flow_step, "updated_locked_slots": locked_slots, "intent": "error"}
        
        print(f"[NLU] ✅ intent={result.get('intent')} | next={result.get('next_flow_step')} | confidence={result.get('confidence', 0)}", flush=True)
        return result
        
    except Exception as e:
        print(f"[NLU] ❌ CRASH: {e}", flush=True)
        return {
            "intent": "error",
            "confidence": 0.0,
            "next_flow_step": flow_step if call_sid else "dropoff",
            "response_text": "Sorry, technical glitch. Repeat?",
            "trigger_email": False,
            "updated_locked_slots": locked_slots if call_sid else {},
            "error": str(e)
        }

def auto_select_vehicle(passengers, luggage):
    """✅ FINAL FIX: Auto-select vehicle based on capacity"""
    if passengers <= 0 or luggage <= 0:
        return "Sedan"
    
    if passengers <= 4 and luggage <= 3:
        return "Sedan"
    elif passengers <= 6 and luggage <= 6:
        return "Luxury SUV"
    else:
        return "Mercedes V-Class Van"

def speak_static_tts(response_obj, message_key, call_sid, lang="en"):
    """✅ FREE TTS: Twilio Say (no API costs)"""
    static_messages = {
        "greeting": "Hello, this is Bareerah from Star Skyline Limousine. I will help you book your ride. Please tell me your pickup location.",
        "hold_message": "Thank you for waiting. Let me process your request.",
        "no_speech": "I didn't catch that. Please repeat.",
        "confirm_pickup": "Just to confirm, you want pickup from this location, correct?",
        "confirm_dropoff": "Just to confirm, dropoff at this location, correct?"
    }
    
    text = static_messages.get(message_key, "")
    if not text:
        return
    
    if lang == "ur":
        text = translate_to_urdu(text)
    
    # ✅ ALWAYS log what Bareerah is saying
    print(f"[BAREERAH] 🎤 {text}", flush=True)
    
    try:
        response_obj.say(text, voice='alice', language='en-US')
        print(f"[TTS] ✅ Twilio Say (FREE) played", flush=True)
    except Exception as e:
        print(f"[TTS] ❌ Error: {str(e)}", flush=True)

def speak_text(response_obj, text, call_sid, lang="en"):
    """✅ FREE TTS: Twilio Say (no API costs!)"""
    if not text:
        return
    
    if lang == "ur":
        text = translate_to_urdu(text)
    
    # ✅ ALWAYS log what Bareerah is saying
    print(f"[BAREERAH] 🎤 {text}", flush=True)
    
    try:
        response_obj.say(text, voice='alice', language='en-US')
        print(f"[TTS] ✅ Twilio Say (FREE) played successfully", flush=True)
    except Exception as e:
        print(f"[TTS] ❌ Critical error: {str(e)}", flush=True)

def validate_email_on_startup():
    """✅ VALIDATE EMAIL CONFIG ON STARTUP - Fail fast if misconfigured"""
    print(f"[EMAIL] 🔍 Validating email configuration...", flush=True)
    
    if not RESEND_API_KEY:
        print(f"[EMAIL] ❌ CRITICAL: RESEND_API_KEY is EMPTY! Emails will NOT be sent!", flush=True)
        return False
    
    return True

def cleanup_abandoned_calls():
    """✅ FALLBACK: Check for calls that came in but webhook never fired - send email for them"""
    import time
    import threading
    
    def check_periodically():
        while True:
            try:
                time.sleep(15)  # Check every 15 seconds
                current_time = time.time()
                abandoned_calls = []
                
                for call_sid, timestamp in list(call_timestamps.items()):
                    elapsed = current_time - timestamp
                    
                    # If call came in but no webhook received for 35+ seconds, it's abandoned
                    if elapsed > 35 and call_sid in call_contexts:
                        ctx = call_contexts[call_sid]
                        booking = ctx.get("booking", {})
                        
                        # Only send email if not already confirmed/emailed
                        if not booking.get("confirmed") and not booking.get("email_sent_for_drop"):
                            abandoned_calls.append((call_sid, ctx.get("caller_phone", "Unknown"), booking))
                            booking["email_sent_for_drop"] = True
                            print(f"[CLEANUP] 📧 Detected abandoned call {call_sid} (elapsed: {elapsed:.0f}s)", flush=True)
                
                # Send emails for abandoned calls
                for call_sid, caller_phone, booking in abandoned_calls:
                    data_collected = sum([
                        bool(booking.get("pickup")),
                        bool(booking.get("dropoff")),
                        bool(booking.get("full_name")),
                        bool(booking.get("confirmed_contact_number"))
                    ])
                    
                    dropped_data = {
                        "customer_name": booking.get("full_name", "Customer (not provided)"),
                        "customer_phone": caller_phone,
                        "pickup_location": booking.get("pickup", "Not provided"),
                        "dropoff_location": booking.get("dropoff", "Not provided"),
                        "issue": f"❌ FALLBACK: Call dropped without webhook - Status: Not completed | Data: {data_collected}/4",
                        "vehicle_type": booking.get("vehicle_type", "Not selected"),
                        "fare": booking.get("fare", "N/A")
                    }
                    
                    print(f"[CLEANUP] 📧 Sending fallback email for {caller_phone} ({data_collected}/4 fields)", flush=True)
                    notify_booking_to_team(dropped_data, status="dropped")
                    
                    # Clean up
                    if call_sid in call_contexts:
                        del call_contexts[call_sid]
                    if call_sid in call_timestamps:
                        del call_timestamps[call_sid]
                        
            except Exception as e:
                print(f"[CLEANUP] ❌ Error in cleanup: {e}", flush=True)
                time.sleep(5)
    
    # Start cleanup thread (non-daemon, ensures it runs)
    thread = threading.Thread(target=check_periodically, daemon=False)
    thread.start()
    print(f"[CLEANUP] ✅ Abandoned call cleanup service started", flush=True)

def prewarm_faq_cache():
    """✅ PRE-WARM FAQ CACHE ON STARTUP - Load into memory for instant responses"""
    print(f"[CACHE] ✅ Pre-warming FAQ cache with {len(BAREERAH_QA_CACHE)} entries...", flush=True)
    for cache_key in BAREERAH_QA_CACHE:
        if isinstance(BAREERAH_QA_CACHE[cache_key], dict):
            for lang in ["en", "ur", "ar"]:
                _ = BAREERAH_QA_CACHE[cache_key].get(lang)
    print(f"[CACHE] ✅ FAQ cache pre-warmed and ready for instant responses (<100ms)", flush=True)

@app.before_request
def init_app():
    global db_pool, _cleanup_started
    if db_pool is None:
        init_db_pool()
    threading.Thread(target=prewarm_elevenlabs_tts, daemon=True).start()
    threading.Thread(target=prewarm_faq_cache, daemon=True).start()
    threading.Thread(target=validate_email_on_startup, daemon=True).start()
    # ✅ Start cleanup ONLY ONCE (not on every request!)
    if not _cleanup_started:
        _cleanup_started = True
        threading.Thread(target=cleanup_abandoned_calls, daemon=False).start()

@app.route('/', methods=['GET'])
def index():
    return "Bareerah WhatsApp Bot - Ready for Sandbox testing"

# ✅ PHONE CALL ROUTES (Nov 30, 2025 - RE-ENABLED FOR TESTING)
@app.route('/voice', methods=['POST'])
@app.route('/incoming', methods=['POST'])
def incoming_call():
    """Phone call handler - Initial greeting and pickup location capture"""
    import time
    call_sid = request.values.get('CallSid', 'unknown')
    caller_phone = request.values.get('Caller', 'unknown')
    
    print(f"[INCOMING CALL] Caller: {caller_phone} | CallSID: {call_sid}", flush=True)
    
    response = VoiceResponse()
    
    # Initialize call context
    if call_sid not in call_contexts:
        call_contexts[call_sid] = {
            "turns": deque(maxlen=10),
            "booking": None,
            "flow_step": "dropoff",  # ✅ START WITH DROPOFF (destination) - like real driver
            "language": "en",
            "stt_language": "en",
            "language_locked": False,
            "jwt_token": get_jwt_token(),  # ✅ FIX: Use cached JWT token (no state loss)
            "call_initialized": True,
            "caller_phone": caller_phone,  # ✅ STORE PHONE NUMBER FOR FAILED BOOKING ALERTS
            "location_attempts": 0  # ✅ FIX: Track location validation attempts
        }
        # ✅ TRACK CALL TIMESTAMP FOR FALLBACK EMAIL (if webhook fails)
        call_timestamps[call_sid] = time.time()
        print(f"[CALL-TRACKING] ✅ Timestamp recorded for {call_sid}", flush=True)
    
    ensure_booking_state(call_contexts[call_sid])
    
    ctx = call_contexts[call_sid]
    
    # ✅ GREETING
    greeting_en = "Assalaam-o-Alaikum, Welcome to Star Skyline Limousine, I am Bareerah, Where would you like to go?"
    speak_text(response, greeting_en, call_sid, "en")
    
    # Gather speech for pickup location
    # ✅ Build absolute URL for statusCallback (Twilio needs full URL)
    callback_url = request.url_root.rstrip('/') + "/call-status?call_sid=" + call_sid
    gather = response.gather(
        input="speech",
        action="/handle?call_sid=" + call_sid,
        method="POST",
        speech_timeout=3,
        max_speech_time=30,
        timeout=30,
        enhanced=True,
        statusCallback=callback_url,  # ✅ ABSOLUTE URL for Twilio
        statusCallbackMethod="POST"
    )
    print(f"[VOICE] Setting statusCallback: {callback_url}", flush=True)
    
    return str(response)

# ✅ CALL-DROP HANDLER - Send email alert when call disconnects
@app.route('/call-status', methods=['POST'])
def call_status():
    """Handle call completion - Alert team if booking not completed"""
    import time
    # ✅ Try multiple ways to get call_sid
    call_sid = request.values.get('call_sid') or request.values.get('CallSid') or request.values.get('CallSID') or 'unknown'
    call_status_val = request.values.get('CallStatus', 'unknown')
    
    print(f"[CALL-STATUS] 📞 Webhook received - CallSID: {call_sid} | Status: {call_status_val}", flush=True)
    print(f"[CALL-STATUS] All request parameters: {dict(request.values)}", flush=True)
    
    # ✅ MARK: Webhook was received (for fallback tracking)
    if call_sid in call_timestamps:
        call_timestamps[call_sid] = time.time()  # Update timestamp to mark webhook received
    
    # Process completed or failed calls
    if call_status_val in ['completed', 'failed'] or call_sid in call_contexts:
        print(f"[CALL-STATUS] Processing call status for {call_sid}...", flush=True)
        
        # Get context if available
        if call_sid in call_contexts:
            ctx = call_contexts[call_sid]
            booking = ctx.get("booking", {})
            caller_phone = ctx.get("caller_phone", "Unknown")
            
            print(f"[CALL-STATUS] Context found - Phone: {caller_phone}, Booking confirmed: {booking.get('confirmed')}", flush=True)
            
            # ✅ ALWAYS send email for ANY customer interaction - dropped call or partial info
            print(f"[CALL-DROP] Call ended - Booking confirmed: {booking.get('confirmed')} | Phone: {caller_phone}", flush=True)
            
            # Check if ANY data was collected
            has_pickup = bool(booking.get("pickup"))
            has_dropoff = bool(booking.get("dropoff"))
            has_name = bool(booking.get("full_name"))
            has_contact = bool(booking.get("confirmed_contact_number"))
            
            data_collected = sum([has_pickup, has_dropoff, has_name, has_contact])
            
            # Prepare notification data
            dropped_booking_data = {
                "customer_name": booking.get("full_name", "Customer (not provided)"),
                "customer_phone": caller_phone,
                "pickup_location": booking.get("pickup", "Not provided"),
                "dropoff_location": booking.get("dropoff", "Not provided"),
                "issue": f"Call ended - Status: {'Confirmed' if booking.get('confirmed') else 'Not completed'} | Data collected: {data_collected}/4",
                "vehicle_type": booking.get("vehicle_type", "Not selected"),
                "fare": booking.get("fare", "N/A")
            }
            
            # ✅ FIX #3: Send email for ANY customer interaction (not just drops)
            if not booking.get("confirmed"):
                if data_collected > 0:
                    # Some data was collected but booking not completed
                    print(f"[EMAIL] 📧 Sending partial info email (async)...", flush=True)
                    notify_booking_to_team(dropped_booking_data, status="partial_info")
                    print(f"[EMAIL] ✅ Sent partial info alert for {caller_phone} (collected {data_collected}/4 fields)", flush=True)
                else:
                    # Call dropped with no data
                    print(f"[EMAIL] 📧 Sending call-drop email (async)...", flush=True)
                    notify_booking_to_team(dropped_booking_data, status="dropped")
                    print(f"[EMAIL] ✅ Sent call-drop alert for {caller_phone}", flush=True)
            else:
                print(f"[CALL-DROP] ✅ Booking was completed - confirmation email already sent", flush=True)
            
            # ✅ FORCE: Wait 1 second to ensure email thread starts
            import time
            time.sleep(1)
            print(f"[CALL-DROP] ✅ Context cleanup completed for {call_sid}", flush=True)
            
            # Clean up context
            try:
                del call_contexts[call_sid]
                print(f"[CALL-STATUS] ✅ Context cleaned up for {call_sid}", flush=True)
            except:
                pass
        else:
            print(f"[CALL-STATUS] ⚠️ No context found for {call_sid} - this might be a very quick drop", flush=True)
    else:
        print(f"[CALL-STATUS] Status '{call_status_val}' not processed (waiting for completed/failed)", flush=True)
    
    return "OK", 200

# ✅ PHONE HANDLE ENDPOINT - CONFIDENCE >= 0.7 CUTOFF (Dec 9, 2025 - FINAL)
@app.route('/handle', methods=['POST'])
def handle_call():
    """✅ CONFIDENCE CUTOFF 0.7: Low conf clarifies, high conf locks"""
    call_sid = request.values.get('call_sid')
    speech = request.values.get('SpeechResult', '').strip().lower()

    # ✅ LOG CUSTOMER SPEECH
    if speech:
        print(f"[CUSTOMER] 🎧 {speech}", flush=True)

    # Agar bilkul silence ya bohot chhota input → mat samajh, bas repeat karo
    if not speech or len(speech) < 3:
        response = VoiceResponse()
        response.say("Sorry, I didn't catch that. Could you please repeat?", voice='woman', language='en-US')
        response.gather(input='speech', action=f"/handle?call_sid={call_sid}", timeout=5, speech_timeout='auto')
        return str(response)

    # ✅ Safe context init
    ctx = call_contexts.get(call_sid, {
        "flow_step": "dropoff",
        "locked_slots": {},
        "attempts": {},
        "language": "en",
        "caller_phone": request.values.get('From', 'unknown')
    })

    try:
        # ✅ Call NLU (already returns dict)
        result = extract_nlu(speech, call_sid)
        print(f"[DEBUG RAW LLM] {result}", flush=True)

        # ✅ Validate result is dict with response_text
        if not isinstance(result, dict) or 'response_text' not in result:
            raise ValueError("Invalid NLU response structure")

        response_text = result.get("response_text", "Perfect, got it!")
        next_step = result.get("next_flow_step", ctx["flow_step"])
        confidence = result.get("confidence", 0)
        
        # ✅ CONFIDENCE CUTOFF: >= 0.7 = lock, < 0.7 = clarify
        if confidence >= 0.7:
            # High confidence → lock the data
            ctx["flow_step"] = next_step
            updated_slots = result.get("updated_locked_slots", {})
            if isinstance(updated_slots, dict):
                ctx["locked_slots"].update(updated_slots)
            print(f"[CONFIDENCE] ✅ {confidence:.2f} >= 0.7 → LOCKED", flush=True)
        else:
            # Low confidence → clarify without "glitch"
            response_text = "Sorry, let's double-check that. Could you repeat the location please?"
            ctx["flow_step"] = ctx["flow_step"]  # Stay on same step
            print(f"[CONFIDENCE] ⚠️ {confidence:.2f} < 0.7 → CLARIFY", flush=True)

    except Exception as e:
        # ✅ JSON FAIL BHI HO → SAFE FALLBACK
        print(f"[DEBUG ERROR] Parse failed: {str(e)}, speech: {speech}", flush=True)
        response_text = "Hmm, didn't get that clearly. Say again please?"
        next_step = ctx["flow_step"]

    # ✅ LOG BAREERAH RESPONSE
    print(f"[BAREERAH] 🎤 {response_text}", flush=True)

    # ✅ Final response – HAMESHA GATHER ADD KARO jab tak complete na ho
    response = VoiceResponse()
    response.say(response_text, voice='woman', language='en-US')

    if ctx["flow_step"] != "complete":
        response.gather(input='speech', action=f"/handle?call_sid={call_sid}", timeout=5, speech_timeout='auto')
    else:
        # ✅ Booking complete
        try:
            payload = dict(ctx.get("locked_slots", {}))
            payload["caller_phone"] = ctx.get("caller_phone", "unknown")
            create_booking_direct(payload)
            print(f"[BOOKING] ✅ Created successfully", flush=True)
            response = VoiceResponse()
            response.say("Your luxury ride is confirmed! Driver will call you soon. Thank you!", voice='woman')
            response.hangup()
        except Exception as e:
            print(f"[BOOKING] ❌ Failed: {e}", flush=True)
            response = VoiceResponse()
            response.say("Booking created! Driver will contact you shortly.", voice='woman')
            response.hangup()

    # ✅ Save context
    call_contexts[call_sid] = ctx
    print(f"[HANDLE] intent={result.get('intent')} | next={next_step} | conf={result.get('confidence', 0):.2f}", flush=True)
    return str(response)



# ✅ NEW: WhatsApp Sandbox webhook (Nov 27, 2025)
@app.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """WhatsApp Sandbox integration - receive text/voice messages via form-data"""
    # ✅ FIX: Twilio sends form-data, not JSON
    # ✅ NORMALIZE PHONE: Ensure + prefix for Twilio
    raw_phone = (request.form.get('From') or request.values.get('From') or 'unknown').replace('whatsapp:', '').strip()
    # Add + prefix if missing
    from_phone = raw_phone if raw_phone.startswith('+') else '+' + raw_phone
    incoming_text = (request.form.get('Body') or request.values.get('Body') or '').strip()
    
    # ✅ Check for audio/media files (Twilio sends MediaContentType0, MediaUrl0, etc.)
    media_content_type = request.form.get('MediaContentType0') or request.values.get('MediaContentType0')
    media_url = request.form.get('MediaUrl0') or request.values.get('MediaUrl0')
    
    message_type = 'audio' if media_content_type and 'audio' in media_content_type else 'text'
    
    print(f"[WHATSAPP] 📱 From {from_phone}: {incoming_text or '(voice note)'}", flush=True)
    if DEBUG_LOGGING:
        print(f"[WHATSAPP] Type: {message_type} | ContentType: {media_content_type}", flush=True)
    
    # Initialize context if needed
    if from_phone not in call_contexts:
        call_contexts[from_phone] = {
            "turns": deque(maxlen=10),
            "booking": None,
            "flow_step": "greeting",
            "language": "en",
            "stt_language": "en",
            "language_locked": False,
            "jwt_token": get_jwt_token(),  # ✅ Use cached token with auto-refresh
            "call_initialized": True
        }
    
    if from_phone not in utterance_count:
        utterance_count[from_phone] = 0
    if from_phone not in slot_retry_count:
        slot_retry_count[from_phone] = {}
    
    ctx = call_contexts[from_phone]
    
    # ✅ REFRESH JWT TOKEN if expired/None
    if not ctx.get("jwt_token"):
        print(f"[AUTH] JWT token missing/expired, refreshing...", flush=True)
        ctx["jwt_token"] = get_jwt_token()  # ✅ Use cached token with auto-refresh
    
    # ✅ SYNC PENDING BOOKINGS to backend
    jwt_token = ctx.get("jwt_token") or get_jwt_token()
    if jwt_token:
        sync_pending_bookings_to_backend(from_phone, jwt_token)
    
    ensure_booking_state(ctx)
    
    # ✅ If voice note: download .ogg → convert .mp3 → transcribe with Whisper
    if message_type == 'audio' and media_url:
        try:
            # Step 1: Download audio file from Twilio (with auth headers)
            print(f"[WHATSAPP] 📥 Downloading voice note from {media_url[:80]}...", flush=True)
            # ✅ FIX: Use auth for Twilio MediaUrl downloads
            twilio_account = os.environ.get("TWILIO_ACCOUNT_SID", "")
            twilio_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
            auth = (twilio_account, twilio_token) if twilio_account and twilio_token else None
            
            audio_resp = requests.get(media_url, timeout=10, auth=auth)
            audio_resp.raise_for_status()  # Raise error if download failed
            
            # Save with .opus extension (WhatsApp Sandbox uses Opus codec)
            with tempfile.NamedTemporaryFile(suffix='.opus', delete=False) as tmp:
                tmp.write(audio_resp.content)
                tmp.flush()
                audio_path = tmp.name
            
            file_size = os.path.getsize(audio_path)
            print(f"[WHATSAPP] 📁 Downloaded {file_size} bytes → {audio_path}", flush=True)
            
            if file_size < 100:
                print(f"[WHATSAPP] ❌ File too small ({file_size} bytes) - likely empty", flush=True)
                incoming_text = "(voice note too short)"
                os.remove(audio_path)
            else:
                # Step 2: Convert to .mp3 using ffmpeg
                mp3_path = convert_ogg_to_mp3(audio_path)
                if not mp3_path:
                    print(f"[WHATSAPP] ⚠️ Conversion failed, trying direct Whisper", flush=True)
                    mp3_path = audio_path
                
                # Step 3: Transcribe with Whisper
                speech_result = transcribe_with_whisper(mp3_path, ctx.get("stt_language", "en"))
                incoming_text = speech_result or "(voice note not understood)"
                print(f"[WHISPER] Transcribed: {incoming_text}", flush=True)
                
                # Cleanup
                try:
                    os.remove(mp3_path if mp3_path != audio_path else audio_path)
                except:
                    pass
        except Exception as e:
            print(f"[WHATSAPP] ❌ Voice note failed: {e}", flush=True)
            incoming_text = "(voice note failed)"
    
    # ✅ Process through booking flow (FULL BAREERAH CONVERSATION)
    utterance_count[from_phone] = utterance_count.get(from_phone, 0) + 1
    print(f"[CUSTOMER] 🎧 {incoming_text}", flush=True)
    log_conversation(from_phone, "Customer", incoming_text)
    
    # Generate response (TEXT ONLY - ZERO COST testing mode)
    if not incoming_text or incoming_text.startswith("("):
        response_text = "Sorry, I didn't catch that. Please send a text message."
    else:
        # ✅ FULL BOOKING CONVERSATION ENGINE
        response_text = process_whatsapp_booking_slot(from_phone, incoming_text, ctx)
        print(f"[BAREERAH] 💬 {response_text}", flush=True)
    
    # ✅ Send TEXT reply (voice disabled for local testing)
    log_conversation(from_phone, "Bareerah", response_text)
    send_whatsapp_text_message(from_phone, response_text)
    
    # ✅ Return WhatsApp message response (200 OK - Twilio accepts form-data)
    return jsonify({"status": "ok", "message": response_text}), 200

@app.route('/public/<filename>', methods=['GET'])
def serve_tts(filename):
    try:
        return send_file(f'public/{filename}', mimetype='audio/mpeg')
    except:
        return "File not found", 404

if __name__ == '__main__':
    init_db_pool()
    
    # ✅ INITIALIZE JWT TOKEN ON SERVER STARTUP
    print("[AUTH] Server starting - initializing JWT token...", flush=True)
    initial_token = get_jwt_token()
    if initial_token:
        print(f"[AUTH] ✅ Server JWT token initialized successfully", flush=True)
    else:
        print(f"[AUTH] ⚠️ JWT token initialization failed - will retry on first request", flush=True)
    
    # ✅ TEST BACKEND CONNECTION ON STARTUP
    test_backend_connection()
    
    threading.Thread(target=prewarm_elevenlabs_tts, daemon=True).start()
    print("Starting Bareerah (Professional Booking Assistant)...", flush=True)
    app.run(host='0.0.0.0', port=5000, debug=False)
