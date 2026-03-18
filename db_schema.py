import psycopg
import os
from dotenv import load_dotenv

load_dotenv()

def print_schema():
    conn = psycopg.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    
    print("--- TABELLE ---")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = [r[0] for r in cur.fetchall()]
    for t in tables:
        print(f"Tabella: {t}")
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s;", (t,))
        for col in cur.fetchall():
            print(f"   - {col[0]} ({col[1]})")

if __name__ == "__main__":
    print_schema()
