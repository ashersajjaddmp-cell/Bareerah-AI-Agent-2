import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def check_db():
    url = os.environ.get('DATABASE_URL')
    print(f"Connecting to: {url}")
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = cur.fetchall()
        print("Tables found:", tables)
        
        for table in tables:
            t_name = table[0]
            cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{t_name}'")
            cols = cur.fetchall()
            print(f"Columns in {t_name}:", cols)
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
