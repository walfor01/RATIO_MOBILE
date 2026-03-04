"""
ai_sql.py — Chat-to-SQL libero con retry automatico su errore.
L'utente scrive liberamente, Groq genera SQL, se fallisce prova a correggersi.
"""

import re
import decimal
import datetime
import psycopg
from groq import Groq
from bot.config import GROQ_API_KEY, DATABASE_URL

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_SQL = """Sei un esperto SQL per PostgreSQL. Gestisci un database di un'azienda italiana di arredamento su misura chiamata RATIO.

SCHEMA ESATTO (usa SOLO queste tabelle e colonne):

TABELLA preventivo:
  id, nome_cliente, data_creazione, status, totale_generale, totale_ivato

  status può essere: 'BOZZA', 'CONFERMATO', 'FATTURATO', 'ANNULLATO'

TABELLA righepreventivo:
  id, preventivo_id, ambiente, descrizione, categoria, fornitore,
  quantita, prezzo_vendita_no_iva, prezzo_vendita_ivato, utile_euro,
  data_consegna, data_installazione

DIZIONARIO SINONIMI (l'utente usa questi termini):
- "ordini", "commesse", "cantieri", "lavori", "progetti" → si riferisce a "preventivo"
- "fatturato", "ricavi", "vendite", "incassato" → SUM(totale_generale) su status IN ('CONFERMATO','FATTURATO')
- "attivi", "aperti", "in corso" → status = 'CONFERMATO'
- "margine", "utile", "guadagno", "profitto" → utile_euro in righepreventivo
- "consegne", "scadenze", "in arrivo" → data_consegna o data_installazione

GESTIONE DATE (data_consegna e data_installazione sono VARCHAR con formato misto):
Per confrontare le date usa SEMPRE questa espressione:
CASE WHEN col LIKE '__/__/____' THEN TO_DATE(col,'DD/MM/YYYY')
     WHEN col LIKE '____-__-__' THEN TO_DATE(col,'YYYY-MM-DD')
     ELSE NULL END

Sostituisci "col" con la colonna specifica.

REGOLE:
1. Genera SOLO SELECT. Mai INSERT/UPDATE/DELETE/DROP/ALTER.
2. Rispondi SOLO con SQL puro. Niente markdown, backtick o spiegazioni.
3. Per status usa UPPER(status).
4. LIMIT 20 sempre.
5. Usa SOLO le colonne elencate sopra - non inventare mai colonne nuove."""

SYSTEM_NATURAL = """Sei un assistente aziendale professionale italiano per RATIO, azienda di arredamento.
Converti dati grezzi in risposte naturali, concise e professionali in italiano.
- Numeri in euro: es. 181.494,78 €
- Usa emoji con misura
- Sii diretto e umano
- Se non ci sono dati dillo gentilmente"""


def _clean_sql(raw: str) -> str:
    return re.sub(r"```(?:sql)?", "", raw).strip("`").strip()


def _fmt_val(v) -> str:
    if isinstance(v, (decimal.Decimal, float)):
        return f"{float(v):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(v, datetime.date):
        return v.strftime("%d/%m/%Y")
    return str(v) if v is not None else "—"


def _rows_to_text(rows) -> str:
    if not rows:
        return "Nessun dato trovato."
    if isinstance(rows, dict):
        return "\n".join(f"{k}: {_fmt_val(v)}" for k, v in rows.items() if v is not None)
    lines = []
    for i, row in enumerate(rows[:15], 1):
        parts = [f"{k}: {_fmt_val(v)}" for k, v in row.items() if v is not None]
        lines.append(f"{i}. " + " | ".join(parts))
    if len(rows) > 15:
        lines.append(f"... e altri {len(rows)-15} risultati")
    return "\n".join(lines)


def _run_sql(sql: str) -> list[dict]:
    """Esegue SQL in sola lettura."""
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate"]
    if any(k in sql.lower() for k in forbidden):
        raise ValueError("Operazione non permessa")
    with psycopg.connect(DATABASE_URL) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def _generate_sql(user_question: str, error_context: str = "") -> str:
    """Chiede a Groq di generare SQL. Se c'è un errore precedente lo include per autocorrezione."""
    messages = [{"role": "system", "content": SYSTEM_SQL}]
    if error_context:
        messages.append({"role": "user", "content": user_question})
        messages.append({"role": "assistant", "content": error_context})
        messages.append({"role": "user", "content": f"Errore SQL: {error_context}. Genera una query corretta usando SOLO le colonne dello schema."})
    else:
        messages.append({"role": "user", "content": user_question})

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.05,
        max_tokens=600
    )
    return _clean_sql(resp.choices[0].message.content)


def _natural(user_question: str, data_text: str) -> str:
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_NATURAL},
            {"role": "user", "content": f'Domanda: "{user_question}"\n\nDati:\n{data_text}\n\nRispondi in italiano naturale.'}
        ],
        temperature=0.3, max_tokens=300
    )
    return resp.choices[0].message.content.strip()


def answer_question(user_question: str) -> str:
    """Pipeline: domanda → SQL → esecuzione (con retry su errore) → risposta naturale."""
    last_error = ""
    for attempt in range(3):  # max 3 tentativi
        try:
            sql = _generate_sql(user_question, last_error if attempt > 0 else "")

            # Blocco sicurezza
            forbidden = ["insert", "update", "delete", "drop", "alter", "truncate"]
            if any(k in sql.lower() for k in forbidden):
                return "⛔ Operazione non permessa."

            rows = _run_sql(sql)
            data_text = _rows_to_text(rows)
            return _natural(user_question, data_text)

        except Exception as e:
            last_error = str(e)
            if attempt == 2:  # ultimo tentativo fallito
                if "does not exist" in last_error:
                    return "⚠️ Non riesco a trovare i dati per questa domanda. Prova con: *fatturato*, *scadenze*, *clienti*, oppure il nome di un cliente."
                return "❌ Problema tecnico temporaneo. Riprova tra poco."
            # continua con retry includendo l'errore
            continue
