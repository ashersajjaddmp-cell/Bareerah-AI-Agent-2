#!/usr/bin/env python3
"""Extract conversation logs line by line"""

import requests
import time

def run_test_and_extract():
    BASE_URL = "http://localhost:5000/whatsapp"
    
    print("📱 BAREERAH CONVERSATION LOGS - LINE BY LINE")
    print("="*70)
    
    # Test 1: Complete English Booking
    print("\n🧪 TEST 1: ENGLISH BOOKING CONVERSATION")
    print("-"*70)
    
    phone = "+971505558888"
    conversation = [
        "I need ride from Dubai Mall to Burj Khalifa tomorrow, 2 passengers, 1 bag",
        "Yes",
        "Ahmed Khan",
        "Yes",
        "No",
        "ahmed@gmail.com",
        "Yes"
    ]
    
    turn = 1
    for msg in conversation:
        data = {'From': f'whatsapp:{phone}', 'Body': msg}
        r = requests.post(BASE_URL, data=data, timeout=15)
        response = r.json()['message']
        
        print(f"\nTurn {turn}:")
        print(f"👤 CUSTOMER: {msg}")
        print(f"🤖 BAREERAH: {response}")
        
        turn += 1
        time.sleep(0.5)
    
    # Test 2: Arabic Booking
    print("\n\n🧪 TEST 2: ARABIC BOOKING CONVERSATION")
    print("-"*70)
    
    phone = "+971505559999"
    conversation = [
        "أريد سيارة من الفندق إلى المطار غدا، شخص واحد",
        "نعم",
        "محمد علي",
        "نعم",
        "لا",
        "mohammed@email.com"
    ]
    
    turn = 1
    for msg in conversation:
        data = {'From': f'whatsapp:{phone}', 'Body': msg}
        r = requests.post(BASE_URL, data=data, timeout=15)
        response = r.json()['message']
        
        print(f"\nTurn {turn}:")
        print(f"👤 CUSTOMER: {msg}")
        print(f"🤖 BAREERAH: {response}")
        
        turn += 1
        time.sleep(0.5)
    
    # Test 3: Q&A Questions
    print("\n\n🧪 TEST 3: Q&A QUESTIONS CONVERSATION")
    print("-"*70)
    
    phone = "+971505550000"
    conversation = [
        "I need to go from Marina to Airport tomorrow",
        "1 passenger",
        "What is the total fare?",
        "Do you accept credit card?",
        "Yes",
        "John Smith"
    ]
    
    turn = 1
    for msg in conversation:
        data = {'From': f'whatsapp:{phone}', 'Body': msg}
        r = requests.post(BASE_URL, data=data, timeout=15)
        response = r.json()['message']
        
        print(f"\nTurn {turn}:")
        print(f"👤 CUSTOMER: {msg}")
        print(f"🤖 BAREERAH: {response}")
        
        turn += 1
        time.sleep(0.5)
    
    print("\n" + "="*70)
    print("✅ CONVERSATION EXTRACTION COMPLETE")
    print("="*70)

if __name__ == "__main__":
    run_test_and_extract()
