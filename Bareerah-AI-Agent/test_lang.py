
import requests

def test_multilang_and_bargain():
    base_url = "http://localhost:5000"
    call_sid = "CALL_TEST_LANG_BARGAIN"
    
    # 1. Simulate English Selection (Press 1)
    print("English & Bargaining Test started")
    requests.post(f"{base_url}/select-language", data={"CallSid": call_sid, "Digits": "1"})
    
    # 2. Give Name
    resp = requests.post(f"{base_url}/handle", data={"CallSid": call_sid, "SpeechResult": "My name is John Doe"})
    print(f"Ayesha (English): {resp.text[:200]}...")
    
    # 3. Bargain
    resp = requests.post(f"{base_url}/handle", data={"CallSid": call_sid, "SpeechResult": "Can I get a 20% discount on the price?"})
    print(f"Ayesha's Bargain Response: {resp.text[:300]}...")
    
    # 4. Simulate Urdu Selection (Press 2)
    call_sid_urdu = "CALL_TEST_URDU"
    print("Testing Urdu Selection")
    resp = requests.post(f"{base_url}/select-language", data={"CallSid": call_sid_urdu, "Digits": "2"})
    # Check if Urdu greeting is in TwiML
    if "naam" in resp.text:
        print("Urdu Greeting correctly generated!")
        
    # 5. Arabic Check
    call_sid_arabic = "CALL_TEST_ARABIC"
    print("Testing Arabic Selection")
    resp = requests.post(f"{base_url}/select-language", data={"CallSid": call_sid_arabic, "Digits": "3"})
    if "ismuka" in resp.text:
        print("Arabic Greeting correctly generated!")

if __name__ == "__main__":
    test_multilang_and_bargain()
