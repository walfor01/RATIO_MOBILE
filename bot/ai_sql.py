"""
ai_sql.py — Converte domande in linguaggio naturale in query SQL
             usando Groq (Llama-3.3-70b) e le esegue sul DB in sola lettura.
"""

import re
import psycopg
from groq import Groq
from bot.config import GROQ_API_KEY, DATABASE_URL

client = Groq(api_key=GROQ_API_KEY)

# Schema del database iniettato nel prompt di sistema
DB_SCHEMA = """
Hai accesso a un database PostgreSQL di un'azienda di arredamento su misura chiamata RATIO.

TABELLA: preventivo
  - id (integer)
  - nome_cliente (character varying)
  - data_creazione (date)
  - status (character varying): valori esatti: 'BOZZA', 'CONFERMATO', 'FATTURATO', 'ANNULLATO'
  - totale_generale (numeric): totale imponibile
  - totale_ivato (numeric): totale con IVA

TABELLA: righepreventivo
  - id (integer)
  - preventivo_id (integer): FK verso preventivo.id
  - ambiente (character varying)
  - descrizione (character varying)
  - categoria (character varying)
  - fornitore (character varying)
  - quantita (numeric)
  - prezzo_vendita_no_iva (numeric)
  - prezzo_vendita_ivato (numeric)
  - utile_euro (numeric): margine netto in euro
  - data_consegna (character varying): data come stringa YYYY-MM-DD
  - data_installazione (character varying): data come stringa YYYY-MM-DD

ESEMPI DI QUERY CORRETTE:
-- Scadenze imminenti (date_consegna e data_installazione sono VARCHAR, usa TO_DATE):
SELECT p.nome_cliente, r.ambiente, r.data_consegna
FROM righepreventivo r JOIN preventivo p ON r.preventivo_id = p.id
WHERE r.data_consegna IS NOT NULL
  AND TO_DATE(r.data_consegna, 'YYYY-MM-DD') BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
ORDER BY r.data_consegna LIMIT 20;

-- Fatturato confermati:
SELECT SUM(totale_generale) AS fatturato FROM preventivo WHERE UPPER(status) = 'CONFERMATO';

-- Preventivi in bozza:
SELECT COUNT(*) as totale FROM preventivo WHERE UPPER(status) = 'BOZZA';

REGOLE OBBLIGATORIE:
1. SOLO query SELECT. Mai UPDATE, DELETE, INSERT, DROP, ALTER, TRUNCATE.
2. Rispondi SOLO con SQL puro. Niente markdown, backtick o commenti.
3. Per status usa SEMPRE UPPER(status).
4. Per le date usa SEMPRE TO_DATE(colonna, 'YYYY-MM-DD') perche sono varchar.
5. Non inventare colonne. Usa SOLO quelle elencate sopra.
6. LIMIT 20 sempre.
"""

SYSTEM_PROMPT = f"""Sei un assistente SQL esperto per un gestionale aziendale italiano.
{DB_SCHEMA}
Ricevi domande in italiano. Rispondi ESCLUSIVAMENTE con la query SQL, null'altro."""


def ask_groq_for_sql(user_question: str) -> str:
    """Chiede a Groq di generare una query SQL dalla domanda dell'utente."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_question}
        ],
        temperature=0.1,  # bassa temperatura = risposte più deterministiche
        max_tokens=500
    )
    sql = response.choices[0].message.content.strip()
    # Rimuovi eventuali backtick o markdown che il modello potrebbe aggiungere
    sql = re.sub(r"```(?:sql)?", "", sql).strip("`").strip()
    return sql


def run_readonly_query(sql: str) -> list[dict]:
    """Esegue la query SQL in modalità read-only e restituisce i risultati."""
    # Blocco di sicurezza: impedisce query distruttive
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate", "create"]
    sql_lower = sql.lower()
    for keyword in forbidden:
        if keyword in sql_lower:
            raise ValueError(f"Query non permessa: contiene '{keyword}'")

    with psycopg.connect(DATABASE_URL) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]


def format_results(rows: list[dict]) -> str:
    """Formatta i risultati della query in un messaggio leggibile per Telegram."""
    if not rows:
        return "📭 Nessun risultato trovato."

    lines = []
    for i, row in enumerate(rows[:15], 1):  # Max 15 righe per messaggio
        parts = []
        for key, val in row.items():
            if val is None:
                continue
            # Formatta i numeri monetari
            if isinstance(val, float) and ("totale" in key or "utile" in key or "prezzo" in key):
                parts.append(f"{key}: {val:,.2f} €".replace(",", "."))
            else:
                parts.append(f"{key}: {val}")
        lines.append(f"📌 [{i}] " + " | ".join(parts))

    result = "\n".join(lines)
    if len(rows) > 15:
        result += f"\n\n_... e altri {len(rows) - 15} risultati_"
    return result


def answer_question(user_question: str) -> str:
    """Pipeline completa: domanda → SQL → esecuzione → risposta formattata."""
    try:
        sql = ask_groq_for_sql(user_question)
        rows = run_readonly_query(sql)
        answer = format_results(rows)
        return f"🔍 *Query eseguita:*\n`{sql}`\n\n{answer}"
    except ValueError as e:
        return f"⛔ Operazione non permessa: {e}"
    except Exception as e:
        return f"❌ Errore durante l'elaborazione:\n`{e}`"
