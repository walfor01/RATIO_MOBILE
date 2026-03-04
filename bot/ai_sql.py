"""
ai_sql.py — Chat-to-SQL libero con validazione colonne.
L'utente scrive liberamente, Groq genera SQL, il sistema valida le colonne
prima dell'esecuzione per evitare errori da colonne inventate.
"""

import re
import decimal
import datetime
import psycopg
from groq import Groq
from bot.config import GROQ_API_KEY, DATABASE_URL

client = Groq(api_key=GROQ_API_KEY)

# ─── Colonne REALI del database (whitelist per validazione) ─────────────────
VALID_COLUMNS = {
    # preventivo
    "id", "nome_cliente", "data_creazione", "status",
    "totale_generale", "totale_ivato",
    # righepreventivo
    "preventivo_id", "ambiente", "descrizione", "categoria",
    "fornitore", "quantita", "prezzo_vendita_no_iva",
    "prezzo_vendita_ivato", "utile_euro",
    "data_consegna", "data_installazione",
    # alias comuni usati nelle query
    "fatturato", "totale", "count", "sum", "avg", "max", "min",
    "numero_preventivi", "valore", "valore_totale", "fatturato_totale",
    "utile_totale", "righe", "preventivi", "nome", "cliente",
}

# ─── Sistema prompt per la generazione SQL ──────────────────────────────────
SYSTEM_SQL = """Sei un esperto SQL per PostgreSQL. Hai accesso a questo database di un'azienda italiana di arredamento chiamata RATIO.

TABELLA preventivo:
  id (integer), nome_cliente (varchar), data_creazione (date),
  status (varchar) — valori: 'BOZZA', 'CONFERMATO', 'FATTURATO', 'ANNULLATO',
  totale_generale (numeric) — imponibile in €,
  totale_ivato (numeric) — totale con IVA in €

TABELLA righepreventivo:
  id (integer), preventivo_id (integer FK→preventivo.id),
  ambiente (varchar), descrizione (varchar), categoria (varchar),
  fornitore (varchar), quantita (numeric),
  prezzo_vendita_no_iva (numeric), prezzo_vendita_ivato (numeric),
  utile_euro (numeric) — margine netto,
  data_consegna (varchar) — può essere 'DD/MM/YYYY' o 'YYYY-MM-DD',
  data_installazione (varchar) — stesso formato di data_consegna

REGOLE CRITICHE:
1. Genera SOLO SELECT. Mai INSERT/UPDATE/DELETE/DROP/ALTER.
2. Rispondi SOLO con SQL puro. Zero spiegazioni o markdown.
3. Per status: usa UPPER(status) nei confronti.
4. Per le date (data_consegna, data_installazione): sono VARCHAR con formato misto.
   Usa questa espressione sicura per convertirle:
   CASE WHEN data_consegna LIKE '__/__/____' THEN TO_DATE(data_consegna,'DD/MM/YYYY')
        WHEN data_consegna LIKE '____-__-__' THEN TO_DATE(data_consegna,'YYYY-MM-DD')
        ELSE NULL END
5. Quando l'utente chiede "fatturato", "ricavi", "vendite": usa totale_generale con status IN ('CONFERMATO','FATTURATO').
6. Quando l'utente chiede "utile" o "margine": usa utile_euro da righepreventivo.
7. LIMIT 20 sempre.
8. USA SOLO colonne elencate sopra. Non inventare colonne."""

SYSTEM_NATURAL = """Sei un assistente aziendale professionale italiano per RATIO, azienda di arredamento di lusso.
Trasformi dati del database in risposte concise e naturali in italiano.
- Numeri in euro: 181.494,78 €
- Usa emoji appropriate ma con misura
- Sii diretto e professionale
- Se non ci sono dati, dillo gentilmente"""


def _clean_sql(raw: str) -> str:
    """Rimuove markdown extra dal SQL generato da Groq."""
    return re.sub(r"```(?:sql)?", "", raw).strip("`").strip()


def _validate_columns(sql: str) -> list[str]:
    """Controlla che il SQL non contenga colonne inventate. Restituisce lista di colonne sconosciute."""
    # Estrae parole che potrebbero essere nomi di colonna (dopo SELECT, WHERE, ORDER BY ecc.)
    # Rimuovi stringhe tra apici, numeri, keywords SQL e funzioni note
    sql_clean = re.sub(r"'[^']*'", "", sql)  # rimuovi stringhe
    sql_clean = re.sub(r"\b\d+\b", "", sql_clean)  # rimuovi numeri
    tokens = re.findall(r"\b([a-z_][a-z0-9_]*)\b", sql_clean.lower())

    sql_keywords = {
        "select", "from", "where", "join", "on", "and", "or", "not",
        "in", "like", "between", "is", "null", "order", "by", "group",
        "having", "limit", "offset", "as", "distinct", "case", "when",
        "then", "else", "end", "upper", "lower", "coalesce", "sum",
        "count", "avg", "max", "min", "to_date", "current_date",
        "interval", "cast", "inner", "left", "right", "outer",
        "preventivo", "righepreventivo", "desc", "asc", "true", "false",
        "varchar", "integer", "numeric", "date", "days"
    }

    unknown = []
    for token in tokens:
        if token not in sql_keywords and token not in VALID_COLUMNS and len(token) > 2:
            unknown.append(token)

    return unknown


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


def _natural(user_question: str, data_text: str) -> str:
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_NATURAL},
            {"role": "user", "content": f'L\'utente ha chiesto: "{user_question}"\n\nDati:\n{data_text}\n\nRispondi in italiano naturale e conciso.'}
        ],
        temperature=0.3, max_tokens=300
    )
    return resp.choices[0].message.content.strip()


def answer_question(user_question: str) -> str:
    """Pipeline: domanda libera → SQL (Groq) → validazione colonne → esecuzione → risposta naturale."""
    try:
        # Step 1: genera SQL
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_SQL},
                {"role": "user", "content": user_question}
            ],
            temperature=0.05,
            max_tokens=600
        )
        sql = _clean_sql(resp.choices[0].message.content)

        # Step 2: valida colonne
        unknown = _validate_columns(sql)
        if unknown:
            # Filtra falsi positivi comuni
            real_unknown = [u for u in unknown if u not in {
                "imponibile", "ivato", "attivi", "confermati", "recenti"
            }]
            if real_unknown:
                return (f"⚠️ Non ho trovato nel database alcuni elementi della tua domanda. "
                        f"Prova a riformulare.\n_(riferimento a: {', '.join(real_unknown[:3])})_")

        # Step 3: esegui
        rows = _run_sql(sql)

        # Step 4: risposta naturale
        data_text = _rows_to_text(rows)
        return _natural(user_question, data_text)

    except ValueError as e:
        return f"⛔ {e}"
    except Exception as e:
        err = str(e)
        if "does not exist" in err:
            return "⚠️ Non ho capito la domanda. Prova a riformularla diversamente."
        if "out of range" in err or "invalid input" in err:
            return "⚠️ Problema nel confronto delle date. Prova con: *'consegne di marzo'* o *'scadenze prossimi 7 giorni'*."
        return f"❌ Problema tecnico. Riprova tra poco."
