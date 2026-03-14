"""
queries.py — Query SQL predefinite e testate per RATIO.
Usate dal bot al posto di lasciare che l'AI inventi SQL da zero.
"""

import datetime
import psycopg
from bot.config import DATABASE_URL


def _exec(sql: str, params=None) -> list[dict]:
    """Esegue una query in sola lettura e restituisce i risultati come lista di dict."""
    with psycopg.connect(DATABASE_URL) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


# ─── QUERY PREDEFINITE ─────────────────────────────────────────────────────────

def q_fatturato() -> dict:
    """Fatturato totale (CONFERMATO + FATTURATO)."""
    rows = _exec("""
        SELECT
            SUM(totale_generale)  AS imponibile,
            SUM(totale_ivato)     AS ivato,
            COUNT(*)              AS numero_preventivi
        FROM preventivo
        WHERE UPPER(status) IN ('CONFERMATO', 'FATTURATO')
    """)
    return rows[0] if rows else {}


def q_preventivi_per_status() -> list[dict]:
    """Conteggio preventivi per stato."""
    return _exec("""
        SELECT status, COUNT(*) AS totale, SUM(totale_generale) AS valore
        FROM preventivo
        GROUP BY status
        ORDER BY totale DESC
    """)


def q_scadenze_prossimi_giorni(giorni: int = 14) -> list[dict]:
    """Scadenze (consegne e montaggi) nei prossimi N giorni.
       Gestisce sia il formato YYYY-MM-DD che DD/MM/YYYY."""
    today = datetime.date.today()
    future = today + datetime.timedelta(days=giorni)

    # Prova prima a capire il formato dal primo record non nullo
    fmt_rows = _exec("""
        SELECT data_consegna FROM righepreventivo
        WHERE data_consegna IS NOT NULL AND data_consegna != ''
        LIMIT 1
    """)

    if fmt_rows:
        sample = str(fmt_rows[0].get("data_consegna", ""))
        # Se contiene '/' è DD/MM/YYYY, altrimenti YYYY-MM-DD
        if "/" in sample:
            date_format = "DD/MM/YYYY"
        else:
            date_format = "YYYY-MM-DD"
    else:
        date_format = "YYYY-MM-DD"

    sql = f"""
        SELECT
            p.nome_cliente,
            r.ambiente,
            r.data_consegna,
            r.data_installazione,
            p.status
        FROM righepreventivo r
        JOIN preventivo p ON r.preventivo_id = p.id
        WHERE UPPER(p.status) IN ('CONFERMATO', 'FATTURATO')
          AND (
            (r.data_consegna IS NOT NULL AND r.data_consegna != ''
             AND TO_DATE(r.data_consegna, '{date_format}') BETWEEN %s AND %s)
            OR
            (r.data_installazione IS NOT NULL AND r.data_installazione != ''
             AND TO_DATE(r.data_installazione, '{date_format}') BETWEEN %s AND %s)
          )
        ORDER BY r.data_consegna
        LIMIT 20
    """
    return _exec(sql, (today, future, today, future))


def q_clienti_principali(limit: int = 10) -> list[dict]:
    """Top clienti per valore totale preventivi confermati."""
    return _exec("""
        SELECT nome_cliente, COUNT(*) AS preventivi, SUM(totale_generale) AS valore_totale
        FROM preventivo
        WHERE UPPER(status) IN ('CONFERMATO', 'FATTURATO')
        GROUP BY nome_cliente
        ORDER BY valore_totale DESC
        LIMIT %s
    """, (limit,))


def q_preventivi_recenti(limit: int = 10) -> list[dict]:
    """Ultimi preventivi creati."""
    return _exec("""
        SELECT nome_cliente, status, totale_generale, data_creazione
        FROM preventivo
        ORDER BY data_creazione DESC
        LIMIT %s
    """, (limit,))


def q_utile_totale() -> dict:
    """Utile (margine) totale sui cantieri attivi."""
    rows = _exec("""
        SELECT SUM(r.utile_euro) AS utile_totale
        FROM righepreventivo r
        JOIN preventivo p ON r.preventivo_id = p.id
        WHERE UPPER(p.status) IN ('CONFERMATO', 'FATTURATO')
    """)
    return rows[0] if rows else {}


def q_fornitore_statistiche() -> list[dict]:
    """Acquisti per fornitore."""
    return _exec("""
        SELECT fornitore, COUNT(*) AS righe, SUM(prezzo_vendita_no_iva) AS valore_totale
        FROM righepreventivo
        WHERE fornitore IS NOT NULL AND fornitore != ''
        GROUP BY fornitore
        ORDER BY valore_totale DESC
        LIMIT 15
    """)


def q_cerca_cliente(nome: str) -> list[dict]:
    """Cerca preventivi di uno specifico cliente."""
    return _exec("""
        SELECT id, nome_cliente, status, totale_generale, data_creazione
        FROM preventivo
        WHERE LOWER(nome_cliente) LIKE LOWER(%s)
        ORDER BY data_creazione DESC
        LIMIT 10
    """, (f"%{nome}%",))
