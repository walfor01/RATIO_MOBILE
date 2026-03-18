"""
scheduler.py — Job giornaliero per gli Alert Scadenze.
Viene chiamato ogni mattina alle 08:00 dal bot.
"""

import datetime
import psycopg
from bot.config import DATABASE_URL, ALERT_DAYS_AHEAD


def get_scadenze_imminenti() -> list[dict]:
    """
    Recupera le scadenze (consegne e installazioni) nei prossimi N giorni.
    """
    today = datetime.date.today()
    deadline = today + datetime.timedelta(days=ALERT_DAYS_AHEAD)

    query = """
    SELECT
        p.nome_cliente,
        r.ambiente,
        r.descrizione,
        r.fornitore,
        r.data_consegna,
        r.data_installazione,
        p.id as preventivo_id
    FROM righepreventivo r
    JOIN preventivo p ON r.preventivo_id = p.id
    WHERE UPPER(p.status) IN ('CONFERMATO', 'FATTURATO')
      AND (
          (r.data_consegna IS NOT NULL AND r.data_consegna BETWEEN %s AND %s)
          OR
          (r.data_installazione IS NOT NULL AND r.data_installazione BETWEEN %s AND %s)
      )
    ORDER BY LEAST(
        COALESCE(r.data_consegna, '9999-01-01'),
        COALESCE(r.data_installazione, '9999-01-01')
    ) ASC;
    """
    try:
        with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(query, (today, deadline, today, deadline))
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as e:
        print(f"[Scheduler] Errore DB: {e}")
        return []


def build_alert_message() -> str | None:
    """
    Compone il messaggio di alert giornaliero.
    Restituisce None se non ci sono scadenze imminenti.
    """
    scadenze = get_scadenze_imminenti()
    if not scadenze:
        return None

    today = datetime.date.today()
    lines = [f"🚨 *RATIO Alert* — Scadenze prossimi {ALERT_DAYS_AHEAD} giorni\n"]

    for s in scadenze:
        cliente = s.get("nome_cliente", "N/A")
        ambiente = s.get("descrizione") or s.get("ambiente") or "Articolo"
        pid = s.get("preventivo_id", "")

        # Scadenza consegna
        if s.get("data_consegna"):
            dc = s["data_consegna"]
            if isinstance(dc, datetime.date):
                days_left = (dc - today).days
                emoji = "📦"
                timing = f"tra {days_left} giorno/i" if days_left > 0 else "⚠️ OGGI"
                lines.append(
                    f"{emoji} *Consegna* — {cliente} / {ambiente}\n"
                    f"   → {dc.strftime('%d/%m/%Y')} ({timing})"
                    + (f" | Fornitore: {s['fornitore']}" if s.get("fornitore") else "")
                )

        # Scadenza montaggio
        if s.get("data_installazione"):
            di = s["data_installazione"]
            if isinstance(di, datetime.date):
                days_left = (di - today).days
                emoji = "🔧"
                timing = f"tra {days_left} giorno/i" if days_left > 0 else "⚠️ OGGI"
                lines.append(
                    f"{emoji} *Montaggio* — {cliente} / {ambiente}\n"
                    f"   → {di.strftime('%d/%m/%Y')} ({timing})"
                )

    lines.append(f"\n_Totale scadenze: {len(scadenze)}_")
    return "\n".join(lines)
