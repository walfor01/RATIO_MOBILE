"""
ai_sql.py — Converte domande in linguaggio naturale in query SQL
             usando Groq (Llama-3.3-70b) e le esegue sul DB in sola lettura.
             Poi riformatta il risultato in italiano naturale.
"""

import re
import psycopg
from groq import Groq
from bot.config import GROQ_API_KEY, DATABASE_URL

client = Groq(api_key=GROQ_API_KEY)

# Schema del database iniettato nel prompt di sistema
DB_SCHEMA = """
Database PostgreSQL di RATIO, azienda italiana di arredamento su misura.

TABELLA: preventivo
  - id (integer)
  - nome_cliente (character varying)
  - data_creazione (date)
  - status (character varying): valori esatti: 'BOZZA', 'CONFERMATO', 'FATTURATO', 'ANNULLATO'
  - totale_generale (numeric): totale imponibile in euro
  - totale_ivato (numeric): totale con IVA in euro

TABELLA: righepreventivo
  - id (integer)
  - preventivo_id (integer): FK verso preventivo.id
  - ambiente (character varying): es. "Cucina", "Camera"
  - descrizione (character varying)
  - categoria (character varying)
  - fornitore (character varying)
  - quantita (numeric)
  - prezzo_vendita_no_iva (numeric)
  - prezzo_vendita_ivato (numeric)
  - utile_euro (numeric): margine netto in euro
  - data_consegna (character varying): data nel formato DD/MM/YYYY
  - data_installazione (character varying): data nel formato DD/MM/YYYY

FORMATO DATE FONDAMENTALE:
Le colonne data_consegna e data_installazione sono VARCHAR nel formato DD/MM/YYYY.
Per confrontarle con date usa SEMPRE: TO_DATE(data_consegna, 'DD/MM/YYYY')

ESEMPI DI QUERY CORRETTE:
-- Scadenze prossimi 7 giorni:
SELECT p.nome_cliente, r.ambiente, r.data_consegna, r.data_installazione
FROM righepreventivo r JOIN preventivo p ON r.preventivo_id = p.id
WHERE UPPER(p.status) IN ('CONFERMATO', 'BOZZA')
  AND (
    (r.data_consegna IS NOT NULL AND r.data_consegna != '' AND TO_DATE(r.data_consegna, 'DD/MM/YYYY') BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days')
    OR
    (r.data_installazione IS NOT NULL AND r.data_installazione != '' AND TO_DATE(r.data_installazione, 'DD/MM/YYYY') BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days')
  )
ORDER BY r.data_consegna LIMIT 20;

-- Fatturato totale (CONFERMATO + FATTURATO = cantieri attivi e completati):
SELECT SUM(totale_generale) AS fatturato_totale, COUNT(*) AS numero_preventivi
FROM preventivo WHERE UPPER(status) IN ('CONFERMATO', 'FATTURATO');

-- Preventivi in bozza:
SELECT COUNT(*) as totale FROM preventivo WHERE UPPER(status) = 'BOZZA';

-- Preventivi confermati con cliente:
SELECT nome_cliente, totale_generale, data_creazione
FROM preventivo WHERE UPPER(status) = 'CONFERMATO' ORDER BY data_creazione DESC LIMIT 20;

REGOLE OBBLIGATORIE:
1. SOLO query SELECT. Mai UPDATE, DELETE, INSERT, DROP, ALTER, TRUNCATE.
2. Rispondi SOLO con SQL puro. Niente markdown, backtick o commenti.
3. Per status usa SEMPRE UPPER(status).
4. Per le date usa SEMPRE TO_DATE(colonna, 'DD/MM/YYYY') - formato italiano DD/MM/YYYY.
5. Prima di filtrare date, aggiungi sempre: colonna IS NOT NULL AND colonna != ''
6. Non inventare colonne. Usa SOLO quelle elencate sopra.
7. LIMIT 20 sempre.
"""

SYSTEM_PROMPT_SQL = f"""Sei un assistente SQL esperto per un gestionale aziendale italiano.
{DB_SCHEMA}
Ricevi domande in italiano. Rispondi ESCLUSIVAMENTE con la query SQL, null'altro."""

SYSTEM_PROMPT_NATURAL = """Sei un assistente aziendale italiano per un'azienda di arredamento chiamata RATIO.
Ricevi dati grezzi da un database e devi trasformarli in una risposta naturale in italiano, concisa e professionale.
Usa emoji appropriate. Formatta i numeri monetari come euro italiani (es: 181.494,78 €).
Non mostrare dati tecnici come ID o nomi di colonne. Sii diretto e umano."""


def ask_groq_for_sql(user_question: str) -> str:
    """Chiede a Groq di generare una query SQL dalla domanda dell'utente."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_SQL},
            {"role": "user", "content": user_question}
        ],
        temperature=0.1,
        max_tokens=500
    )
    sql = response.choices[0].message.content.strip()
    sql = re.sub(r"```(?:sql)?", "", sql).strip("`").strip()
    return sql


def run_readonly_query(sql: str) -> list[dict]:
    """Esegue la query SQL in modalità read-only e restituisce i risultati."""
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


def format_rows_as_text(rows: list[dict]) -> str:
    """Converte i risultati in testo leggibile da passare all'AI per la risposta naturale."""
    if not rows:
        return "Nessun risultato trovato."
    lines = []
    for row in rows[:15]:
        parts = []
        for key, val in row.items():
            if val is not None:
                parts.append(f"{key}={val}")
        lines.append(", ".join(parts))
    result = "\n".join(lines)
    if len(rows) > 15:
        result += f"\n(... e altri {len(rows) - 15} risultati)"
    return result


def ask_groq_for_natural_response(user_question: str, data_text: str) -> str:
    """Chiede a Groq di formulare una risposta naturale in italiano dai dati grezzi."""
    prompt = f"""L'utente ha chiesto: "{user_question}"

I dati dal database sono:
{data_text}

Rispondi all'utente in italiano naturale e conciso, come se fossi un assistente aziendale professionale."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_NATURAL},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=400
    )
    return response.choices[0].message.content.strip()


def answer_question(user_question: str) -> str:
    """Pipeline completa: domanda → SQL → esecuzione → risposta in italiano naturale."""
    try:
        # Step 1: genera SQL
        sql = ask_groq_for_sql(user_question)

        # Step 2: esegui la query
        rows = run_readonly_query(sql)

        # Step 3: converti i dati in testo grezzo
        data_text = format_rows_as_text(rows)

        # Step 4: chiedi a Groq di rispondere in italiano naturale
        natural_response = ask_groq_for_natural_response(user_question, data_text)

        return natural_response

    except ValueError as e:
        return f"⛔ Operazione non permessa: {e}"
    except Exception as e:
        return f"❌ Non ho capito la domanda o c'è stato un problema tecnico.\nDettaglio: `{e}`"
