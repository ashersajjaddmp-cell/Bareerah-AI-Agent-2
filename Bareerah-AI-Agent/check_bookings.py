import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def check_bookings():
    url = os.environ.get('DATABASE_URL')
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'bookings'")
        cols = cur.fetchall()
        print("Bookings columns:", [c[0] for c in cols])
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_bookings()
