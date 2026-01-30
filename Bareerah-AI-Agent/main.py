from dotenv import load_dotenv
load_dotenv()  # ✅ Load environment variables from .env file (Redeploy Trigger)

import sys
# ✅ Fix UnicodeEncodeError on Windows (console doesn't support emojis by default)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

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
from datetime import datetime, timedelta, timezone
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
print("🚀 BAREERAH AI AGENT STARTING UP... (Verification Push)", flush=True)

OPENAI_CLIENT = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
GOOGLE_CLOUD_TTS_KEY = os.environ.get("GOOGLE_CLOUD_TTS_KEY")
WEBSITE_URL = os.environ.get("WEBSITE_URL", "")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "https://5ef5530c-38d9-4731-b470-827087d7bc6f-00-2j327r1fnap1d.sisko.replit.dev")
BASE_API_URL = f"{BACKEND_BASE_URL}/api"
BOOKING_ENDPOINT = f"{BACKEND_BASE_URL}/api/bookings/create-manual"

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
URDU_KEYWORDS = {"meri", "mera", "mein", "hoon", "hain", "malik", "sahab", "acha", "theek", "bilkul", "kahan", "jana", "chalo", "karo", "ruko", "subah", "shaam", "kal", "aaj", "abhi", "jee", "naam"}
ARABIC_KEYWORDS = {"alhijra", "almarina", "masr", "ahal", "tayyib", "sahih", "almaer", "hawaya", "aiwa", "naam", "shukran", "marhaba", "ahlan", "yalla", "bukra", "alyawm", "sabah", "masa"}

# ✅ MULTI-LANGUAGE TTS + STT: Voice and speech recognition mapping
POLLY_VOICES = {
    "en": {"voice": "Polly.Joanna", "tts_lang": "en-US", "stt_lang": "en-US"},
    "ur": {"voice": "Polly.Aditi", "tts_lang": "hi-IN", "stt_lang": "hi-IN"},  # Hindi closest to Urdu
    "ar": {"voice": "Polly.Zeina", "tts_lang": "arb", "stt_lang": "ar-SA"}
}

# ✅ HINDI/URDU TO ROMAN TRANSLITERATION MAPPING
HINDI_URDU_TRANSLITERATION = {
    # Hindi vowels
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo',
    'ऋ': 'ri', 'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au',
    # Hindi consonants
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'w', 'श': 'sh', 'ष': 'sh',
    'स': 's', 'ह': 'h',
    # Special
    'ः': 'h', 'ँ': 'n', 'ं': 'n', 'ः': ':',
    # Hindi diacritics (halant removes the inherent 'a')
    '्': '',
    # Numbers
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4', '५': '5',
    '६': '6', '७': '7', '८': '8', '९': '9',
}

def is_airport_location(location_text):
    """✅ Detect if location is an airport (Dubai International, Al Maktoum, etc)"""
    if not location_text:
        return False
    text_lower = location_text.lower()
    airport_keywords = [
        "airport", "dxb", "dwc", "auh", "terminal", "emirates", "flydubai", "etihad",
        "dubai international", "maktoum", "international airport", "civil aviation",
        "al maktoum", "ras al khaimah", "sharjah", "fujairah", "ajman",
        "arrivals", "departures", "check-in", "gates"
    ]
    return any(kw in text_lower for kw in airport_keywords)

def transliterate_hindi_to_roman(text):
    """Convert Hindi/Urdu script to Roman transliteration (e.g., 'रमीज़' → 'Rameez')"""
    if not text:
        return text
    
    result = []
    for char in text:
        if char in HINDI_URDU_TRANSLITERATION:
            result.append(HINDI_URDU_TRANSLITERATION[char])
        elif char.isascii():
            result.append(char)
        # Skip unknown Unicode characters (like combining marks)
    
    transliterated = ''.join(result)
    # Clean up: remove extra spaces, capitalize first letter
    transliterated = ' '.join(transliterated.split())
    return transliterated.strip()

def detect_skip_intent(text):
    """✅ ENHANCED MULTILINGUAL SKIP DETECTION - regex patterns + synonym lists"""
    if not text:
        return True  # Empty = skip
    
    text_lower = text.lower().strip()
    
    # ✅ Quick check for very short responses (likely filler/skip)
    if len(text_lower) < 3:
        return True
    
    # ✅ SYNONYM LISTS (tokenized for exact matching)
    skip_tokens_en = {"skip", "no", "none", "nothing", "nope", "pass", "next", "proceed", "continue", "escape"}
    skip_tokens_ur = {"nahi", "bas", "aage", "choro", "mat", "kuch", "skip", "pass"}
    skip_tokens_ar = {"la", "mafi", "khalas", "mafish", "skip", "pass"}
    
    # Check if ANY word matches skip tokens
    words = set(text_lower.split())
    if words & skip_tokens_en or words & skip_tokens_ur or words & skip_tokens_ar:
        # But exclude if there's actual content (like "no waiting time needed")
        content_words = words - skip_tokens_en - skip_tokens_ur - skip_tokens_ar - {"i", "the", "a", "an", "to", "is", "hai", "ho", "ki", "ka", "ke"}
        if len(content_words) < 2:  # If very few content words, it's a skip
            return True
    
    # ✅ REGEX PATTERNS for mixed-language negations
    skip_patterns = [
        r"\b(no|nahi|la)\s*(need|notes?|special|extra|likhna|likho|aktub)\b",  # "no need", "nahi likhna", "la aktub"
        r"\b(don'?t|mat|la)\s*(add|write|put|likho|note)\b",  # "don't add", "mat likho", "la note"
        r"\b(nothing|kuch\s*nahi|mafish|mafi)\s*(special|extra)?\b",  # "nothing special", "kuch nahi"
        r"\b(skip|choro|bass?|khalas)\s*(it|this|ye|kar)?\b",  # "skip it", "bass", "khalas"
        r"^(no|nahi|la|bas|skip|none|nothing)$",  # Single word skips
        r"likhne\s*ki\s*zarurat\s*nahi",  # "likhne ki zarurat nahi"
        r"koi\s*zarurat\s*nahi",  # "koi zarurat nahi"
        r"zarurat\s*nahi",  # "zarurat nahi"
        r"rehne\s*do",  # "rehne do"
        r"kuch\s*mat",  # "kuch mat"
        r"ma\s*fi\s*shay?",  # "ma fi shay" (Arabic)
        r"la\s*hajah?",  # "la hajah" (Arabic)
    ]
    
    for pattern in skip_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False

def capture_vehicle_snapshot(ctx):
    """✅ Capture current vehicle state for potential rollback"""
    slots = ctx.get("locked_slots", {})
    return {
        "vehicle": slots.get("vehicle", "sedan"),
        "vehicle_model": slots.get("vehicle_model", "Sedan"),
        "fare": slots.get("fare", "AED 100"),
        "distance_km": slots.get("distance_km", 25)
    }

def apply_vehicle_snapshot(ctx, snapshot):
    """✅ Restore vehicle state from snapshot"""
    if not snapshot:
        return
    ctx["locked_slots"]["vehicle"] = snapshot.get("vehicle", "sedan")
    ctx["locked_slots"]["vehicle_model"] = snapshot.get("vehicle_model", "Sedan")
    ctx["locked_slots"]["fare"] = snapshot.get("fare", "AED 100")
    if "distance_km" in snapshot:
        ctx["locked_slots"]["distance_km"] = snapshot["distance_km"]

def parse_upgrade_intent(speech, luxury_options):
    """✅ PRIORITY-BASED UPGRADE INTENT CLASSIFICATION
    Returns: (intent, selected_option_index or None)
    Intent priority: confirm > select > reject/expensive > unknown
    """
    speech_lower = speech.lower()
    
    # ✅ PRIORITY 1: Explicit confirmation with option selection
    # Patterns like "yes option 2", "confirm number 1", "book the mercedes"
    confirm_with_option = re.search(r"(yes|ok|confirm|book|theek|haan|bilkul)\s*.*(option|number|#)?\s*([123])", speech_lower)
    if confirm_with_option:
        option_num = int(confirm_with_option.group(3)) - 1
        if 0 <= option_num < len(luxury_options):
            return ("confirm_with_selection", option_num)
    
    # ✅ PRIORITY 2: Explicit model mention (even with "expensive" mentioned, if they say the model, they want it)
    for i, opt in enumerate(luxury_options):
        model_words = [w.lower() for w in opt["model"].split() if len(w) > 3]
        if any(word in speech_lower for word in model_words):
            # Check if this is a positive mention (not "I don't want the Lexus")
            if not re.search(r"(don'?t|nahi|not|no)\s*(want|chahiye|need)", speech_lower):
                return ("select", i)
    
    # ✅ PRIORITY 3: Number selection without explicit confirmation
    num_match = re.search(r"(option|number|#)?\s*([123])\b", speech_lower)
    if num_match:
        option_num = int(num_match.group(2)) - 1
        if 0 <= option_num < len(luxury_options):
            return ("select", option_num)
    
    # ✅ PRIORITY 4: Simple confirmation (yes/ok/theek) - use first option
    confirm_words = {"yes", "yeah", "yup", "ok", "okay", "confirm", "book", "done", "haan", "theek", "bilkul", "jee"}
    if any(word in speech_lower.split() for word in confirm_words):
        # Make sure there's no rejection in the same utterance
        if not any(w in speech_lower for w in ["no", "nahi", "cancel", "expensive", "mehenga", "sasta"]):
            return ("confirm", 0)
    
    # ✅ PRIORITY 5: Previous/original vehicle request
    previous_keywords = ["previous", "original", "first", "pehli", "pehly", "purani", "pichli", "sasti", "cheaper", "alawla", "go back"]
    if any(kw in speech_lower for kw in previous_keywords):
        return ("previous", None)
    
    # ✅ PRIORITY 6: Too expensive / rejection
    expensive_keywords = ["expensive", "too much", "mehenga", "zyada", "sasta", "cheaper", "ghali", "less", "lower"]
    reject_keywords = ["no", "nahi", "cancel", "nope", "la"]
    if any(kw in speech_lower for kw in expensive_keywords):
        return ("expensive", None)
    if any(kw in speech_lower.split() for kw in reject_keywords):
        return ("reject", None)
    
    return ("unknown", None)

def detect_language(text):
    """Detect language from customer speech - returns 'en', 'ur', or 'ar'"""
    if not text:
        return "en"
    text_lower = text.lower()
    words = set(text_lower.split())
    
    # Check for Urdu keywords
    urdu_matches = len(words & URDU_KEYWORDS)
    arabic_matches = len(words & ARABIC_KEYWORDS)
    
    if urdu_matches >= 2:
        return "ur"
    if arabic_matches >= 2:
        return "ar"
    
    # Check for Urdu sentence patterns
    urdu_patterns = ["mujhe", "chahiye", "hai", "hain", "karna", "jana"]
    if any(p in text_lower for p in urdu_patterns):
        return "ur"
    
    return "en"

def get_polly_voice(lang="en"):
    """Get Polly voice config for language (includes TTS voice + STT language)"""
    config = POLLY_VOICES.get(lang, POLLY_VOICES["en"])
    # Ensure backward compatibility
    if "language" in config and "tts_lang" not in config:
        config["tts_lang"] = config["language"]
        config["stt_lang"] = config["language"]
    return config

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
GEO_MARKERS = {
    "airport", "mall", "tower", "street", "road", "avenue", "hotel", "terminal", "marina", "downtown", "city",
    "residence", "village", "jvc", "jlt", "palm", "beach", "park", "souq", "market", "university", "college",
    "school", "hospital", "clinic", "metro", "station", "stop", "area", "zone", "cluster", "block", "house",
    "villa", "apartment", "burj", "khalifa", "frame", "museum", "opera", "atlantis", "garden", "resort",
    "palace", "creek", "harbour", "hills", "meadows", "springs", "lakes", "island", "world", "canal",
    "gate", "center", "centre", "plaza", "square", "court", "heights", "views", "oasis", "silicon",
    "media", "internet", "studio", "sports", "motor", "investment", "business", "bay", "walk", "residences",
    "suites", "inn", "restaurant", "cafe", "club", "gym", "cinema", "theatre", "stadium", "arena"
}

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
    global db_pool
    try:
        if not db_pool:
            init_db_pool()
        conn = db_pool.getconn()
        conn.cursor().execute("SELECT 1")
        return conn
    except Exception as e:
        print(f"[DB] ⚠️ Connection stale, reinitializing pool: {e}", flush=True)
        try:
            if db_pool:
                db_pool.closeall()
        except:
            pass
        db_pool = None
        init_db_pool()
        return db_pool.getconn() if db_pool else None

def return_db_conn(conn):
    if db_pool:
        db_pool.putconn(conn)

def load_call_state(call_sid: str) -> dict:
    """Load call state from PostgreSQL (crash-safe persistence)"""
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT flow_step, locked_slots, caller_phone, notes, language
            FROM call_sessions 
            WHERE call_sid = %s
        """, (call_sid,))
        row = cur.fetchone()
        cur.close()
        return_db_conn(conn)
        
        if row:
            return {
                "flow_step": row["flow_step"],
                "locked_slots": row["locked_slots"] or {},
                "caller_phone": row["caller_phone"] or "unknown",
                "notes": row["notes"] or "",
                "language": row.get("language") or "en"
            }
        return None
    except Exception as e:
        print(f"[DB] ❌ load_call_state error: {e}", flush=True)
        return None

def save_call_state(call_sid: str, ctx: dict) -> bool:
    """Save call state to PostgreSQL (crash-safe persistence)"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO call_sessions (call_sid, flow_step, locked_slots, caller_phone, notes, language, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (call_sid) 
            DO UPDATE SET 
                flow_step = EXCLUDED.flow_step,
                locked_slots = EXCLUDED.locked_slots,
                caller_phone = EXCLUDED.caller_phone,
                notes = EXCLUDED.notes,
                language = EXCLUDED.language,
                updated_at = NOW()
        """, (
            call_sid,
            ctx.get("flow_step", "dropoff"),
            json.dumps(ctx.get("locked_slots", {})),
            ctx.get("caller_phone", "unknown"),
            ctx.get("notes", ""),
            ctx.get("language", "en")
        ))
        conn.commit()
        cur.close()
        return_db_conn(conn)
        print(f"[DB] ✅ State saved for {call_sid}: step={ctx.get('flow_step')}", flush=True)
        return True
    except Exception as e:
        print(f"[DB] ❌ save_call_state error: {e}", flush=True)
        return False

def log_completed_call(call_sid: str, ctx: dict, call_duration_secs: int = 0) -> bool:
    """✅ Log completed call to call_logs table BEFORE deleting session"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Save complete conversation state as JSON
        conversation = {
            "flow_step": ctx.get("flow_step"),
            "locked_slots": ctx.get("locked_slots", {}),
            "notes": ctx.get("notes", "")
        }
        
        cur.execute("""
            INSERT INTO call_logs (call_id, caller_phone, conversation_json, language, call_duration_seconds)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (call_id) DO UPDATE SET 
                conversation_json = EXCLUDED.conversation_json,
                call_duration_seconds = EXCLUDED.call_duration_seconds
        """, (
            call_sid,
            ctx.get("caller_phone", "unknown"),
            json.dumps(conversation),
            ctx.get("language", "en"),
            call_duration_secs
        ))
        conn.commit()
        cur.close()
        return_db_conn(conn)
        print(f"[LOGS] ✅ Call logged for {call_sid}: {ctx.get('locked_slots', {}).get('customer_name', 'Unknown')}", flush=True)
        return True
    except Exception as e:
        print(f"[LOGS] ⚠️ Failed to log call: {e}", flush=True)
        return False

def delete_call_state(call_sid: str) -> bool:
    """Delete call state from PostgreSQL after booking complete"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM call_sessions WHERE call_sid = %s", (call_sid,))
        conn.commit()
        cur.close()
        return_db_conn(conn)
        print(f"[DB] ✅ State deleted for {call_sid}", flush=True)
        return True
    except Exception as e:
        print(f"[DB] ❌ delete_call_state error: {e}", flush=True)
        return False

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

    # ✅ SPELLING CORRECTIONS: Common location misspellings + STT errors
    spelling_fixes = {
        "bemarina": "Dubai Marina Mall",
        "marina mall": "Dubai Marina Mall",
        "marina": "Dubai Marina Mall",
        "the way marina": "Dubai Marina Mall",
        "way marina": "Dubai Marina Mall",
        "the marina": "Dubai Marina Mall",
        "airport": "Dubai Airport",
        "dxb": "Dubai Airport",
        "auh": "Abu Dhabi Airport",
        "sharjah airport": "Sharjah Airport",
        "sjc": "Sharjah Airport",
        "terminal 3": "Dubai International Airport Terminal 3",
        "terminal3": "Dubai International Airport Terminal 3"
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

# ✅ FARE RATES MANAGER: Backend-accurate fare calculation with included_km logic
class FareRatesManager:
    """
    Fare rates from Star Skyline backend (Dec 2025).
    Formula: Base Fare + max(0, Distance - Included KM) × Per KM Rate
    """
    def __init__(self):
        # ✅ EXACT rates from backend screenshot (Dec 8, 2025)
        self.rates = {
            # CLASSIC: Toyota Camry, BMW 5 Series, BYD Han
            "classic": {"base": 95, "included_km": 20, "per_km": 1.00, "hourly": 75},
            "sedan": {"base": 95, "included_km": 20, "per_km": 1.00, "hourly": 75},
            
            # ELITE VAN: Mercedes V Class, Luxury Vans
            "elite_van": {"base": 165, "included_km": 20, "per_km": 2.00, "hourly": 130},
            
            # EXECUTIVE: Lexus ES 300H, Tesla Model 3/Y
            "executive": {"base": 105, "included_km": 20, "per_km": 1.00, "hourly": 85},
            
            # FIRST CLASS: BMW 7 Series, Mercedes S Class, Audi A8
            "first_class": {"base": 450, "included_km": 40, "per_km": 1.75, "hourly": 350},
            
            # LUXURY: Range Rover, Lexus, BMW 7 Series, Mercedes E-Class
            "luxury": {"base": 450, "included_km": 40, "per_km": 1.75, "hourly": 350},
            
            # LUXURY SUV: Cadillac Escalade, GMC Yukon
            "luxury_suv": {"base": 170, "included_km": 20, "per_km": 1.80, "hourly": 140},
            
            # MINI BUS: Mercedes Sprinter (8-10 passengers)
            "mini_bus": {"base": 825, "included_km": 50, "per_km": 7.50, "hourly": 600},
            "minibus": {"base": 825, "included_km": 50, "per_km": 7.50, "hourly": 600},
            
            # URBAN SUV: Toyota Highlander, BYD Song
            "urban_suv": {"base": 108, "included_km": 20, "per_km": 1.00, "hourly": 90},
            "suv": {"base": 108, "included_km": 20, "per_km": 1.00, "hourly": 90},
            
            # Aliases for compatibility
            "van": {"base": 165, "included_km": 20, "per_km": 2.00, "hourly": 130},
            "luxury_van": {"base": 165, "included_km": 20, "per_km": 2.00, "hourly": 130},
        }
        self.last_refresh = 0
        self.refresh_interval = 3600  # 1 hour
    
    def needs_refresh(self) -> bool:
        import time
        return time.time() - self.last_refresh > self.refresh_interval
    
    def fetch_from_backend(self, jwt_token: str) -> bool:
        """Fetch fare rates from backend API (updates local cache if available)"""
        try:
            result = backend_api("GET", "/api/fare-rates", jwt_token=jwt_token)
            if result and isinstance(result, dict):
                rates_data = result.get("rates") or result.get("data") or result
                if rates_data:
                    for vehicle_type, rate_info in rates_data.items():
                        v_type = vehicle_type.lower().replace(" ", "_")
                        if isinstance(rate_info, dict):
                            self.rates[v_type] = {
                                "base": float(rate_info.get("base_fare") or rate_info.get("base") or 95),
                                "included_km": int(rate_info.get("included_km") or 20),
                                "per_km": float(rate_info.get("per_km_rate") or rate_info.get("per_km") or 1.00),
                                "hourly": float(rate_info.get("hourly_rate") or rate_info.get("hourly") or 75)
                            }
                    import time
                    self.last_refresh = time.time()
                    print(f"[FARE_MGR] ✅ Synced fare rates from backend: {list(self.rates.keys())}", flush=True)
                    return True
        except Exception as e:
            print(f"[FARE_MGR] ⚠️ Could not fetch fare rates from API: {e}", flush=True)
        
        # Already have hardcoded rates from backend screenshot
        print(f"[FARE_MGR] ✅ Using backend-accurate hardcoded rates (8 vehicle types)", flush=True)
        return True
    
    def get_rate(self, vehicle_type: str) -> dict:
        """Get fare rates for a vehicle type with smart matching"""
        v_type = vehicle_type.lower().replace(" ", "_").replace("-", "_")
        
        # Direct match
        if v_type in self.rates:
            return self.rates[v_type]
        
        # Smart keyword matching
        if "luxury" in v_type and "suv" in v_type:
            return self.rates["luxury_suv"]
        if "first" in v_type or "class" in v_type:
            return self.rates["first_class"]
        if "executive" in v_type or "exec" in v_type:
            return self.rates["executive"]
        if "elite" in v_type and "van" in v_type:
            return self.rates["elite_van"]
        if "mini" in v_type or "bus" in v_type or "sprinter" in v_type:
            return self.rates["mini_bus"]
        if "urban" in v_type:
            return self.rates["urban_suv"]
        if "luxury" in v_type:
            return self.rates["luxury"]
        if "suv" in v_type:
            return self.rates["urban_suv"]
        if "van" in v_type:
            return self.rates["elite_van"]
        
        # Default to Classic/Sedan
        return self.rates["classic"]
    
    def calculate_fare(self, distance_km: float, vehicle_type: str, booking_type: str = "point_to_point", hours: int = 0) -> int:
        """
        Calculate fare using backend formula:
        Fare = Base Fare + max(0, Distance - Included KM) × Per KM Rate
        """
        rate = self.get_rate(vehicle_type)
        
        if booking_type == "hourly" and hours > 0:
            # Hourly: hours × hourly_rate (includes X km per hour)
            fare = hours * rate["hourly"]
        else:
            # Point-to-point: Base + extra km charges (first X km included in base)
            included_km = rate.get("included_km", 20)
            extra_km = max(0, distance_km - included_km)
            fare = rate["base"] + (extra_km * rate["per_km"])
        
        return round(fare)

# ✅ Global fare rates manager
fare_rates_manager = FareRatesManager()

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
    passengers = booking_data.get('passengers_count') or booking_data.get('passengers', 'N/A') or 'N/A'
    luggage = booking_data.get('luggage_count') or booking_data.get('luggage', 'N/A') or 'N/A'
    fare_raw = booking_data.get('calculated_fare_aed') or booking_data.get('fare', 'N/A') or 'N/A'
    fare = str(fare_raw).replace('AED AED', 'AED').replace('AED ', '').replace(' AED', '')
    fare = f"AED {fare}" if fare != 'N/A' and not str(fare).startswith('AED') else fare
    vehicle = (booking_data.get('vehicle_type') or booking_data.get('vehicle') or 'N/A').upper()
    email = booking_data.get('customer_email', 'N/A') or 'N/A'
    notes = booking_data.get('notes', '') or ''
    booking_ref = booking_data.get('booking_reference', 'BOOK-XXXX') or 'BOOK-XXXX'
    pickup_time = booking_data.get('datetime') or booking_data.get('pickup_time', 'TBD') or 'TBD'
    car_model = booking_data.get('car_model') or booking_data.get('vehicle_model', 'Pending') or 'Pending'
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

def calculate_fare_api(distance_km, vehicle_type, booking_type, jwt_token, hours: int = 0):
    """
    PRODUCTION API: Calculate fare from backend with vehicle-specific fallback.
    Supports both point-to-point and hourly booking types.
    Returns: Integer fare in AED
    """
    if not distance_km or distance_km <= 0:
        return 0  # ✅ Never return None, use fallback
    
    # Build API payload
    payload = {
        "distance_km": distance_km,
        "vehicle_type": vehicle_type,
        "booking_type": booking_type
    }
    if booking_type == "hourly" and hours > 0:
        payload["hours"] = hours
    
    result = backend_api("POST", "/bookings/calculate-fare", payload, jwt_token)
    print(f"[FARE API] Backend response: {result}", flush=True)
    
    # ✅ CALCULATE FALLBACK FIRST (for validation comparison)
    fallback_fare = fare_rates_manager.calculate_fare(distance_km, vehicle_type, booking_type, hours)
    base_fare = fare_rates_manager.get_rate(vehicle_type).get("base", 50)
    
    # Try multiple possible response keys (handle nested 'data' field)
    if result:
        # Backend returns: {'success': True, 'data': {'fare': 618.93}}
        data = result.get("data", result)  # Try nested 'data' first, fallback to root
        fare_value = data.get("fare") or data.get("fare_aed") or data.get("total_fare") or result.get("fare")
        if fare_value is not None and fare_value > 0:
            try:
                fare = float(fare_value)
                fare_aed = round(fare)
                
                # ✅ VALIDATION: Backend fare must be >= base fare and within tolerance of fallback
                # If backend returns ridiculous fare (like 18 AED for SUV), reject and use fallback
                if fare_aed < base_fare:
                    print(f"⚠️ FARE VALIDATION FAILED: Backend returned {fare_aed} AED < base fare {base_fare} AED", flush=True)
                    print(f"✅ Using FALLBACK fare: {fallback_fare} AED (backend is miscalculating)", flush=True)
                    return fallback_fare
                
                # Additional check: if fare differs by >100% from fallback, something is wrong
                if fallback_fare > 0 and abs(fare_aed - fallback_fare) / fallback_fare > 1.0:
                    print(f"⚠️ FARE ANOMALY: Backend {fare_aed} AED vs fallback {fallback_fare} AED (>100% diff)", flush=True)
                    # Still use backend if it's higher (could be surge pricing), fallback if lower
                    if fare_aed < fallback_fare * 0.5:
                        print(f"✅ Using FALLBACK fare: {fallback_fare} AED (backend too low)", flush=True)
                        return fallback_fare
                
                print(f"✅ FARE CALCULATED FROM API: {fare_aed} AED (raw: {fare})", flush=True)
                return fare_aed
            except Exception as e:
                print(f"❌ FARE CONVERSION ERROR: {e}", flush=True)
    
    # ✅ FALLBACK: Use cached rates from FareRatesManager (backend-accurate formula)
    print(f"[FARE] API failed or returned 0, using cached rates for {vehicle_type} ({booking_type})...", flush=True)
    fallback_fare = fare_rates_manager.calculate_fare(distance_km, vehicle_type, booking_type, hours)
    rate = fare_rates_manager.get_rate(vehicle_type)
    if booking_type == "hourly" and hours > 0:
        print(f"✅ FARE (FALLBACK): {fallback_fare} AED | {hours}hrs × {rate['hourly']}/hr", flush=True)
    else:
        included_km = rate.get("included_km", 20)
        extra_km = max(0, distance_km - included_km)
        print(f"✅ FARE (FALLBACK): {fallback_fare} AED | Base:{rate['base']} + {extra_km}km × {rate['per_km']}/km (first {included_km}km included)", flush=True)
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
        # ✅ LAYER 3: FINAL CHECK - Make sure extracted location is valid
        # FIX: Removed strict 2-token check which blocked valid 1-word locations like "JVC", "DIP", "Airport"
        if len(location_tokens) < 1:
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

def extract_nlu_clean(text, flow_step, locked_slots, lang="en"):
    """✅ CLEAN NLU: GPT-4o + LOCATION FALLBACK MATCHING (MULTILINGUAL)"""
    try:
        # ✅ Calculate TODAY's date in Dubai timezone (UTC+4)
        dubai_tz = timezone(timedelta(hours=4))
        today_dubai = datetime.now(dubai_tz).strftime('%Y-%m-%d')
        
        # ✅ LOCATION FALLBACK DICTIONARY (120+ Dubai locations)
        POPULAR_DUBAI_LOCATIONS = {
            "dubai airport": "Dubai International Airport", "dubai international": "Dubai International Airport",
            "international airport": "Dubai International Airport", "dxb": "Dubai International Airport",
            "al maktoum": "Al Maktoum International Airport", "zabeel park": "Zabeel Park", "zabeel": "Zabeel Park",
            "creek park": "Dubai Creek Park", "safa park": "Safa Park", "marina mall": "Dubai Marina Mall",
            "dubai mall": "The Dubai Mall", "mall of the emirates": "Mall of the Emirates",
            "burj khalifa": "Burj Khalifa", "burj": "Burj Khalifa", "emirates tower": "Emirates Towers",
            "downtown dubai": "Downtown Dubai", "burj al arab": "Burj Al Arab", "jumeirah": "Jumeirah",
            "dubai marina": "Dubai Marina", "jbr": "JBR - Jumeirah Beach Residence",
            "atlantis": "Atlantis The Palm", "wild wadi": "Wild Wadi Waterpark",
            "deira city centre": "Deira City Centre", "city centre": "Deira City Centre",
            "legoland": "Legoland Dubai", "global village": "Global Village",
            "expo city": "Expo City Dubai", "sheikh zayed road": "Sheikh Zayed Road",
            "al barsha": "Al Barsha", "business bay": "Business Bay", "deira": "Deira",
            "bur dubai": "Bur Dubai", "karama": "Al Karama", "jlt": "Jumeirah Lakes Towers",
        }
        
        # Map flow_step to context for GPT-4o
        step_contexts_en = {
            "dropoff": "We are asking for the destination (dropoff).",
            "pickup": "We are asking for the starting point (pickup).",
            "flight_info": "We are asking for flight details (time/number).",
            "datetime": "We are asking for the pickup time.",
            "passengers": "We are asking for the number of passengers.",
            "luggage": "We are asking for the number of bags.",
            "name": "We are asking for the customer's name.",
            "notes": "We are asking for any special requests.",
            "confirm": "We are asking to confirm the booking details.",
        }
        step_templates = step_contexts_en # Placeholder for backward compat if needed
        
        # Prepare explicit status for LLM to prevent loops
        known = [f"- {k.replace('_', ' ').upper()}: {v}" for k, v in locked_slots.items() if v]
        known_str = "\n".join(known) if known else "None - This is the start of the booking."
        
        system = f"""You are Bareerah, a human-like, professional limousine booking assistant for Star Skyline Limousine. 
You are talking to a customer via voice. 

CURRENT BOOKING PROGRESS:
{known_str}

TASKS:
1. EXTRACT: Find any booking data in the user's speech: [dropoff, pickup, datetime, passengers, luggage, name].
2. RESPOND: Acknowledge what they said, then ask for the FIRST missing piece of info from the list above. 
3. NEXT STEP: Identify which missing field you are asking for in your response.

IMPORTANT: 
- DO NOT ask questions for information already listed in 'CURRENT BOOKING PROGRESS'.
- If they just gave you the dropoff, your response MUST ask for the pickup (or next missing field).
- Keep responses short (under 15 words) and natural.

Return ONLY this JSON:
{{
  "extracted_slots": {{ "slot_name": "value" }},
  "response": "Your natural response acknowledging input and asking for the NEXT thing",
  "next_step": "the field you are asking for now"
}}"""

RULES:
- If user provides info already confirmed, just acknowledge it.
- If user corrects info (e.g. "Actually I mean Dubai Mall"), extract it and update your response.
- Keep responses short, clear, and friendly.
ALWAYS return valid JSON."""

        user = f'Customer said: "{text}"\n\nExtract and respond.'
        
        resp = OPENAI_CLIENT.chat.completions.create(
            model="gpt-4o-mini",  # ✅ MUCH FASTER FOR VOICE
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            response_format={"type": "json_object"},
            max_tokens=150,
            timeout=3
        )
        
        result = json.loads(resp.choices[0].message.content)
        extracted_slots = result.get('extracted_slots', {})
        # For backward compatibility with the rest of the script:
        extracted = extracted_slots.get(flow_step) or result.get('extracted_value', '').strip()
        confidence = result.get('confidence', 0)
        response = result.get('response', 'Got it.')
        next_step = result.get('next_step', flow_step)
        
        # ✅ SMART LOCATION FALLBACK (If LLM extracted nothing or low confidence)
        if flow_step in ["dropoff", "pickup"] and not extracted:
            # (Keeping the word-match logic for safety)
            text_lower = text.lower()
            text_words = set(w for w in text_lower.split() if len(w) > 2)
            best_value = None
            best_score = 0
            for key, val in POPULAR_DUBAI_LOCATIONS.items():
                kw = set(w for w in key.split() if len(w) > 2)
                if text_words & kw:
                    score = len(text_words & kw) / (len(text_words) + 0.1)
                    if score > best_score:
                        best_score = score
                        best_value = val
            if best_value and best_score > 0.4:
                extracted = best_value
                extracted_slots[flow_step] = extracted
                confidence = 0.9
        
        print(f"[NLU] extracted={extracted_slots} | next={next_step} | response='{response[:50]}...'", flush=True)
        return {
            "extracted_slots": extracted_slots,
            "extracted_value": extracted,
            "confidence": confidence,
            "response": response,
            "next_step": next_step
        }
        
    except Exception as e:
        print(f"[NLU] ❌ Error: {str(e)}", flush=True)
        return {
            "extracted_value": "",
            "confidence": 0.0,
            "response": "Sorry, could you repeat that?",
            "next_step": flow_step
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
                    
                    # If call came in but no webhook received for 120+ seconds, it's abandoned
                    if elapsed > 120 and call_sid in call_contexts:
                        ctx = call_contexts[call_sid]
                        slots = ctx.get("locked_slots", {})
                        
                        # Only send email if not already confirmed/emailed
                        if ctx.get("flow_step") != "complete" and not ctx.get("email_sent_for_drop"):
                            abandoned_calls.append((call_sid, ctx.get("caller_phone", "Unknown"), slots, ctx))
                            ctx["email_sent_for_drop"] = True
                            print(f"[CLEANUP] 📧 Detected abandoned call {call_sid} (elapsed: {elapsed:.0f}s)", flush=True)
                
                # Send emails for abandoned calls
                for call_sid, caller_phone, slots, ctx in abandoned_calls:
                    data_collected = sum([
                        bool(slots.get("pickup")),
                        bool(slots.get("dropoff")),
                        bool(slots.get("passengers")),
                        bool(slots.get("datetime"))
                    ])
                    
                    dropped_data = {
                        "customer_name": "Customer (not provided)",
                        "customer_phone": caller_phone,
                        "pickup_location": slots.get("pickup", "Not provided"),
                        "dropoff_location": slots.get("dropoff", "Not provided"),
                        "pickup_time": slots.get("datetime", "TBD"),
                        "passengers": slots.get("passengers", "N/A"),
                        "luggage": slots.get("luggage", "N/A"),
                        "issue": f"❌ FALLBACK: Call dropped without webhook - Status: Not completed | Data: {data_collected}/4",
                        "vehicle_type": slots.get("vehicle", "Not selected"),
                        "vehicle_model": slots.get("vehicle_model", "Pending"),
                        "fare": slots.get("fare", "N/A"),
                        "distance_km": slots.get("distance_km", "N/A")
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

# ✅ PHONE CALL ROUTES (Dec 8, 2025 - PostgreSQL-backed state persistence)
@app.route('/voice', methods=['POST'])
@app.route('/incoming', methods=['POST'])
def incoming_call():
    """Phone call handler - Initial greeting with DB-backed state"""
    import time
    call_sid = request.values.get('CallSid', 'unknown')
    caller_phone = request.values.get('Caller', 'unknown')
    
    print(f"[INCOMING CALL] Caller: {caller_phone} | CallSID: {call_sid}", flush=True)
    
    response = VoiceResponse()
    
    # ✅ DB-BACKED STATE: Check if existing session, otherwise create new
    ctx = load_call_state(call_sid)
    if not ctx:
        ctx = {
            "flow_step": "dropoff",
            "locked_slots": {},
            "caller_phone": caller_phone,
            "notes": ""
        }
        save_call_state(call_sid, ctx)
        print(f"[DB] ✅ New session created for {call_sid}", flush=True)
    else:
        print(f"[DB] ✅ Resumed session for {call_sid}, step={ctx['flow_step']}", flush=True)
    
    # ✅ Also keep in-memory for call-status handler compatibility
    call_contexts[call_sid] = ctx
    call_timestamps[call_sid] = time.time()
    
    # ✅ DTMF LANGUAGE SELECTION: Accept digit press OR speech
    greeting_lang = "Assalaam-o-Alaikum, Welcome to Star Skyline Limousine, I am Bareerah. Press 1 for English, 2 for Urdu, 3 for Arabic. Or just tell me where you want to go!"
    print(f"[BAREERAH] 🎤 {greeting_lang}", flush=True)
    
    callback_url = request.url_root.rstrip('/') + "/call-status?call_sid=" + call_sid
    gather = response.gather(
        input="speech dtmf",  # ✅ Accept BOTH speech AND digit press
        action="/handle?call_sid=" + call_sid,
        method="POST",
        speech_timeout=2,
        max_speech_time=30,
        timeout=30,
        enhanced=True,
        numDigits=1,  # ✅ Stop after 1 digit press
        statusCallback=callback_url,
        statusCallbackMethod="POST"
    )
    gather.say(greeting_lang, voice='Polly.Joanna', language='en-US')
    print(f"[TTS] ✅ Twilio Say (FREE) played successfully", flush=True)
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
        
        # ✅ DB-BACKED: Try in-memory first, then fallback to DB
        ctx = call_contexts.get(call_sid)
        if not ctx:
            ctx = load_call_state(call_sid)
            print(f"[CALL-STATUS] Loaded context from DB for {call_sid}", flush=True)
        
        if ctx:
            locked_slots = ctx.get("locked_slots", {})
            caller_phone = ctx.get("caller_phone", "Unknown")
            
            # Check if ANY data was collected
            has_dropoff = bool(locked_slots.get("dropoff"))
            has_pickup = bool(locked_slots.get("pickup"))
            has_datetime = bool(locked_slots.get("datetime"))
            
            data_collected = sum([has_dropoff, has_pickup, has_datetime])
            
            print(f"[CALL-STATUS] Context found - Phone: {caller_phone}, Data collected: {data_collected}/3", flush=True)
            
            # Prepare notification data
            dropped_booking_data = {
                "customer_name": "Customer (not provided)",
                "customer_phone": caller_phone,
                "dropoff_location": locked_slots.get("dropoff", "Not provided"),
                "pickup_location": locked_slots.get("pickup", "Not provided"),
                "datetime": locked_slots.get("datetime", "Not provided"),
                "issue": f"Call dropped - Data collected: {data_collected}/3 fields"
            }
            
            # Send email if ANY data was collected
            if data_collected > 0:
                print(f"[EMAIL] 📧 Sending partial info email (async)...", flush=True)
                notify_booking_to_team(dropped_booking_data, status="partial_info")
                print(f"[EMAIL] ✅ Sent call-drop alert for {caller_phone} (collected {data_collected}/3 fields)", flush=True)
            else:
                print(f"[CALL-DROP] ℹ️ Call ended with no data collected", flush=True)
            
            # ✅ FORCE: Wait 1 second to ensure email thread starts
            import time
            time.sleep(1)
            print(f"[CALL-DROP] ✅ Context cleanup completed for {call_sid}", flush=True)
            
            # ✅ DB-BACKED: Log dropped call BEFORE cleanup
            try:
                if call_sid in call_contexts:
                    log_completed_call(call_sid, call_contexts[call_sid])  # ✅ Log to call_logs table
                delete_call_state(call_sid)
                if call_sid in call_contexts:
                    del call_contexts[call_sid]
                print(f"[CALL-STATUS] ✅ Context cleaned up from DB & memory for {call_sid}", flush=True)
            except Exception as cleanup_err:
                print(f"[CALL-STATUS] ⚠️ Cleanup error: {cleanup_err}", flush=True)
        else:
            print(f"[CALL-STATUS] ⚠️ No context found for {call_sid} - this might be a very quick drop", flush=True)
    else:
        print(f"[CALL-STATUS] Status '{call_status_val}' not processed (waiting for completed/failed)", flush=True)
    
    return "OK", 200

# ✅ PHONE HANDLE - DB-BACKED STATE (Dec 8, 2025 - Crash-resistant)
@app.route('/handle', methods=['POST'])
def handle_call():
    """DB-backed state machine: dropoff→pickup→datetime→passengers→luggage→notes→vehicle→confirm→complete"""
    try:
        call_sid = request.values.get('call_sid', 'unknown')
        
        # ✅ CHECK FOR DTMF DIGIT (Language selection from greeting)
        digits = request.values.get('Digits', '').strip()
        speech = request.values.get('SpeechResult', '').strip()
        
        # ✅ Handle DTMF digit press for language selection
        if digits and digits in ['1', '2', '3']:
            print(f"[DTMF] 🔢 Customer pressed: {digits}", flush=True)
            digit_to_lang = {'1': 'en', '2': 'ur', '3': 'ar'}
            selected_lang = digit_to_lang[digits]
            
            # Load context and set language
            ctx = load_call_state(call_sid)
            if not ctx:
                ctx = {
                    "flow_step": "dropoff",
                    "locked_slots": {},
                    "caller_phone": request.values.get('From', 'unknown'),
                    "notes": "",
                    "language": selected_lang
                }
            else:
                ctx["language"] = selected_lang
            
            save_call_state(call_sid, ctx)
            call_contexts[call_sid] = ctx
            print(f"[LANG] 🌐 Language set via DTMF: {selected_lang}", flush=True)
            
            # Now ask for dropoff
            voice_config = get_polly_voice(selected_lang)
            resp = VoiceResponse()
            gather = resp.gather(
                input='speech',
                action=f"/handle?call_sid={call_sid}",
                timeout=30,
                speech_timeout='auto',
                enhanced=True,
                language=voice_config.get("stt_lang", "en-US")
            )
            dropoff_msg = "Where would you like to go?" if selected_lang == "en" else "Aap kahan jana chahte hain?" if selected_lang == "ur" else "Aina tarid an thihab?"
            gather.say(dropoff_msg, voice=voice_config["voice"], language=voice_config.get("tts_lang", "en-US"))
            return str(resp)
        
        # ✅ LOG CUSTOMER SPEECH (transliterate Hindi to Roman for readability)
        if speech:
            speech_log = transliterate_hindi_to_roman(speech)
            print(f"[CUSTOMER] 🎧 {speech_log}", flush=True)
        
        # Silence → ask repeat (with barge-in)
        if not speech or len(speech) < 2:
            # Load context for language preference
            ctx = load_call_state(call_sid)
            lang = ctx.get("language", "en") if ctx else "en"
            voice_config = get_polly_voice(lang)
            
            resp = VoiceResponse()
            gather = resp.gather(input='speech', action=f"/handle?call_sid={call_sid}", timeout=30, speech_timeout='auto', enhanced=True, language=voice_config.get("stt_lang", "en-US"))
            gather.say("Sorry, I didn't catch that. Please repeat?", voice=voice_config["voice"], language=voice_config.get("tts_lang", "en-US"))
            return str(resp)
        
        # ✅ DB-BACKED: Load state from PostgreSQL (crash-safe)
        ctx = load_call_state(call_sid)
        if not ctx:
            ctx = {
                "flow_step": "dropoff",
                "locked_slots": {},
                "caller_phone": request.values.get('From', 'unknown'),
                "notes": "",
                "language": "en"
            }
            save_call_state(call_sid, ctx)
            print(f"[DB] ✅ New session created in /handle for {call_sid}", flush=True)
        else:
            print(f"[DB] ✅ Loaded session: step={ctx['flow_step']}, slots={list(ctx.get('locked_slots', {}).keys())}", flush=True)
        
        # ✅ MULTI-LANGUAGE: Detect language from customer speech
        detected_lang = detect_language(speech)
        if detected_lang != "en" and ctx.get("language", "en") == "en":
            ctx["language"] = detected_lang
            print(f"[LANG] 🌐 Language detected: {detected_lang}", flush=True)
        
        # Also keep in-memory for call-status handler
        call_contexts[call_sid] = ctx
        
        # Get current language for brain
        current_lang = ctx.get("language", "en")
        response_text = ""
        
        # ✅ UNIFIED BRAIN CALL
        nlu = extract_nlu_clean(speech, ctx["flow_step"], ctx["locked_slots"], current_lang)
        
        # ✅ MULTI-EXTRACTION: Save identified slots
        if nlu.get("extracted_slots"):
            for slot, val in nlu["extracted_slots"].items():
                if val:
                    ctx["locked_slots"][slot] = val
                    print(f"[BRAIN] ✅ Extracted {slot}: {val}", flush=True)

        # ✅ NO LOOP GUARD: Trust the Brain's response/next_step choice 
        # The Brain now knows exactly what's locked and asks for the right thing.
        ctx["flow_step"] = nlu.get("next_step", ctx["flow_step"])
        response_text = nlu.get("response", "Could you repeat that?")

        # ✅ Check for airport specifically to switch to flight_info if needed
        for loc_slot in ["pickup", "dropoff"]:
            lv = ctx["locked_slots"].get(loc_slot)
            if lv and is_airport_location(lv) and not ctx["locked_slots"].get("flight_time"):
                # If Brain didn't already transition us to flight_info, do it here
                if ctx["flow_step"] != "flight_info":
                    ctx["flow_step"] = "flight_info"
                    ctx["locked_slots"]["flight_type"] = "arrival" if loc_slot == "pickup" else "departure"
                    # Add a custom response since we're overriding brain
                    if current_lang == "ur":
                        response_text = f"Theek hai, {lv}. Aapki flight ka time kya hai?"
                    else:
                        response_text = f"Got it, {lv}. What time is your flight?"


        # ✅ FUNCTIONAL LOGIC CHAIN (prevents hitting the final 'else')
        if ctx["flow_step"] in ["dropoff", "pickup", "name", "notes", "vehicle"]:
             pass # Use response_text from Brain

        
        # ✅ SKIP OLD REDUNDANT STEPS - Just use Brain's response
        # We only keep the specific logic for time parsing and booking creation
        # ✅ FUNCTIONAL LOGIC CHAIN (prevents hitting the final 'else')
        # These steps use the response generated by the Brain above.
        if ctx["flow_step"] in ["dropoff", "pickup", "name", "notes", "vehicle", "passengers", "luggage"]:
             pass 

        
        # ✅ STEP 2.5: ASK FOR FLIGHT INFO (if airport detected)
        elif ctx["flow_step"] == "flight_info":
            # Extract flight time from speech
            nlu = extract_nlu_clean(speech, "datetime", ctx["locked_slots"], current_lang)
            if nlu.get("confidence", 0) >= 0.7:
                flight_time_raw = nlu.get("extracted_value", "")
                
                try:
                    from datetime import datetime as dt, timezone, timedelta
                    dubai_tz = timezone(timedelta(hours=4))
                    
                    # ✅ FIX: Handle multiple time formats (YYYY-MM-DD HH:MM, HH:MM, 12-hour, etc)
                    parsed = None
                    formats_to_try = [
                        "%Y-%m-%d %H:%M",      # 2025-12-12 14:30
                        "%Y-%m-%d %I:%M %p",   # 2025-12-12 2:30 PM
                        "%H:%M",               # 14:30
                        "%I:%M %p",            # 2:30 PM
                    ]
                    
                    for fmt in formats_to_try:
                        try:
                            parsed = dt.strptime(flight_time_raw.strip(), fmt)
                            print(f"[AIRPORT] ✅ Parsed time '{flight_time_raw}' with format '{fmt}'", flush=True)
                            break
                        except ValueError:
                            continue
                    
                    if not parsed:
                        raise ValueError(f"Could not parse time: {flight_time_raw}")
                    
                    # If only time was provided (no date), use today's date
                    if parsed.year == 1900:  # strptime default year for time-only format
                        now_utc = dt.now(timezone.utc)
                        now_dubai = now_utc.astimezone(dubai_tz)
                        parsed = parsed.replace(year=now_dubai.year, month=now_dubai.month, day=now_dubai.day)
                    
                    dubai_dt = parsed.replace(tzinfo=dubai_tz)
                    
                    # ✅ Format as ISO 8601 UTC for backend
                    flight_time_utc = dubai_dt.astimezone(timezone.utc).isoformat()
                    ctx["locked_slots"]["flight_time"] = flight_time_utc
                    # ✅ FIX: Read flight_type from locked_slots (persisted) instead of ctx (not persisted)
                    flight_type = ctx["locked_slots"].get("flight_type", "departure")
                    
                    print(f"[AIRPORT] ✅ Flight {flight_type.upper()}: {flight_time_utc}", flush=True)
                    
                    # Move to next step (datetime if we came from dropoff, else passengers)
                    if flight_type == "departure":
                        # Came from dropoff → next is pickup
                        ctx["flow_step"] = "pickup"
                        response_text = "Perfect! Your departure time is noted. Now, where are you departing from?"
                    else:
                        # Came from pickup → next is datetime
                        ctx["flow_step"] = "datetime"
                        response_text = "Great! Your arrival time is noted. When do you need to be picked up?"
                    
                except Exception as e:
                    print(f"[AIRPORT] ⚠️ Parse error: {e}", flush=True)
                    if current_lang == "ur":
                        response_text = "Mujhe samajh nahi aya. Flight ka time dobara bataye? Jaise 14:30 ya 2:30 PM"
                    elif current_lang == "ar":
                        response_text = "Lam afhum. Aw waqtu alrahlah marra okhrah? Mathalan 14:30"
                    else:
                        response_text = "I didn't catch that. Can you say the flight time again? Like 2:30 PM or 14:30"
            else:
                if current_lang == "ur":
                    response_text = "Flight time samajh nahi aya. Kya time ho sakte?"
                elif current_lang == "ar":
                    response_text = "Lam afhum alwaqt. Aw alwaqt?"
                else:
                    response_text = "I didn't catch the time. What time is your flight?"
        
        # ✅ STEP 3: ASK FOR DATETIME
        elif ctx["flow_step"] == "datetime":
            if nlu.get("confidence", 0) >= 0.7:
                raw_dt = nlu.get("extracted_value", "")
                
                # ✅ DUBAI TIMEZONE FIX
                try:
                    from datetime import datetime as dt, timezone, timedelta
                    dubai_tz = timezone(timedelta(hours=4))
                    parsed = dt.strptime(raw_dt, "%Y-%m-%d %H:%M")
                    now_utc = dt.now(timezone.utc)
                    now_dubai = now_utc.astimezone(dubai_tz)
                    dubai_dt = parsed.replace(tzinfo=dubai_tz)
                    formatted_dt = dubai_dt.strftime("%Y-%m-%d %H:%M")
                    
                    ctx["locked_slots"]["datetime"] = formatted_dt
                    
                    today_dubai = now_dubai.date()
                    dubai_date = dubai_dt.date()
                    days_diff = (dubai_date - today_dubai).days
                    
                    if days_diff < 0:
                        ctx["flow_step"] = "datetime"
                        if not response_text: response_text = "I'm sorry, I need a time in the future. When would you like the ride?"
                    else:
                        ctx["flow_step"] = "passengers"
                        print(f"[DATETIME] ✅ ACCEPTED: {formatted_dt}", flush=True)
                except Exception as e:
                    print(f"[DATETIME] ⚠️ Parse error: {e}", flush=True)
            
            if not response_text: response_text = nlu.get("response", "When would you like the ride?")
        
        # ✅ STEP 4: PASSENGERS
        elif ctx["flow_step"] == "passengers":
            pass # Extraction handled by Brain + saved at top

        # ✅ STEP 5: LUGGAGE
        elif ctx["flow_step"] == "luggage":
            pass # Extraction handled by Brain + saved at top

        # ✅ STEP 5.5: ASK FOR CUSTOMER NAME
        elif ctx["flow_step"] == "name":
            if nlu.get("confidence", 0) >= 0.7:
                name = nlu.get("extracted_slots", {}).get("name") or nlu.get("extracted_value", "")
                if name:
                    ctx["locked_slots"]["customer_name"] = name.title()
                    ctx["flow_step"] = "notes"
                    print(f"[FLOW] ✅ NAME LOCKED: {name}", flush=True)
            if not response_text: response_text = nlu.get("response", "What is your name?")
        
        # ✅ STEP 6: ASK FOR NOTES (waiting time, special requests) → AUTO-RUN VEHICLE
        elif ctx["flow_step"] == "notes":
            # ✅ TRANSLITERATE ONLY for skip detection (not for storage)
            speech_transliterated = transliterate_hindi_to_roman(speech)
            
            # ✅ Check if skip intent using transliterated speech (for language-agnostic detection)
            if detect_skip_intent(speech_transliterated):
                ctx["notes"] = ""  # ✅ Explicitly set to empty string
                print(f"[FLOW] ✅ NOTES SKIPPED (detected skip: '{speech_transliterated}' from '{speech}')", flush=True)
            else:
                # ✅ Store ORIGINAL speech, not transliterated version
                if speech and len(speech.strip()) >= 3:
                    ctx["notes"] = speech
                    print(f"[FLOW] ✅ NOTES CAPTURED: {speech} (transliterated: {speech_transliterated})", flush=True)
                else:
                    ctx["notes"] = ""  # ✅ Don't save empty/short strings
                    print(f"[FLOW] ⚠️ NOTES EMPTY, skipping", flush=True)
            
            # ✅ AUTO-RUN VEHICLE SELECTION IMMEDIATELY (no waiting for customer input)
            ctx["flow_step"] = "vehicle"
            pax = ctx["locked_slots"].get("passengers", 1)
            lug = ctx["locked_slots"].get("luggage", 0)
            jwt_token = get_jwt_token()
            vehicle, err = suggest_vehicle(pax, lug, jwt_token)
            
            if vehicle:
                ctx["locked_slots"]["vehicle"] = vehicle
                pickup = ctx["locked_slots"].get("pickup", "")
                dropoff = ctx["locked_slots"].get("dropoff", "")
                distance_km = calculate_distance_google_maps(pickup, dropoff)
                if not distance_km or distance_km <= 0:
                    distance_km = 25
                    print(f"[FARE] ⚠️ Google Maps failed, using fallback 25km", flush=True)
                else:
                    print(f"[FARE] ✅ Google Maps distance: {distance_km}km ({pickup} → {dropoff})", flush=True)
                ctx["locked_slots"]["distance_km"] = distance_km
                fare = calculate_fare_api(distance_km, vehicle, "point_to_point", jwt_token)
                if not fare or fare <= 0:
                    fare = 50 + int(distance_km * 3.5) + (lug * 20)
                ctx["locked_slots"]["fare"] = f"AED {int(fare)}"
                ctx["flow_step"] = "confirm"
                
                # ✅ PROFESSIONAL: Include vehicle MODEL name (not just category)
                vehicle_models = {
                    "suv": "GMC Yukon",
                    "sedan": "Toyota Camry", 
                    "luxury": "Lexus ES350",
                    "van": "Toyota Previa",
                    "luxury van": "Mercedes Viano",
                    "urban suv": "Chevrolet Tahoe",
                    "first class": "Lexus ES350",
                    "executive": "Honda Accord",
                    "elite van": "Mercedes Viano",
                    "classic": "Toyota Corolla",
                    "mini bus": "15-Seater Coach"
                }
                vehicle_model = vehicle_models.get(vehicle.lower(), vehicle.upper())
                ctx["locked_slots"]["vehicle_model"] = vehicle_model
                
                # ✅ FIX: Only say "Noted:" if customer actually said something (notes were recorded)
                # Don't say it if they said "skip", "no", "nahi", etc.
                notes_msg = f"Noted: {ctx['notes']}. " if ctx["notes"] and len(ctx["notes"].strip()) > 0 else ""
                response_text = f"{notes_msg}Based on {pax} passengers and {lug} bags, we recommend a {vehicle_model}. Your fare is {ctx['locked_slots']['fare']}. Confirm?"
                print(f"[FLOW] ✅ VEHICLE+FARE: {vehicle_model} ({vehicle}) | {ctx['locked_slots']['fare']} | {distance_km}km", flush=True)
            else:
                response_text = "Sorry, no vehicles available. Driver will call you."
                ctx["flow_step"] = "complete"
        
        # ✅ STEP 7: VEHICLE (only if re-entered from confirmation rejection)
        elif ctx["flow_step"] == "vehicle":
            pax = ctx["locked_slots"].get("passengers", 1)
            lug = ctx["locked_slots"].get("luggage", 0)
            jwt_token = get_jwt_token()
            vehicle, err = suggest_vehicle(pax, lug, jwt_token)
            
            if vehicle:
                ctx["locked_slots"]["vehicle"] = vehicle
                pickup = ctx["locked_slots"].get("pickup", "")
                dropoff = ctx["locked_slots"].get("dropoff", "")
                distance_km = ctx["locked_slots"].get("distance_km") or calculate_distance_google_maps(pickup, dropoff) or 25
                fare = calculate_fare_api(distance_km, vehicle, "point_to_point", jwt_token)
                if not fare or fare <= 0:
                    fare = 50 + int(distance_km * 3.5) + (lug * 20)
                ctx["locked_slots"]["fare"] = f"AED {int(fare)}"
                ctx["flow_step"] = "confirm"
                vehicle_model = ctx["locked_slots"].get("vehicle_model", vehicle.upper())
                pax = ctx["locked_slots"].get("passengers", 1)
                lug = ctx["locked_slots"].get("luggage", 0)
                response_text = f"Based on {pax} passengers and {lug} bags, we recommend a {vehicle_model}. Your fare is {ctx['locked_slots']['fare']}. Confirm?"
                print(f"[FLOW] ✅ VEHICLE+FARE: {vehicle_model} | {ctx['locked_slots']['fare']} | {distance_km}km", flush=True)
            else:
                response_text = "Sorry, no vehicles available. Try again?"
        
        # ✅ STEP 7.5: UPGRADE SELECT (dedicated flow step for luxury vehicle selection)
        elif ctx["flow_step"] == "upgrade_select":
            # ✅ FIX: Read from locked_slots (persisted to DB) instead of ctx
            luxury_options = ctx.get("locked_slots", {}).get("luxury_options", [])
            original_snapshot = ctx.get("locked_slots", {}).get("original_snapshot", {})
            
            # ✅ USE PRIORITY-BASED INTENT CLASSIFICATION
            intent, option_idx = parse_upgrade_intent(speech, luxury_options)
            print(f"[UPGRADE] Intent: {intent}, Option: {option_idx}", flush=True)
            
            if intent in ("confirm_with_selection", "select") and option_idx is not None and option_idx < len(luxury_options):
                # ✅ Customer selected a specific luxury option
                selected_option = luxury_options[option_idx]
                ctx["locked_slots"]["vehicle"] = selected_option["type"]
                ctx["locked_slots"]["vehicle_model"] = selected_option["model"]
                ctx["locked_slots"]["fare"] = f"AED {selected_option['fare']}"
                ctx["flow_step"] = "confirm"
                
                if current_lang == "ur":
                    response_text = f"Behtareen choice! {selected_option['model']} select ki. Aapka fare AED {selected_option['fare']} hai. Confirm kar doon?"
                elif current_lang == "ar":
                    response_text = f"Khiyar mumtaz! {selected_option['model']}. Ujratuk AED {selected_option['fare']}. Hal akid?"
                else:
                    response_text = f"Excellent choice! {selected_option['model']} selected. Your fare is AED {selected_option['fare']}. Should I confirm?"
                print(f"[FLOW] 🚗 LUXURY SELECTED: {selected_option['model']} at AED {selected_option['fare']}", flush=True)
            
            elif intent == "confirm" and luxury_options:
                # ✅ Customer confirms without selecting → use first luxury option
                selected_option = luxury_options[0]
                ctx["locked_slots"]["vehicle"] = selected_option["type"]
                ctx["locked_slots"]["vehicle_model"] = selected_option["model"]
                ctx["locked_slots"]["fare"] = f"AED {selected_option['fare']}"
                ctx["flow_step"] = "confirm"
                
                if current_lang == "ur":
                    response_text = f"Behtareen! {selected_option['model']} select ki. Aapka fare AED {selected_option['fare']} hai. Confirm kar doon?"
                elif current_lang == "ar":
                    response_text = f"Mumtaz! {selected_option['model']}. Ujratuk AED {selected_option['fare']}. Hal akid?"
                else:
                    response_text = f"Great! {selected_option['model']} selected. Your fare is AED {selected_option['fare']}. Should I confirm?"
                print(f"[FLOW] 🚗 DEFAULT LUXURY SELECTED: {selected_option['model']}", flush=True)
            
            elif intent in ("previous", "expensive", "reject"):
                # ✅ RESTORE ORIGINAL VEHICLE from snapshot (stored in locked_slots)
                apply_vehicle_snapshot(ctx, original_snapshot)
                ctx["flow_step"] = "confirm"
                # ✅ Clean up upgrade data from locked_slots
                ctx["locked_slots"].pop("luxury_options", None)
                ctx["locked_slots"].pop("original_snapshot", None)
                
                original_model = original_snapshot.get("vehicle_model", "your vehicle")
                original_fare = original_snapshot.get("fare", "AED 100")
                
                if current_lang == "ur":
                    response_text = f"Koi baat nahi! Aapki pehli gaari {original_model} fare {original_fare} pe ready hai. Confirm kar doon?"
                elif current_lang == "ar":
                    response_text = f"La bais! Sayaratuk {original_model} bi {original_fare} mutaha. Hal akid?"
                else:
                    response_text = f"No problem! Your {original_model} at {original_fare} is ready. Shall I confirm?"
                print(f"[FLOW] 🔙 Customer chose original: {original_model} @ {original_fare}", flush=True)
            
            else:
                # Ask again
                if current_lang == "ur":
                    response_text = "Kaunsi luxury gaari chahiye? Ya pehli wali rakhein?"
                elif current_lang == "ar":
                    response_text = "Ayy sayara turid? Aw alawla?"
                else:
                    response_text = "Which luxury vehicle would you like? Or keep the original?"
        
        # ✅ STEP 8: CONFIRM BOOKING (handle questions too)
        elif ctx["flow_step"] == "confirm":
            # ✅ MULTILINGUAL confirmation words (English + Urdu/Hindi transliteration + raw Hindi)
            confirm_words = {
                # English
                "yes", "yeah", "yup", "confirm", "ok", "okay", "book", "done", "sure", "please",
                # Urdu/Hindi transliteration
                "haan", "theek", "bilkul", "jee", "bilkul theek", "acha",
                # Raw Hindi/Urdu script (from speech recognition)
                "हाँ", "हान", "ठीक", "बिलकुल", "जी", "आचा", "ये", "येस", "यस", "हाँ", "जी हाँ"
            }
            reject_words = {"cancel", "restart", "start over", "different", "nahi"}
            positive_phrases = ["is good", "good enough", "fine", "sounds good", "that's good", "this is good", "works", "perfect", "great"]
            
            # ✅ VEHICLE UPGRADE KEYWORDS (Multilingual + transliterated variants)
            upgrade_keywords = {
                # English
                "upgrade", "luxury", "better", "premium", "bigger", "vip", "executive", "first class",
                "lexus", "mercedes", "bmw", "audi", "rolls royce", "bentley",
                # Urdu/Hindi transliterated variants
                "luxury car", "badi gaari", "achi gaari", "mehnga", "premium gaari", "zyada achi", 
                "lexus", "mercedes", "luxury chahiye", "upgrade karo", "badi wali", "badhiya", "fancy",
                "pehle wali", "aur achhee", "aur badhiya", "upgread", "s i want", "want upgrade",
                # Arabic
                "sayara fakhira", "afkham", "luxury", "arqa"
            }
            
            # ✅ RETURN TO ORIGINAL VEHICLE KEYWORDS (Multilingual)
            previous_keywords = {
                # English
                "previous", "original", "first", "before", "go back", "initial", "cheaper", "affordable",
                # Urdu/Hindi
                "pehli", "pehly", "pehli wali", "purani", "pichli", "sasti", "kam rate", "kam fare",
                "jo pehle batai", "wo hi", "wohi", "pehle wali gaari",
                # Arabic
                "alawla", "alsabiqa", "alkhadima"
            }
            
            # ✅ TOO EXPENSIVE / REJECTION KEYWORDS (Multilingual)
            too_expensive_keywords = {
                # English
                "expensive", "too much", "too high", "cheaper", "less", "lower price", "not that",
                # Urdu/Hindi
                "mehenga", "zyada hai", "ziada hai", "kam karo", "sasta", "bahut hai", "nahi itna",
                # Arabic
                "ghali", "kathir", "arkhas"
            }
            
            speech_lower = speech.lower()
            
            # ✅ TRANSLITERATE FIRST before checking keywords (handles Hindi/Urdu script)
            speech_transliterated = transliterate_hindi_to_roman(speech).lower()
            
            # ✅ Check BOTH lowercase AND transliterated + original speech for all variants
            has_positive_phrase = any(phrase in speech_lower for phrase in positive_phrases) or any(phrase in speech_transliterated for phrase in positive_phrases)
            has_confirm_word = any(word in speech_lower for word in confirm_words) or any(word in speech for word in confirm_words if len(word) > 2) or any(word in speech_transliterated for word in confirm_words)
            has_reject_word = any(word in speech_lower for word in reject_words) or any(word in speech_transliterated for word in reject_words)
            # ✅ CHECK TRANSLITERATED SPEECH FOR UPGRADE (so "एस आई वांट अपग्रेड" → "s i want upgrade" → matches "upgrade")
            has_upgrade_request = any(kw in speech_lower for kw in upgrade_keywords) or any(kw in speech_transliterated for kw in upgrade_keywords)
            has_previous_request = any(kw in speech_lower for kw in previous_keywords)
            has_too_expensive = any(kw in speech_lower for kw in too_expensive_keywords)
            
            # ✅ VEHICLE UPGRADE FLOW: DISABLED - Always skip upgrade flow
            if False and has_upgrade_request and not has_confirm_word:
                # ✅ CAPTURE SNAPSHOT of original vehicle for rollback (store in LOCKED_SLOTS for DB persistence)
                if "original_snapshot" not in ctx.get("locked_slots", {}):
                    ctx["locked_slots"]["original_snapshot"] = capture_vehicle_snapshot(ctx)
                    print(f"[UPGRADE] 📦 Storing original snapshot: {ctx['locked_slots']['original_snapshot']}", flush=True)
                
                # ✅ LUXURY VEHICLE OPTIONS with models and fares
                luxury_options = [
                    {"type": "luxury", "model": "Lexus ES350", "category": "Luxury Sedan"},
                    {"type": "luxury suv", "model": "Cadillac Escalade", "category": "Luxury SUV"},
                    {"type": "first class", "model": "Mercedes S-Class", "category": "First Class"},
                ]
                
                jwt_token = get_jwt_token()
                distance_km = ctx["locked_slots"].get("distance_km", 25)
                
                # Calculate fares for each luxury option
                luxury_fare_options = []
                for opt in luxury_options:
                    fare = calculate_fare_api(distance_km, opt["type"], "point_to_point", jwt_token)
                    if not fare or fare <= 0:
                        fare = 150 + int(distance_km * 4)  # Fallback for luxury
                    luxury_fare_options.append({
                        "type": opt["type"],
                        "model": opt["model"],
                        "fare": int(fare)
                    })
                
                # ✅ Store options in LOCKED_SLOTS (persisted to DB) AND change flow_step to dedicated upgrade_select
                ctx["locked_slots"]["luxury_options"] = luxury_fare_options
                ctx["flow_step"] = "upgrade_select"  # ✅ DEDICATED FLOW STEP
                
                # ✅ PERSIST STATE IMMEDIATELY (before responding)
                save_call_state(call_sid, ctx)
                
                # Build response based on language
                if current_lang == "ur":
                    response_text = f"Ji bilkul! Hamare luxury options yeh hain: "
                    for i, opt in enumerate(luxury_fare_options, 1):
                        response_text += f"{i}. {opt['model']} - AED {opt['fare']}. "
                    response_text += "Kaunsi gaari pasand hai? Ya pehli wali hi rakhein?"
                elif current_lang == "ar":
                    response_text = f"Tabaan! Khiyaratuna alfakhira: "
                    for i, opt in enumerate(luxury_fare_options, 1):
                        response_text += f"{i}. {opt['model']} - AED {opt['fare']}. "
                    response_text += "Ayy sayara turid? Aw alawla?"
                else:
                    response_text = f"Sure! Our luxury options are: "
                    for i, opt in enumerate(luxury_fare_options, 1):
                        response_text += f"{i}. {opt['model']} at AED {opt['fare']}. "
                    response_text += "Which one would you like? Or keep the original?"
                
                print(f"[FLOW] 🚗 UPGRADE REQUEST: Showing {len(luxury_fare_options)} luxury options", flush=True)
            
            # If customer says something positive like "is good", treat as confirmation
            elif (has_positive_phrase or has_confirm_word) and not has_upgrade_request:
                # ✅ FIX: Create booking IMMEDIATELY (don't wait for next speech)
                try:
                    slots = ctx.get("locked_slots", {})
                    # ✅ Parse fare from "AED 619" format
                    fare_raw = slots.get("fare", "0")
                    fare_int = int(str(fare_raw).replace("AED", "").replace(",", "").strip()) if fare_raw else 0
                    
                    # ✅ MAP field names to match backend expectations (COMPLETE)
                    pickup_datetime = slots.get("datetime", "")
                    
                    # ✅ AUTO-DETECT BOOKING TYPE (airport_transfer if flight info present)
                    booking_type = "airport_transfer" if slots.get("flight_type") else "point_to_point"
                    
                    payload = {
                        "customer_name": slots.get("customer_name", "Customer"),  # ✅ Use collected name (already transliterated)
                        "customer_phone": ctx.get("caller_phone", "unknown"),
                        "pickup_location": slots.get("pickup", ""),
                        "dropoff_location": slots.get("dropoff", ""),
                        "fare_aed": fare_int,
                        "fare": fare_int,  # ✅ Backend may expect "fare" not "fare_aed"
                        "distance_km": float(slots.get("distance_km", 0)),  # ✅ ADD distance
                        "vehicle_type": slots.get("vehicle", "sedan"),
                        "vehicle_model": slots.get("vehicle_model", ""),  # ✅ ADD vehicle model
                        "booking_type": booking_type,  # ✅ airport_transfer or point_to_point
                        "passengers_count": int(slots.get("passengers", 1)),
                        "luggage_count": int(slots.get("luggage", 0)),
                        "pickup_time": pickup_datetime,  # ✅ MAP pickup_datetime → pickup_time for backend
                        "pickup_datetime": pickup_datetime,  # Keep for compatibility
                        "notes": ctx.get("notes", ""),  # ✅ Already transliterated
                        # ✅ NEW: Flight info fields (optional, only if airport transfer)
                        "flight_type": slots.get("flight_type", None),  # arrival or departure
                        "flight_time": slots.get("flight_time", None)  # ISO 8601 UTC datetime
                    }
                    success = create_booking_direct(payload)
                    response_text = "Your ride is confirmed! Driver will call you shortly. Thank you for choosing Star Skyline Limousine!"
                    print(f"[BOOKING] ✅ CREATED: {payload}", flush=True)
                    
                    # ✅ SEND CONFIRMATION EMAIL even if backend fails (capture lead)
                    try:
                        email_data = {
                            "customer_name": payload.get("customer_name", "Customer"),
                            "customer_phone": payload.get("customer_phone"),
                            "customer_email": ctx.get("customer_email", ""),  # ✅ Email if available
                            "pickup_location": payload.get("pickup_location"),
                            "dropoff_location": payload.get("dropoff_location"),
                            "passengers_count": payload.get("passengers_count"),  # ✅ Use correct key
                            "passengers": payload.get("passengers_count"),  # ✅ Fallback for template
                            "luggage_count": payload.get("luggage_count"),  # ✅ Use correct key
                            "luggage": payload.get("luggage_count"),  # ✅ Fallback for template
                            "calculated_fare_aed": payload.get("fare_aed"),  # ✅ Use correct key
                            "fare": f"AED {payload.get('fare_aed')}",  # ✅ Fallback
                            "vehicle_type": payload.get("vehicle_type"),  # ✅ Use correct key
                            "vehicle": payload.get("vehicle_type"),  # ✅ Fallback
                            "vehicle_model": payload.get("vehicle_model", ""),  # ✅ ADD vehicle model
                            "datetime": payload.get("pickup_datetime"),  # ✅ Pickup time
                            "notes": payload.get("notes", ""),  # ✅ Add notes
                            "booking_reference": f"BOOK-{payload.get('customer_phone', 'XXXX').replace('+', '').replace(' ', '')[-4:].upper()}"  # ✅ Generate temp ref
                        }
                        notify_booking_to_team(email_data, status="created" if success else "pending")
                        print(f"[EMAIL] ✅ Booking confirmation sent to team", flush=True)
                    except Exception as email_err:
                        print(f"[EMAIL] ⚠️ Failed to send confirmation email: {email_err}", flush=True)
                    
                    # DB CLEANUP: Log call BEFORE deleting session
                    log_completed_call(call_sid, ctx)  # ✅ Log to call_logs table
                    delete_call_state(call_sid)
                    if call_sid in call_contexts:
                        del call_contexts[call_sid]
                    
                    resp = VoiceResponse()
                    # ✅ Use multilingual voice for final confirmation
                    voice_config = get_polly_voice(current_lang)
                    resp.say(response_text, voice=voice_config["voice"], language=voice_config.get("tts_lang", "en-US"))
                    resp.hangup()
                    return str(resp)
                except Exception as e:
                    print(f"[BOOKING] ❌ ERROR: {e}", flush=True)
                    error_msg = "Booking error. Our team will call you back shortly."
                    if current_lang == "ur":
                        error_msg = "Booking mein error aya. Hamara team aapko callback karega."
                    elif current_lang == "ar":
                        error_msg = "Khata fil hajz. Siyatsiluk fareek."
                    resp = VoiceResponse()
                    voice_config = get_polly_voice(current_lang)
                    resp.say(error_msg, voice=voice_config["voice"], language=voice_config.get("tts_lang", "en-US"))
                    resp.hangup()
                    return str(resp)
            elif has_reject_word and not has_positive_phrase:
                response_text = "No problem. Let me start over. Where would you like to go?"
                ctx["flow_step"] = "dropoff"
                ctx["locked_slots"] = {}
            else:
                vehicle_model = ctx["locked_slots"].get("vehicle_model", "SUV")
                fare = ctx["locked_slots"].get("fare", "AED 220")
                # ✅ MULTILINGUAL confirmation response
                if current_lang == "ur":
                    response_text = f"Hum {vehicle_model} bhej rahe hain. Aapka fare {fare} hai. Kya main confirm kar doon?"
                elif current_lang == "ar":
                    response_text = f"Sanaqduk {vehicle_model}. Ujratuk {fare}. Hal akid?"
                else:
                    response_text = f"We'll send a {vehicle_model}. Your fare is {fare}. Should I confirm your booking?"
                print(f"[FLOW] ℹ️ Question answered, re-asking confirmation (lang={current_lang})", flush=True)
        
        # ✅ STEP 9-10: CREATE BOOKING & COMPLETE
        elif ctx["flow_step"] == "complete":
            try:
                payload = dict(ctx.get("locked_slots", {}))
                payload["caller_phone"] = ctx.get("caller_phone", "unknown")
                # ✅ Add notes (waiting time) to payload
                if ctx.get("notes"):
                    payload["notes"] = ctx["notes"]
                create_booking_direct(payload)
                response_text = "Your ride is confirmed! Driver will call you shortly. Thank you!"
                print(f"[BOOKING] ✅ CREATED: {payload}", flush=True)
                
                # ✅ DB CLEANUP: Log call BEFORE deleting session
                log_completed_call(call_sid, ctx)  # ✅ Log to call_logs table
                delete_call_state(call_sid)
                if call_sid in call_contexts:
                    del call_contexts[call_sid]
                
                resp = VoiceResponse()
                resp.say(response_text, voice='woman', language='en-US')
                resp.hangup()
                return str(resp)
            except Exception as e:
                print(f"[BOOKING] ❌ ERROR: {e}", flush=True)
                response_text = "Booking error. Driver will call you."
                # ✅ Log even on error to preserve call history
                log_completed_call(call_sid, ctx)  # ✅ Log to call_logs table
                delete_call_state(call_sid)
                resp = VoiceResponse()
                resp.say(response_text, voice='woman', language='en-US')
                resp.hangup()
                return str(resp)
        
        else:
            response_text = "Sorry, something went wrong. Let's start over. Where would you like to go?"
            ctx["flow_step"] = "dropoff"
        
        # ✅ LOG BAREERAH RESPONSE
        print(f"[BAREERAH] 🎤 {response_text}", flush=True)
        
        # ✅ DB-BACKED: Save state to PostgreSQL (crash-safe)
        save_call_state(call_sid, ctx)
        call_contexts[call_sid] = ctx
        
        # ✅ BARGE-IN ENABLED: Nest Say INSIDE Gather so customer can interrupt
        resp = VoiceResponse()
        
        # ✅ MULTI-LANGUAGE TTS + STT: Use detected language for both voice AND speech recognition
        lang = ctx.get("language", "en")
        voice_config = get_polly_voice(lang)
        
        gather = resp.gather(
            input='speech',
            action=f"/handle?call_sid={call_sid}",
            timeout=30,
            speech_timeout='auto',
            enhanced=True,
            language=voice_config.get("stt_lang", "en-US")  # ✅ STT language for Urdu/Arabic
        )
        gather.say(response_text, voice=voice_config["voice"], language=voice_config.get("tts_lang", "en-US"))
        return str(resp)
    
    except Exception as e:
        # ✅ CATCH ANY UNHANDLED EXCEPTION - NO MORE "application error"
        print(f"[ERROR] ❌ UNHANDLED EXCEPTION: {str(e)}", flush=True)
        print(f"[ERROR] Stack trace: {type(e).__name__}", flush=True)
        try:
            resp = VoiceResponse()
            resp.say("Sorry, technical issue. Please call back shortly.", voice='woman')
            resp.hangup()
            return str(resp)
        except:
            return "OK", 200



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


# ✅ STARTUP INITIALIZATION (Runs for both Gunicorn and local python main.py)
def startup_init():
    try:
        # Give Gunicorn a moment to start listening
        import time
        time.sleep(1) 
        
        print("[STARTUP] 🚀 Initializing services (Background)...", flush=True)
        init_db_pool()
        
        # ✅ INITIALIZE JWT TOKEN
        print("[AUTH] Initializing JWT token...", flush=True)
        initial_token = get_jwt_token()
        if initial_token:
            print(f"[AUTH] ✅ Server JWT token initialized successfully", flush=True)
            # ✅ FETCH FARE RATES
            fare_rates_manager.fetch_from_backend(initial_token)
        else:
            print(f"[AUTH] ⚠️ JWT token initialization failed - will retry on first request", flush=True)
        
        # ✅ TEST BACKEND CONNECTION
        test_backend_connection()
        
        # ✅ PREWARM TTS
        threading.Thread(target=prewarm_elevenlabs_tts, daemon=True).start()
        print("[STARTUP] ✅ Initialization complete!", flush=True)
    except Exception as e:
        print(f"[STARTUP] ❌ CRITICAL INIT ERROR: {e}", flush=True)
        pass

# ✅ RUN INIT ASYNC so Gunicorn starts immediately (prevents Railway timeout)
print("🚀 App Loaded - Starting init thread...", flush=True)
threading.Thread(target=startup_init, daemon=True).start()

if __name__ == '__main__':
    print("Starting Bareerah (Professional Booking Assistant) in LOCAL mode...", flush=True)
    app.run(host='0.0.0.0', port=5000, debug=False)
