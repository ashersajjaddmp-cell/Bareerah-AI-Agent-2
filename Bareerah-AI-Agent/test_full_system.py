
import os
import psycopg2
from openai import OpenAI
import requests
import sys
from dotenv import load_dotenv

# Force UTF-8 encoding for output
sys.stdout.reconfigure(encoding='utf-8')

# Load keys from .env
load_dotenv()

def test_config():
    print("[INFO] STARTING SELF-DIAGNOSIS...")

    # 1. CHECK KEYS EXISTENCE
    openai_key = os.getenv("OPENAI_API_KEY")
    eleven_key = os.getenv("ELEVENLABS_API_KEY")
    db_url = os.getenv("DATABASE_URL")
    backend_url = os.getenv("BACKEND_BASE_URL")

    print(f"Checking OpenAI Key... {'[OK]' if openai_key else '[MISSING]'}")
    print(f"Checking ElevenLabs Key... {'[OK]' if eleven_key else '[MISSING]'}")
    print(f"Checking Database URL... {'[OK]' if db_url else '[MISSING]'}")
    
    # 2. TEST OPENAI CONNECTION
    print("\n[TEST] OpenAI Connectivity...")
    try:
        client = OpenAI(api_key=openai_key)
        # Simple cheap request
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Ping"}]
        )
        print(f"[SUCCESS] OpenAI Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"[FAILED] OpenAI Error: {e}")

    # 3. TEST ELEVENLABS CONNECTION
    print("\n[TEST] ElevenLabs Connectivity...")
    try:
        url = "https://api.elevenlabs.io/v1/user"
        headers = {"xi-api-key": eleven_key}
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            print("[SUCCESS] ElevenLabs Authenticated")
        else:
            print(f"[FAILED] ElevenLabs Status: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"[FAILED] ElevenLabs Connection Error: {e}")

    # 4. TEST DATABASE CONNECTION
    print("\n[TEST] Database Connectivity...")
    try:
        conn = psycopg2.connect(db_url)
        print("[SUCCESS] Connected to NeonDB")
        conn.close()
    except Exception as e:
        print(f"[FAILED] Database Error: {e}")

    # 5. TEST BACKEND PING
    print("\n[TEST] Backend URL...")
    try:
        resp = requests.get(f"{backend_url}/")
        print(f"[SUCCESS] Backend Reachable: {resp.status_code}")
    except Exception as e:
        print(f"[FAILED] Backend Unreachable: {e}")

if __name__ == "__main__":
    test_config()
