#!/usr/bin/env python3
"""
Test Bookings Script - Simulate 5 realistic customer conversations
2 One-way bookings, 3 Two-way bookings
Languages: 1 English, 2 Urdu, 2 Arabic
"""

import requests
import time
from typing import List
from urllib.parse import urlencode

BASE_URL = "http://localhost:5000/whatsapp"

# ============================================================================
# BOOKING 1: ENGLISH - ONE-WAY (Dubai Marina → Abu Dhabi)
# ============================================================================
BOOKING_1_ENGLISH_ONEWAY = [
    ("Hello, I need a ride from Dubai Marina to Abu Dhabi tomorrow at 3pm", "booking_start"),
    ("There will be 2 passengers and 2 suitcases", "details"),
    ("I prefer a comfortable sedan for the journey", "preference"),
    ("The pickup address is Marina Crescent, Dubai Marina", "pickup_confirm"),
    ("Destination is the Emirates Palace area in Abu Dhabi", "dropoff_confirm"),
    ("Can you confirm the vehicle will have air conditioning?", "question"),
    ("What's the estimated time for the journey?", "question"),
    ("My name is Michael James Anderson", "name"),
    ("Yes, that is my name", "name_confirm"),
    ("I would like a standard vehicle", "vehicle_choice"),
    ("No, I won't need a return trip", "round_trip"),
    ("What's the total fare for this journey?", "fare_check"),
    ("Is the driver experienced with long distance travel?", "question"),
    ("Will the vehicle have USB charging ports?", "question"),
    ("Do you accept credit card payments at the end?", "question"),
    ("michael.anderson@gmail.com", "email"),
    ("Yes, that's my email address", "email_confirm"),
    ("Proceeding with the booking", "final_confirm"),
]

# ============================================================================
# BOOKING 2: URDU - ONE-WAY (JBR to Downtown)
# ============================================================================
BOOKING_2_URDU_ONEWAY = [
    ("السلام علیکم، مجھے JBR سے ڈاؤن ٹاؤن تک چاہیے", "booking_start"),
    ("ایک آدمی اور ایک بیگ ہے", "details"),
    ("کل شام 6 بجے چاہیے", "time"),
    ("کیا سوال ہے کہ کار وہ کون سی ہوگی؟", "question"),
    ("کار میں AC ہے یا نہیں؟", "question"),
    ("میرا نام احمد حسن علی ہے", "name"),
    ("ہاں صحیح ہے", "name_confirm"),
    ("عام سیڈان ٹھیک ہے", "vehicle_choice"),
    ("نہیں، واپسی نہیں چاہیے", "round_trip"),
    ("کتنی دوری ہے JBR سے ڈاؤن ٹاؤن تک؟", "question"),
    ("ڈرائیور اچھا ہے یا نہیں؟", "question"),
    ("کتنا وقت لگے گا؟", "question"),
    ("کیا ٹریفک میں مسئلہ ہے؟", "question"),
    ("موبائل سے پے کر سکتے ہیں؟", "question"),
    ("کیا موسیقی ہے کار میں؟", "question"),
    ("احمد@email.com", "email"),
    ("ہاں یہی ہے", "email_confirm"),
    ("ہاں آگے بڑھیں", "final_confirm"),
]

# ============================================================================
# BOOKING 3: ARABIC - TWO-WAY/ROUND-TRIP (Airport ↔ Downtown)
# ============================================================================
BOOKING_3_ARABIC_ROUNDTRIP = [
    ("السلام عليكم، أريد سيارة من المطار إلى وسط المدينة", "booking_start"),
    ("هناك ثلاثة أشخاص وثلاث حقائب كبيرة", "details"),
    ("غدًا الساعة الثانية عشرة ظهرًا", "time"),
    ("هل السيارة جديدة أم قديمة؟", "question"),
    ("ما هو رقم التليفون للسائق؟", "question"),
    ("اسمي محمد عبد الرحمن السعيد", "name"),
    ("نعم، هذا اسمي صحيح", "name_confirm"),
    ("أريد سيارة فاخرة من فضلك", "vehicle_choice"),
    ("نعم، أحتاج إلى رحلة العودة", "round_trip"),
    ("متى يجب أن أحجز العودة؟", "question"),
    ("هل السيارة بها واي فاي؟", "question"),
    ("كم يكون السعر الكلي؟", "fare_check"),
    ("هل المطار من فضلك لديكم أماكن انتظار؟", "question"),
    ("هل المشروبات موجودة بالسيارة؟", "question"),
    ("هل يمكن للسائق التحدث بالإنجليزية؟", "question"),
    ("محمد@email.com", "email"),
    ("نعم، هذا البريد الإلكتروني صحيح", "email_confirm"),
    ("موافق، ابدأ الحجز", "final_confirm"),
]

# ============================================================================
# BOOKING 4: URDU - TWO-WAY/ROUND-TRIP (Business Bay ↔ Dubai Mall)
# ============================================================================
BOOKING_4_URDU_ROUNDTRIP = [
    ("ہیلو، مجھے بزنس بے سے دبائی مال تک چاہیے", "booking_start"),
    ("دو لوگ اور ایک چھوٹا بیگ ہے", "details"),
    ("آج شام 5 بجے", "time"),
    ("کیا سوال یہ ہے کہ کار میں ہیٹنگ ہے؟", "question"),
    ("ڈرائیور کے پاس تجربہ ہے یا نہیں؟", "question"),
    ("میرا نام فاطمہ احمد خان ہے", "name"),
    ("جی، یہ صحیح ہے", "name_confirm"),
    ("لگژری کار چاہتے ہیں", "vehicle_choice"),
    ("ہاں، واپسی بھی چاہیے", "round_trip"),
    ("واپسی کتنے بجے ہو سکتی ہے؟", "question"),
    ("کار میں ماسک ہے یا نہیں؟", "question"),
    ("کتنا خرچ آئے گا؟", "fare_check"),
    ("کیا ڈرائیور خاتون ہے یا نہیں؟", "question"),
    ("بیگ میں کتنا سامان رکھ سکتے ہیں؟", "question"),
    ("کیا کسی اور کو لے سکتے ہیں؟", "question"),
    ("fatima@email.com", "email"),
    ("ہاں یہی صحیح ہے", "email_confirm"),
    ("ٹھیک ہے، آگے بڑھیں", "final_confirm"),
]

# ============================================================================
# BOOKING 5: ENGLISH - TWO-WAY/ROUND-TRIP (Palm Jumeirah → Burj Khalifa)
# ============================================================================
BOOKING_5_ENGLISH_ROUNDTRIP = [
    ("Hi, I need transportation from Palm Jumeirah to Burj Khalifa", "booking_start"),
    ("There are 4 of us and we have 2 large suitcases and 2 medium bags", "details"),
    ("We need it tomorrow morning at 9am sharp", "time"),
    ("Can you tell me what type of vehicles you have available?", "question"),
    ("Is there a specific dress code for the driver?", "question"),
    ("My name is Sarah Elizabeth Cunningham", "name"),
    ("Yes, that's correct", "name_confirm"),
    ("We'd like your best luxury vehicle available", "vehicle_choice"),
    ("Yes, we need a return trip as well", "round_trip"),
    ("We'll be ready to return at 5pm", "round_trip_time"),
    ("Does your luxury vehicle come with a mini bar?", "question"),
    ("What's your cancellation policy if plans change?", "question"),
    ("Can the driver wait for us if needed?", "question"),
    ("Do you provide travel insurance?", "question"),
    ("What's the total cost for the full day service?", "fare_check"),
    ("Can we request a specific driver or route?", "question"),
    ("sarah.cunningham@outlook.com", "email"),
    ("That's the correct email", "email_confirm"),
    ("Perfect, proceed with the booking", "final_confirm"),
]

def send_message(phone: str, text: str, conversation_type: str) -> dict:
    """Send a WhatsApp message to Flask app using FORM-ENCODED data"""
    # Use form-encoded data (not JSON) as Flask app expects request.form.get('From')
    data = {
        "From": f"whatsapp:{phone}",
        "Body": text
    }
    
    try:
        response = requests.post(
            BASE_URL,
            data=data,  # Form-encoded instead of json
            timeout=10
        )
        print(f"  ✓ {text[:40]}... → {response.status_code}")
        return response.json() if response.text else {}
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
        return {"error": str(e)}

def run_booking_conversation(booking_name: str, phone: str, messages: List[tuple]) -> None:
    """Run a full booking conversation"""
    print(f"\n{'='*70}")
    print(f"🚗 {booking_name}")
    print(f"{'='*70}")
    print(f"📱 Phone: {phone}")
    print(f"💬 Conversation ({len(messages)} messages):")
    
    for i, (message, msg_type) in enumerate(messages, 1):
        print(f"\n  [{i}/{len(messages)}] {msg_type.upper()}")
        send_message(phone, message, msg_type)
        time.sleep(1.5)  # Increased delay to avoid connection pool exhaustion
    
    print(f"\n✅ {booking_name} - COMPLETED")

def main():
    """Run all test bookings"""
    print("\n" + "="*70)
    print("🎯 BAREERAH TEST BOOKINGS - 5 CONVERSATIONS")
    print("="*70)
    
    bookings = [
        ("BOOKING #1 - ENGLISH ONE-WAY (Marina → Abu Dhabi)", "+971501234567", BOOKING_1_ENGLISH_ONEWAY),
        ("BOOKING #2 - URDU ONE-WAY (JBR → Downtown)", "+971502345678", BOOKING_2_URDU_ONEWAY),
        ("BOOKING #3 - ARABIC ROUND-TRIP (Airport ↔ Downtown)", "+971503456789", BOOKING_3_ARABIC_ROUNDTRIP),
        ("BOOKING #4 - URDU ROUND-TRIP (Business Bay ↔ Dubai Mall)", "+971504567890", BOOKING_4_URDU_ROUNDTRIP),
        ("BOOKING #5 - ENGLISH ROUND-TRIP (Palm → Burj Khalifa)", "+971505678901", BOOKING_5_ENGLISH_ROUNDTRIP),
    ]
    
    for booking_name, phone, messages in bookings:
        run_booking_conversation(booking_name, phone, messages)
        time.sleep(3)  # Delay between different booking conversations
    
    print("\n" + "="*70)
    print("✅ ALL 5 TEST BOOKINGS COMPLETED!")
    print("="*70)
    print("\n📊 SUMMARY:")
    print("  • Booking 1: English, One-way (Michael James Anderson)")
    print("  • Booking 2: Urdu, One-way (احمد حسن علی)")
    print("  • Booking 3: Arabic, Round-trip (محمد عبد الرحمن السعيد)")
    print("  • Booking 4: Urdu, Round-trip (فاطمہ احمد خان)")
    print("  • Booking 5: English, Round-trip (Sarah Elizabeth Cunningham)")
    print("\n📍 Routes:")
    print("  • Dubai Marina → Abu Dhabi")
    print("  • JBR → Downtown")
    print("  • Airport ↔ Downtown")
    print("  • Business Bay ↔ Dubai Mall")
    print("  • Palm Jumeirah ↔ Burj Khalifa")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
