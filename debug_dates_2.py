import psycopg
import os
import datetime
from dotenv import load_dotenv

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Controllo date
oggi = datetime.date.today()
domani = oggi + datetime.timedelta(days=1)
print(f"Oggi in Python: {oggi} | Domani: {domani}")

query = """
SELECT r.preventivo_id, r.data_consegna, r.data_installazione 
FROM righepreventivo r
JOIN preventivo p ON r.preventivo_id = p.id
WHERE UPPER(p.status) IN ('CONFERMATO', 'BOZZA')
AND (r.data_consegna IS NOT NULL OR r.data_installazione IS NOT NULL);
"""
cur.execute(query)
rows = cur.fetchall()

print("\nDate trovate:")
for row in rows:
    print(row)
    
    # Test della logica che sta in dashboard.py:
    for val in [row[1], row[2]]:
        if val:
            try:
                dt_str = str(val).strip()[:10]
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").date()
                if dt == oggi:
                    print(f"-> MATCH TROVATO OGGI: {dt}")
                elif dt == domani:
                    print(f"-> MATCH TROVATO DOMANI: {dt}")
            except Exception as e:
                # Fallback DD/MM/YYYY se l'utente l'ha scritta a mano su db?
                try:
                    dt = datetime.datetime.strptime(dt_str, "%d/%m/%Y").date()
                    if dt == oggi:
                        print(f"-> MATCH_DDMM TROVATO OGGI: {dt}")
                except:
                    print(f"Impossibile parsare la stringa: {val}")

conn.close()
