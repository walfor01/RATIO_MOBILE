"""
ai_sql.py — Router semantico: usa Groq per interpretare la domanda
             e chiama le query predefinite da queries.py.
             Poi riformatta il risultato in italiano naturale.
"""

import decimal
import datetime
from groq import Groq
from bot.config import GROQ_API_KEY
from bot import queries

client = Groq(api_key=GROQ_API_KEY)

# ─── CATALOGO DELLE QUERY DISPONIBILI ─────────────────────────────────────────

QUERY_CATALOG = """
Hai a disposizione queste funzioni per rispondere alle domande dell'utente:

1. FATTURATO → domande su fatturato totale, ricavi, vendite, quanto abbiamo fatto
2. STATISTICHE → domande su quanti preventivi, quante bozze, quanti confermati, situazione generale
3. SCADENZE → domande su consegne, montaggi, ordini in arrivo, cosa c'è questa settimana/mese
4. CLIENTI → domande su i migliori clienti, chi ha speso di più, top clienti
5. RECENTI → domande sugli ultimi preventivi, cosa abbiamo fatto di recente
6. UTILE → domande su margine, guadagno, utile netto, profitto
7. FORNITORI → domande su fornitori, acquisti, da chi compriamo
8. CERCA:[nome] → se l'utente menziona il nome di un cliente specifico (es. "Rossi", "Bianchi")

Rispondi SOLO con una delle parole chiave sopra (es: FATTURATO, oppure CERCA:Rossi).
Non aggiungere nient'altro.
"""

NATURAL_SYSTEM = """Sei un assistente aziendale professionale italiano per RATIO, azienda di arredamento.
Trasforma dati grezzi del database in risposte concise, calde e professionali in italiano.
- Formatta i numeri in euro: es. 181.494,78 €
- Usa emoji appropriate
- Sii diretto, non verboso
- Se non ci sono dati, dillo gentilmente"""


def _rows_to_text(rows) -> str:
    """Converte risultati DB in testo leggibile per l'AI."""
    if not rows:
        return "Nessun dato disponibile."

    def fmt_val(v):
        if isinstance(v, (decimal.Decimal, float)):
            return f"{float(v):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        if isinstance(v, datetime.date):
            return v.strftime("%d/%m/%Y")
        return str(v) if v is not None else "—"

    if isinstance(rows, dict):
        return "\n".join(f"{k}: {fmt_val(v)}" for k, v in rows.items() if v is not None)

    lines = []
    for i, row in enumerate(rows[:15], 1):
        parts = [f"{k}: {fmt_val(v)}" for k, v in row.items() if v is not None]
        lines.append(f"{i}. " + " | ".join(parts))
    if len(rows) > 15:
        lines.append(f"... e altri {len(rows)-15} risultati")
    return "\n".join(lines)


def _natural_response(user_question: str, data_text: str) -> str:
    """Chiede a Groq di formulare una risposta naturale in italiano."""
    prompt = f'L\'utente ha chiesto: "{user_question}"\n\nDati dal gestionale:\n{data_text}\n\nRispondi in italiano naturale e conciso.'
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": NATURAL_SYSTEM},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=300
    )
    return resp.choices[0].message.content.strip()


def _route_question(user_question: str) -> str:
    """Usa Groq per capire quale query usare. Restituisce la keyword."""
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": QUERY_CATALOG},
            {"role": "user", "content": user_question}
        ],
        temperature=0.0,
        max_tokens=20
    )
    return resp.choices[0].message.content.strip().upper()


def answer_question(user_question: str) -> str:
    """Pipeline principale: domanda → routing → query predefinita → risposta naturale."""
    try:
        intent = _route_question(user_question)

        if intent == "FATTURATO":
            data = queries.q_fatturato()
            data_text = _rows_to_text(data)

        elif intent == "STATISTICHE":
            data = queries.q_preventivi_per_status()
            data_text = _rows_to_text(data)

        elif intent == "SCADENZE":
            data = queries.q_scadenze_prossimi_giorni(14)
            data_text = _rows_to_text(data) if data else "Nessuna scadenza nei prossimi 14 giorni."

        elif intent == "CLIENTI":
            data = queries.q_clienti_principali()
            data_text = _rows_to_text(data)

        elif intent == "RECENTI":
            data = queries.q_preventivi_recenti()
            data_text = _rows_to_text(data)

        elif intent == "UTILE":
            data = queries.q_utile_totale()
            data_text = _rows_to_text(data)

        elif intent == "FORNITORI":
            data = queries.q_fornitore_statistiche()
            data_text = _rows_to_text(data)

        elif intent.startswith("CERCA:"):
            nome = intent.replace("CERCA:", "").strip().capitalize()
            data = queries.q_cerca_cliente(nome)
            data_text = _rows_to_text(data) if data else f"Nessun cliente trovato con nome '{nome}'."

        else:
            # Fallback generico
            data = queries.q_preventivi_per_status()
            data_text = _rows_to_text(data)

        return _natural_response(user_question, data_text)

    except Exception as e:
        return f"❌ Si è verificato un problema tecnico. Riprova tra poco.\n`{e}`"
