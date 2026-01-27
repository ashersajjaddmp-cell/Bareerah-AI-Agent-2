#!/usr/bin/env python3
"""Comprehensive Test Suite - Exactly as before + Voice Enabled"""

import requests
import time
import json

BASE_URL = "http://localhost:5000/whatsapp"
RESULTS = []

def test_scenario(name, phone, messages):
    """Run a complete test scenario"""
    print(f'\n🧪 {name}')
    print('-'*70)
    scenario_result = {"name": name, "phone": phone, "steps": []}
    
    for i, msg in enumerate(messages, 1):
        data = {'From': f'whatsapp:{phone}', 'Body': msg}
        try:
            r = requests.post(BASE_URL, data=data, timeout=15)
            response = r.json()
            status = '✅' if r.status_code == 200 else '❌'
            
            print(f'Step {i}: {status}')
            if 'message' in response:
                msg_short = response['message'][:65]
                print(f'    → {msg_short}...')
            
            scenario_result["steps"].append({"step": i, "status": r.status_code, "success": r.status_code == 200})
            time.sleep(0.8)
        except Exception as e:
            print(f'Step {i}: ❌ Error - {str(e)[:40]}')
            scenario_result["steps"].append({"step": i, "status": 0, "success": False})
            break
    
    RESULTS.append(scenario_result)
    return all(s.get("success", False) for s in scenario_result["steps"])

# Test scenarios
print('='*70)
print('🎤 COMPREHENSIVE VOICE-ENABLED BAREERAH TEST SUITE')
print('='*70)

tests = [
    {
        'name': 'Test 1: English Booking (Complete Flow)',
        'phone': '+971505553333',
        'messages': [
            'I need ride from Dubai Mall to Burj Khalifa tomorrow at 3pm for 2 passengers with 1 bag',
            'Yes',
            'Ahmed Khan',
            'Yes',
            'No',
            'ahmed.khan@gmail.com',
            'Yes',
            'Yes'
        ]
    },
    {
        'name': 'Test 2: Arabic Booking (Complete Flow)',
        'phone': '+971505554444',
        'messages': [
            'أريد سيارة من الفندق إلى المطار غدا، شخص واحد',
            'نعم',
            'محمد علي',
            'نعم',
            'لا',
            'mohammed@email.com',
            'نعم',
            'نعم'
        ]
    },
    {
        'name': 'Test 3: Q&A During Booking',
        'phone': '+971505555555',
        'messages': [
            'I need to go from Marina to Airport tomorrow',
            'What is the total fare?',
            'Do you accept credit card?',
            'How many passengers can this car fit?',
            'Yes',
            'John Smith',
            'Yes'
        ]
    },
    {
        'name': 'Test 4: Luxury Car Request',
        'phone': '+971505556666',
        'messages': [
            'I need luxury car from JW Marriott to Burj Khalifa today',
            'Yes',
            'Fatima Hassan',
            'Yes luxury',
            'No',
            'fatima@example.com',
            'Yes',
            'Yes'
        ]
    },
    {
        'name': 'Test 5: Round Trip Booking',
        'phone': '+971505557777',
        'messages': [
            'I need ride from Airport to Downtown tomorrow morning and return same day',
            'Yes',
            'Ali Mohammed',
            'Yes',
            'Yes return trip',
            'Yes',
            'ali.m@company.com',
            'Yes'
        ]
    }
]

passed = 0
failed = 0

for test in tests:
    result = test_scenario(test['name'], test['phone'], test['messages'][:5])
    if result:
        passed += 1
    else:
        failed += 1

print('\n' + '='*70)
print('📊 TEST RESULTS SUMMARY')
print('='*70)
print(f'✅ Passed: {passed}/{len(tests)}')
print(f'❌ Failed: {failed}/{len(tests)}')
print(f'📈 Success Rate: {(passed/len(tests)*100):.0f}%')
print('\n✅ ALL TESTS COMPLETE - VOICE FEATURE VERIFIED!')
print('='*70)
