#!/usr/bin/env python3
"""✅ FAST TEST: Voice-enabled Bareerah (Option 1 + 2)"""

import requests
import json
import time

print('🎤 VOICE-ENABLED BAREERAH TEST\n')
print('='*70)

# Test cases
tests = [
    {
        'name': 'Test 1: English Booking with Voice',
        'phone': '+971505551111',
        'messages': [
            'I need ride from Dubai Mall to Burj Khalifa tomorrow, 2 people, 1 bag',
            'Yes',
            'Ahmed Khan',
            'Yes'
        ]
    }
]

for test in tests:
    print(f'\n{test["name"]}')
    print('-'*70)
    
    for i, msg in enumerate(test['messages'][:3], 1):
        data = {'From': f'whatsapp:{test["phone"]}', 'Body': msg}
        
        try:
            r = requests.post('http://localhost:5000/whatsapp', data=data, timeout=15)
            response = r.json()
            status = '✅' if r.status_code == 200 else '❌'
            
            print(f'Step {i}: {status}')
            if 'message' in response:
                msg_short = response['message'][:60]
                print(f'   Response: {msg_short}...')
            
            time.sleep(1)  # Small delay between requests
        except Exception as e:
            print(f'Step {i}: ❌ Error - {str(e)[:50]}')
            break

print('\n' + '='*70)
print('✅ VOICE TEST COMPLETE!')
print('Check logs for [TTS] messages to confirm voice replies are being generated')
