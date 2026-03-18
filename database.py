import os
import psycopg
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv
import datetime

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Inizializza un pool di connessioni globale
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10, kwargs={"autocommit": True})

def parse_date(date_val):
    """Cerca di interpretare una stringa o datetime restituendo un oggetto datetime.date"""
    if not date_val: return None
    if isinstance(date_val, datetime.date): return date_val
    if isinstance(date_val, str):
        val = date_val.strip()[:10]
        # Tentativo 1 YYYY-MM-DD
        try:
            return datetime.datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            pass
        # Tentativo 2 DD/MM/YYYY
        try:
            return datetime.datetime.strptime(val, "%d/%m/%Y").date()
        except ValueError:
            pass
    return None

def format_date_it(date_val):
    """Restituisce la data sempre in formato gg/mm/yyyy stringa per l'UI"""
    dt = parse_date(date_val)
    if dt:
        return dt.strftime("%d/%m/%Y")
    return "Data non valida"

def format_eur(val, show_symbol=True):
    """Formatta un numero in Euro (es: € 1.234,56 o 1.234,56)."""
    try:
        val_float = float(val) if val else 0.0
        formattato = f"{val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"€ {formattato}" if show_symbol else formattato
    except (ValueError, TypeError):
        return "€ 0,00" if show_symbol else "0,00"

def get_connection():
    """Restituisce una connessione dal pool al database."""
    return pool.connection()

def get_preventivi():
    """Recupera la lista dei preventivi dal database, ordinati per data decrescente."""
    query = """
    SELECT 
        id, 
        nome_cliente, 
        data_creazione, 
        status, 
        totale_generale 
    FROM preventivo 
    ORDER BY data_creazione DESC
    LIMIT 100;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                # Otteniamo i nomi delle colonne
                columns = [desc[0] for desc in cur.description]
                # Creiamo una lista di dizionari per facilitare l'uso nell'UI
                results = [dict(zip(columns, row)) for row in cur.fetchall()]
                return results
    except Exception as e:
        print(f"Errore query DB: {e}")
        return []

def get_dashboard_stats():
    """Recupera le statistiche per la dashboard contanto i vari status dei preventivi."""
    stats = {
        "attivi": 0,    # Status CONFERMATO
        "in_attesa": 0, # Status BOZZA
        "completati": 0,
        "totale": 0
    }
    
    query = """
    SELECT status, COUNT(*) 
    FROM preventivo 
    GROUP BY status;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()
                
                for row in results:
                    status = (row[0] or "").upper()
                    count = row[1]
                    stats["totale"] += count
                    
                    if status == "CONFERMATO":
                        stats["attivi"] += count
                    elif status == "BOZZA":
                        stats["in_attesa"] += count
                    else:
                        stats["completati"] += count
                        
                return stats
    except Exception as e:
        print(f"Errore query DB Statistiche: {e}")
        return stats

def get_preventivo_by_id(pid):
    """Restituisce un singolo record preventivo per ID."""
    query = """
    SELECT *
    FROM preventivo 
    WHERE id = %s
    LIMIT 1;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (pid,))
                row = cur.fetchone()
                if row:
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
                return None
    except Exception as e:
        print(f"Errore query DB preventivo_by_id {pid}: {e}")
        return None

def get_righe_preventivo(pid):
    """Restituisce tutte le righe/ambienti associati a un preventivo."""
    query = """
    SELECT *
    FROM righepreventivo 
    WHERE preventivo_id = %s AND parent_id IS NULL
    ORDER BY id ASC;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (pid,))
                columns = [desc[0] for desc in cur.description]
                results = [dict(zip(columns, row)) for row in cur.fetchall()]
                return results
    except Exception as e:
        print(f"Errore query DB righe_preventivo {pid}: {e}")
        return []

def get_upcoming_scadenze():
    """Recupera tutte le date di consegna e installazione dai progetti attivi/bozza."""
    query = """
    SELECT r.data_consegna, r.data_installazione, p.nome_cliente, r.ambiente, r.descrizione, p.id as preventivo_id
    FROM righepreventivo r
    JOIN preventivo p ON r.preventivo_id = p.id
    WHERE UPPER(p.status) IN ('CONFERMATO', 'FATTURATO') AND r.parent_id IS NULL;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as e:
        print(f"Errore query DB upcoming_scadenze: {e}")
        return []

def get_all_scadenze():
    """Recupera tutte le scadenze (consegne e installazioni) con fornitore, qta e cliente per la vista Liste."""
    query = """
    SELECT 
        r.data_consegna, 
        r.data_installazione, 
        p.nome_cliente, 
        r.ambiente, 
        r.descrizione,
        r.fornitore,
        r.quantita,
        p.id as preventivo_id
    FROM righepreventivo r
    JOIN preventivo p ON r.preventivo_id = p.id
    WHERE UPPER(p.status) IN ('CONFERMATO', 'FATTURATO')
      AND (r.data_consegna IS NOT NULL OR r.data_installazione IS NOT NULL)
      AND r.parent_id IS NULL;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as e:
        print(f"Errore query DB get_all_scadenze: {e}")
        return []

def get_redditivita_stats():
    """Recupera le statistiche di utile e fatturato per categoria dai progetti confermati/fatturati."""
    query = """
    SELECT 
        COALESCE(r.categoria, 'Altro') AS categoria,
        SUM(COALESCE(r.utile_euro, 0)) AS utile_netto,
        SUM(COALESCE(r.prezzo_vendita_no_iva, 0)) AS fatturato_no_iva
    FROM righepreventivo r
    JOIN preventivo p ON r.preventivo_id = p.id
    WHERE UPPER(p.status) IN ('FATTURATO', 'CONFERMATO') AND r.parent_id IS NULL
    GROUP BY COALESCE(r.categoria, 'Altro')
    HAVING SUM(COALESCE(r.prezzo_vendita_no_iva, 0)) > 0
    ORDER BY utile_netto DESC
    LIMIT 20;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as e:
        print(f"Errore query DB get_redditivita_stats: {e}")
        return []
