#!/usr/bin/env python3
"""Comprehensive Test - 5 Languages, 20+ QA each, Full Booking Flow"""

import requests
import time

BASE_URL = "http://localhost:5000/whatsapp"
RESULTS = {"passed": 0, "failed": 0}

def run_conversation(test_name, phone, conversation_turns):
    """Run a full conversation and verify all steps"""
    print(f'\n{"="*80}')
    print(f'🧪 {test_name}')
    print("="*80)
    
    all_success = True
    for turn_num, (customer_msg, expected_contains) in enumerate(conversation_turns, 1):
        data = {'From': f'whatsapp:{phone}', 'Body': customer_msg}
        try:
            r = requests.post(BASE_URL, data=data, timeout=15)
            response = r.json()['message']
            
            # Check if expected keywords are in response
            has_expected = any(keyword.lower() in response.lower() for keyword in expected_contains)
            status = "✅" if has_expected else "⚠️"
            
            print(f"\n[Turn {turn_num}] {status}")
            print(f"👤 CUSTOMER: {customer_msg}")
            print(f"🤖 BAREERAH: {response[:100]}...")
            
            if not has_expected:
                all_success = False
                print(f"   ⚠️ Missing: {expected_contains}")
            
            time.sleep(0.3)
        except Exception as e:
            print(f"\n[Turn {turn_num}] ❌ ERROR: {str(e)[:50]}")
            all_success = False
            break
    
    if all_success:
        RESULTS["passed"] += 1
        print(f"\n✅ {test_name} PASSED")
    else:
        RESULTS["failed"] += 1
        print(f"\n❌ {test_name} FAILED")
    
    return all_success

# ============================================================================
# TEST 1: ENGLISH - COMPLETE BOOKING WITH 20+ QUESTIONS
# ============================================================================
run_conversation(
    "TEST 1: English (20+ QA)",
    "+971505550001",
    [
        ("I need a ride from Dubai Mall to Burj Khalifa tomorrow at 3pm for 2 passengers with 1 bag", ["BOOKING SUMMARY"]),
        ("What is the total fare?", ["AED", "fare"]),
        ("Do you accept credit card?", ["Cash", "Card", "Apple", "Google"]),
        ("How long will it take?", ["minutes", "traffic"]),
        ("Is the driver experienced?", ["trained", "professional", "experience"]),
        ("Do you have AC?", ["AC", "climate", "control"]),
        ("Can I cancel?", ["booking", "call"]),
        ("What's the vehicle type?", ["sedan", "suv", "car"]),
        ("Do you have USB charging?", ["USB", "charging"]),
        ("Yes, proceed with booking", ["proceed", "confirm"]),
        ("My name is Ahmed Khan", ["name"]),
        ("Yes confirm", ["confirm"]),
        ("No, standard car is fine", ["sedan", "vehicle"]),
        ("No, one way trip", ["one-way", "trip"]),
        ("What payment methods?", ["Cash", "Card", "Apple", "Google"]),
        ("Can I add luggage later?", ["luggage", "bag"]),
        ("Is there WiFi in car?", ["vehicle"]),
        ("Are seatbelts available?", ["safety"]),
        ("What time should I be ready?", ["time", "ready"]),
        ("Yes confirm booking", ["confirm"]),
        ("ahmed.khan@gmail.com", ["email", "@"]),
        ("Yes confirm email", ["confirm"]),
        ("Yes, start the booking", ["booking", "confirm"]),
    ]
)

# ============================================================================
# TEST 2: ARABIC - COMPLETE BOOKING WITH 20+ QUESTIONS
# ============================================================================
run_conversation(
    "TEST 2: Arabic (20+ QA)",
    "+971505550002",
    [
        ("أريد سيارة من الفندق إلى المطار غدا الساعة 4 صباحا شخص واحد رحلة ذهاب فقط", ["BOOKING", "الفندق"]),
        ("كم السعر الاجمالي؟", ["AED", "السعر"]),
        ("هل تقبلون بطاقات الائتمان؟", ["نعم", "بطاقة"]),
        ("كم من الوقت؟", ["دقيقة", "وقت"]),
        ("السائق لديه خبرة؟", ["خبرة", "محترف"]),
        ("هل في تكييف؟", ["تكييف"]),
        ("هل يمكن الإلغاء؟", ["حجز"]),
        ("نوع السيارة؟", ["سيارة", "نوع"]),
        ("في شاحن؟", ["شاحن"]),
        ("نعم موافق", ["موافق", "تأكيد"]),
        ("اسمي محمد علي", ["الاسم"]),
        ("نعم التأكيد صحيح", ["تأكيد"]),
        ("سيارة عادية حسناً", ["سيارة", "عادية"]),
        ("لا رحلة ذهاب فقط", ["ذهاب"]),
        ("ما طرق الدفع؟", ["دفع", "نقد"]),
        ("هل يمكن إضافة حقائب؟", ["حقائب", "أمتعة"]),
        ("في إنترنت بالسيارة؟", ["إنترنت", "واي"]),
        ("في أحزمة أمان؟", ["أمان", "حزام"]),
        ("كم الوقت أستعد؟", ["وقت", "الساعة"]),
        ("تأكيد الحجز", ["حجز", "تأكيد"]),
        ("محمد@email.com", ["email", "@", "بريد"]),
        ("نعم البريد صحيح", ["صحيح", "تأكيد"]),
        ("ابدأ الحجز", ["حجز", "ابدأ"]),
    ]
)

# ============================================================================
# TEST 3: URDU - COMPLETE BOOKING WITH 20+ QUESTIONS
# ============================================================================
run_conversation(
    "TEST 3: Urdu (20+ QA)",
    "+971505550003",
    [
        ("مجھے ڈاون ٹاؤن سے ایروپورٹ جانا ہے کل دوپہر 2 بجے ایک مسافر ہے", ["BOOKING"]),
        ("کل کرایہ کتنا ہے؟", ["AED", "کرایہ"]),
        ("کریڈٹ کارڈ چلتا ہے؟", ["ہاں", "کارڈ"]),
        ("کتنا وقت لگے گا؟", ["منٹ", "وقت"]),
        ("ڈرائیور کو تجربہ ہے؟", ["تجربہ", "ڈرائیور"]),
        ("ایئر کنڈیشننگ ہے؟", ["ایئر"]),
        ("منسوخ کر سکتے ہیں؟", ["حجز"]),
        ("کار کی قسم کیا ہے؟", ["قسم"]),
        ("چارجنگ ہے؟", ["چارجنگ"]),
        ("ہاں آگے بڑھیں", ["آگے", "تسلیم"]),
        ("میرا نام علی ہے", ["نام"]),
        ("ہاں یقین ہے", ["تسلیم"]),
        ("سادہ کار ٹھیک ہے", ["کار"]),
        ("ایک طرفہ ہے", ["ایک", "طرفہ"]),
        ("ادائیگی کے طریقے؟", ["نقد", "ادائیگی"]),
        ("بیگ بعد میں ہو سکتے؟", ["بیگ"]),
        ("کار میں انٹرنیٹ؟", ["انٹرنیٹ"]),
        ("سیٹ بیلٹ ہے؟", ["سیٹ"]),
        ("تیاری کا وقت کیا ہے؟", ["وقت", "تیاری"]),
        ("ہاں حجز تسلیم کریں", ["حجز", "تسلیم"]),
        ("ali@email.com", ["email", "@"]),
        ("ہاں یہ صحیح ہے", ["صحیح", "تسلیم"]),
        ("حجز شروع کریں", ["حجز", "شروع"]),
    ]
)

# ============================================================================
# TEST 4: HINDI - COMPLETE BOOKING WITH 20+ QUESTIONS
# ============================================================================
run_conversation(
    "TEST 4: Hindi (20+ QA)",
    "+971505550004",
    [
        ("मुझे मरीना से दुबई मॉल जाना है कल सुबह 8 बजे दो लोग हैं", ["BOOKING"]),
        ("कुल किराया कितना है?", ["AED", "किराया"]),
        ("क्रेडिट कार्ड चलता है?", ["हां", "कार्ड"]),
        ("कितना समय लगेगा?", ["मिनट", "समय"]),
        ("ड्राइवर को अनुभव है?", ["अनुभव"]),
        ("एसी है?", ["एसी", "ठंडा"]),
        ("रद्द कर सकते हैं?", ["बुकिंग"]),
        ("कार का प्रकार?", ["कार", "प्रकार"]),
        ("चार्जिंग है?", ["चार्जिंग"]),
        ("हां आगे बढ़ें", ["आगे", "पुष्टि"]),
        ("मेरा नाम राज है", ["नाम"]),
        ("हां यकीन है", ["पुष्टि"]),
        ("साधारण कार ठीक है", ["कार"]),
        ("एकतरफा यात्रा है", ["यात्रा"]),
        ("भुगतान के तरीके?", ["नकद", "भुगतान"]),
        ("बैग बाद में जोड़ सकते?", ["बैग"]),
        ("कार में इंटरनेट?", ["इंटरनेट"]),
        ("सीट बेल्ट है?", ["सीट"]),
        ("तैयारी का समय?", ["समय"]),
        ("हां बुकिंग की पुष्टि करें", ["बुकिंग", "पुष्टि"]),
        ("raj@email.com", ["email", "@"]),
        ("हां यह सही है", ["सही", "पुष्टि"]),
        ("बुकिंग शुरू करें", ["बुकिंग", "शुरू"]),
    ]
)

# ============================================================================
# TEST 5: FRENCH - COMPLETE BOOKING WITH 20+ QUESTIONS
# ============================================================================
run_conversation(
    "TEST 5: French (20+ QA)",
    "+971505550005",
    [
        ("J'ai besoin d'une voiture de Jumeirah à la Marina demain à 10h pour 3 personnes", ["BOOKING"]),
        ("Quel est le tarif total?", ["AED", "tarif"]),
        ("Acceptez-vous les cartes de crédit?", ["Oui", "carte"]),
        ("Combien de temps pour arriver?", ["minutes", "temps"]),
        ("Le chauffeur a-t-il de l'expérience?", ["expérience", "chauffeur"]),
        ("Y a-t-il la climatisation?", ["climatisation"]),
        ("Peut-on annuler?", ["réservation"]),
        ("Quel type de voiture?", ["voiture", "type"]),
        ("Y a-t-il un port de charge?", ["charge"]),
        ("Oui, continuez", ["continuer", "confirmer"]),
        ("Mon nom est Pierre Dubois", ["nom"]),
        ("Oui c'est correct", ["correct", "confirmer"]),
        ("Une voiture ordinaire ça va", ["voiture"]),
        ("C'est un voyage aller simple", ["aller"]),
        ("Quels modes de paiement?", ["paiement", "modes"]),
        ("Peut-on ajouter des bagages?", ["bagages"]),
        ("Y a-t-il internet?", ["internet", "wifi"]),
        ("Les ceintures de sécurité?", ["sécurité"]),
        ("À quelle heure je dois être prêt?", ["heure", "prêt"]),
        ("Oui confirmez la réservation", ["réservation", "confirmer"]),
        ("pierre@email.com", ["email", "@"]),
        ("Oui c'est correct", ["correct", "confirmer"]),
        ("Commencez la réservation", ["réservation", "commencer"]),
    ]
)

# ============================================================================
# PRINT RESULTS
# ============================================================================
print(f'\n\n{"="*80}')
print('📊 FINAL RESULTS - ALL TESTS')
print("="*80)
print(f'✅ PASSED: {RESULTS["passed"]}/5')
print(f'❌ FAILED: {RESULTS["failed"]}/5')
print(f'📈 SUCCESS RATE: {(RESULTS["passed"]/5*100):.0f}%')
print("="*80)

