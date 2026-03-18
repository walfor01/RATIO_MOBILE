"""
ai_sql.py — Chat-to-SQL libero con retry semplificato e preprocessing date.
"""

import re
import decimal
import datetime
import psycopg
from groq import Groq
from bot.config import GROQ_API_KEY, DATABASE_URL
from database import format_eur

client = Groq(api_key=GROQ_API_KEY)


# ─── Pre-processing date relative ──────────────────────────────────────────
def _enrich_with_dates(question: str) -> str:
    """Aggiunge le date concrete alla domanda per aiutare Groq a generare SQL corretto."""
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    week_end = today + datetime.timedelta(days=7)
    month_end = today + datetime.timedelta(days=30)

    date_context = (
        f"[Riferimento temporale: oggi={today.strftime('%Y-%m-%d')}, "
        f"domani={tomorrow.strftime('%Y-%m-%d')}, "
        f"fra 7 giorni={week_end.strftime('%Y-%m-%d')}, "
        f"fra 30 giorni={month_end.strftime('%Y-%m-%d')}] "
    )
    # Aggiunge il contesto solo se la domanda contiene riferimenti temporali
    time_keywords = ["domani", "oggi", "settimana", "mese", "prossim", "giorni", "scadenz", "consegn"]
    if any(k in question.lower() for k in time_keywords):
        return date_context + question
    return question

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
    """Rimuove markdown e blocchi <think> (DeepSeek reasoning) dal SQL generato."""
    # Rimuovi blocchi <think>...</think> del modello reasoning
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    # Rimuovi markdown
    raw = re.sub(r"```(?:sql)?", "", raw).strip("`").strip()
    # Se c'è ancora testo prima del SELECT, prendi solo la parte SQL
    if "SELECT" in raw.upper():
        idx = raw.upper().find("SELECT")
        raw = raw[idx:]
    return raw.strip()


def _fmt_val(v) -> str:
    if isinstance(v, (decimal.Decimal, float)):
        return format_eur(v)
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


def _generate_sql(question: str, prev_sql: str = "", prev_error: str = "") -> str:
    """Chiede a Groq di generare SQL, con correzione automatica se c'è un errore precedente."""
    enriched = _enrich_with_dates(question)
    messages = [{"role": "system", "content": SYSTEM_SQL}]

    if prev_sql and prev_error:
        # Retry: mostra il tentativo precedente con il suo errore e chiedi correzione
        msg = (
            f"Domanda: {enriched}\n\n"
            f"Hai generato questo SQL che ha prodotto un errore:\n{prev_sql}\n\n"
            f"Errore: {prev_error}\n\n"
            f"Genera un SQL corretto usando SOLO le colonne dello schema elencate."
        )
        messages.append({"role": "user", "content": msg})
    else:
        messages.append({"role": "user", "content": enriched})

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.05,
        max_tokens=800
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
    """Pipeline: domanda → SQL → esecuzione (con retry corretto su errore) → risposta naturale."""
    last_sql = ""
    last_error = ""

    for attempt in range(2):  # max 2 tentativi
        try:
            last_sql = _generate_sql(user_question, last_sql if attempt > 0 else "", last_error if attempt > 0 else "")

            # Blocco sicurezza
            forbidden = ["insert", "update", "delete", "drop", "alter", "truncate"]
            if any(k in last_sql.lower() for k in forbidden):
                return "Operazione non permessa."

            rows = _run_sql(last_sql)
            data_text = _rows_to_text(rows)
            return _natural(user_question, data_text)

        except Exception as e:
            last_error = str(e)
            if attempt == 1:  # secondo tentativo fallito
                if "does not exist" in last_error:
                    return "Non riesco a trovare i dati. Prova a riformulare la domanda in modo diverso."
                if "out of range" in last_error or "invalid input" in last_error:
                    return "Errore nel formato delle date. Prova con: 'consegne prossimi 7 giorni' o 'scadenze di marzo'."
                return "Problema tecnico temporaneo. Riprova tra poco."
            continue  # riprova con la correzione
