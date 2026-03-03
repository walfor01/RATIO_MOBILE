import psycopg
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("SELECT id, data_creazione, data_installazione_prevista, data_installazione_effettiva FROM preventivo LIMIT 5;")
print("PREVENTIVO:", cur.fetchall())
cur.execute("SELECT preventivo_id, data_consegna, data_installazione FROM righepreventivo WHERE data_consegna IS NOT NULL OR data_installazione IS NOT NULL LIMIT 5;")
print("RIGHE:", cur.fetchall())
