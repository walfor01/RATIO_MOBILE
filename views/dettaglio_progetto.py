import flet as ft
from database import get_preventivo_by_id, get_righe_preventivo, format_date_it, format_eur

def DettaglioProgettoView(page: ft.Page, project_id: int, go_back_func):
    """Componente per visualizzare i dettagli di un singolo Progetto - Stile RATIO"""
    text_color = "#3D3935"
    bg_card = "#E8E2D9"
    
    # 1. Header con freccia di ritorno e Logo
    header = ft.Row(
        controls=[
            ft.IconButton(
                icon=ft.icons.ARROW_BACK,
                icon_color=text_color,
                on_click=lambda _: go_back_func(),
                bgcolor=bg_card,
            ),
            ft.Image(src="logo_ratio.png", height=36, fit=ft.ImageFit.CONTAIN),
            ft.Container(width=40) # Spazio vuoto per bilanciare l'icona a sinistra e centrare il logo
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    # Fetch dati veri
    preventivo = get_preventivo_by_id(project_id)
    righe = get_righe_preventivo(project_id)

    if not preventivo:
        return ft.Container(
            content=ft.Column([header, ft.Text("Progetto non trovato.", color=text_color)]),
            padding=20
        )

    nome_cliente = preventivo.get("nome_cliente") or "Sconosciuto"
    totale = preventivo.get("totale_generale") or 0.0
    status = preventivo.get("status") or "N/A"
    
    # Badge Logic
    status_upper = status.upper()
    if status_upper == "CONFERMATO":
        status_text = "Confermato"
        status_bg = "#80B98A"
    elif status_upper == "BOZZA":
        status_text = "Bozza"
        status_bg = "#EBA661"
    else:
        status_text = "Completato"
        status_bg = "#8A837C"
        
    totale_str = format_eur(totale)

    # 2. Titolo
    title_row = ft.Text("Dettaglio Progetto", size=24, weight=ft.FontWeight.W_600, color=text_color)

    # Calcolo totale utile e imponibile
    totale_utile = 0.0
    totale_imponibile = 0.0
    for r in righe:
        val_utile = r.get("utile_euro")
        if val_utile:
            try:
                totale_utile += float(val_utile)
            except ValueError:
                pass
                
        val_imponibile = r.get("prezzo_vendita_no_iva")
        if val_imponibile:
            try:
                totale_imponibile += float(val_imponibile)
            except ValueError:
                pass
        
    # Prendiamo la descrizione dalla testata del preventivo
    descrizione_progetto = preventivo.get("descrizione") or preventivo.get("note") or "Nessuna descrizione specificata."
        
    delta_str = format_eur(totale_utile)
    imponibile_str = format_eur(totale_imponibile)
    
    # Costo Studio = Imponibile - Delta (utile)
    totale_costo = totale_imponibile - totale_utile
    costo_str = format_eur(totale_costo)

    # 3. Card Hero (Riepilogo alto)
    hero_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(f"{nome_cliente} (Progetto {project_id})", size=16, weight=ft.FontWeight.BOLD, color=text_color),
                ft.Container(
                    content=ft.Text(status_text, size=10, weight=ft.FontWeight.W_600, color="#FFFFFF"),
                    bgcolor=status_bg,
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    border_radius=12,
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(f"{descrizione_progetto}", size=11, color="#8A837C", italic=True),
            ft.Container(height=5),
            ft.Text(f"Cliente: {nome_cliente}", size=13, color=text_color),
            ft.Text(f"Tot. Imponibile: {imponibile_str}", size=13, color=text_color),
            ft.Text(f"Tot. Ivato: {totale_str}", size=13, color=text_color),
            ft.Text(f"Costo Studio: {costo_str}", size=13, color=text_color),
            ft.Text(f"Delta: {delta_str}", size=13, color=text_color),
        ], spacing=2),
        bgcolor=bg_card,
        padding=15,
        border_radius=12,
    )

    # 4. Custom Tabs (Riepilogo, Ambienti, Timeline)
    # Creiamo un content dinamico
    tab_content = ft.Column(spacing=15)
    
    def render_riepilogo():
        # Costruzione del contenuto Riepilogo ("Preventivo", "Scadenze", "Note") come da mockup
        
        # Preventivo section (Elenco di tutte le righe/voci per Descrizione)
        voci_rows = []
        for r in righe:
            desc = r.get("descrizione") or r.get("ambiente") or "Voce generica"
            prezz_fin = r.get("prezzo_vendita_no_iva") or 0.0
            val_str = format_eur(prezz_fin)
            
            # Tronchiamo la descrizione se troppo lunga per stare nella row
            desc_tronc = desc[:32] + "..." if len(desc) > 32 else desc
            
            voci_rows.append(
                ft.Row([
                    ft.Text(desc_tronc, size=13, color=text_color, tooltip=desc),
                    ft.Text(val_str, size=13, color=text_color, weight=ft.FontWeight.W_500)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
            
        # Riquadro Preventivo Scrollabile
        prev_container = ft.Container(
            content=ft.Column([
                ft.Text("Preventivo", weight=ft.FontWeight.BOLD, color=text_color, size=14),
                ft.Container(height=5),
                ft.Container(
                    content=ft.Column(voci_rows, spacing=4, scroll=ft.ScrollMode.AUTO),
                    height=130 # Fissiamo un'altezza per scroll interno
                )
            ], spacing=2),
            border=ft.border.all(1, "#EAE1D8"),
            border_radius=12,
            padding=15,
        )
        
        # Scadenze section (Prende le data_consegna e data_installazione dalle righe)
        scadenze_list = []
        
        date_consegna = set()
        date_installazione = set()
        
        for r in righe:
            if r.get("data_consegna"):
                dt = format_date_it(r.get("data_consegna"))
                if dt != "Data non valida":
                    date_consegna.add(dt)
            if r.get("data_installazione"):
                dt = format_date_it(r.get("data_installazione"))
                if dt != "Data non valida":
                    date_installazione.add(dt)
                
        if date_consegna:
            scadenze_list.append(f"Consegne: {', '.join(date_consegna)}")
        if date_installazione:
            scadenze_list.append(f"Montaggi: {', '.join(date_installazione)}")
            
        if not scadenze_list:
            scadenze_list.append("Nessuna consegna o montaggio programmato.")
            
        scadenze_controls = [ft.Text(s, size=13, color=text_color) for s in scadenze_list]

        scad_container = ft.Container(
            content=ft.Column([
                ft.Text("Scadenze", weight=ft.FontWeight.BOLD, color=text_color, size=14),
                ft.Container(height=5),
                *scadenze_controls
            ], spacing=2),
            border=ft.border.all(1, "#EAE1D8"),
            border_radius=12,
            padding=15,
        )
        
        # (Niente note, su richiesta dell'utente)
        
        return [prev_container, scad_container]
        
    def render_timeline():
        # Costruiamo una lista verticale ("Timeline") degli eventi salienti estratti dalla testata (preventivo)
        eventi_timeline = []
        
        # 1. Creazione Progetto
        dt_creazione = preventivo.get("data_creazione") 
        if dt_creazione:
            eventi_timeline.append(("Avvio Progetto (Creazione)", format_date_it(dt_creazione), "#A9937E"))
        else:
            eventi_timeline.append(("Avvio Progetto (Creazione)", "Data Sconosciuta", "#C7C0B8"))
            
        # 2. Elenco Consegne (raggruppate per data)
        consegne_dict = {}
        montaggi_dict = {}
        
        for r in righe:
            # Raggruppo consegne
            if r.get("data_consegna"):
                dt = format_date_it(r.get("data_consegna"))
                if dt != "Data non valida":
                    nome = r.get("descrizione") or r.get("ambiente") or "Articolo"
                    if dt not in consegne_dict:
                        consegne_dict[dt] = []
                    consegne_dict[dt].append(nome)
                
            # Raggruppo montaggi
            if r.get("data_installazione"):
                dt = format_date_it(r.get("data_installazione"))
                if dt != "Data non valida":
                    nome = r.get("descrizione") or r.get("ambiente") or "Articolo"
                    if dt not in montaggi_dict:
                        montaggi_dict[dt] = []
                    montaggi_dict[dt].append(nome)

        if consegne_dict:
            for dt, nomi in consegne_dict.items():
                items_str = "\n".join([f"• {n}" for n in nomi])
                eventi_timeline.append((f"Consegne in programma:\n{items_str}", dt, "#EBA661"))
        else:
            eventi_timeline.append(("Consegne", "Non definite", "#C7C0B8"))
            
        if montaggi_dict:
            for dt, nomi in montaggi_dict.items():
                items_str = "\n".join([f"• {n}" for n in nomi])
                eventi_timeline.append((f"Montaggi in programma:\n{items_str}", dt, "#80B98A"))
        else:
            eventi_timeline.append(("Montaggi", "In Attesa", "#C7C0B8"))

        timeline_controls = []
        for idx, (titolo, data_str, color) in enumerate(eventi_timeline):
            is_last = (idx == len(eventi_timeline) - 1)
            
            # Elemento della timeline (pallino e linea verticale)
            timeline_node = ft.Row([
                # Colonna di sinistra: pallino e retta
                ft.Column([
                    ft.Container(width=12, height=12, border_radius=6, bgcolor=color),
                    ft.Container(width=2, height=max(40, len(titolo.split('\n')) * 20), bgcolor=color if not is_last else ft.colors.TRANSPARENT, margin=ft.padding.only(left=5))
                ], spacing=0, alignment=ft.MainAxisAlignment.START),
                
                # Colonna di destra: Testo (Titolo e Data)
                ft.Column([
                    ft.Text(f"Data: {data_str}", color="#8A837C", size=12, weight=ft.FontWeight.W_500),
                    ft.Text(titolo, weight=ft.FontWeight.W_600, color=text_color, size=14),
                    ft.Container(height=15) # Spazio inferiore
                ], spacing=2, expand=True) # expand per evitare overflow orizzontale
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START)
            
            timeline_controls.append(timeline_node)

        # Riquadro contenitore della Timeline
        timeline_container = ft.Container(
            content=ft.Column([
                ft.Text("Fasi del Progetto", weight=ft.FontWeight.BOLD, color=text_color, size=15),
                ft.Container(height=15),
                ft.Container(
                    content=ft.Column(timeline_controls, spacing=0, scroll=ft.ScrollMode.AUTO),
                    height=250 # Fissiamo l'altezza per attivare lo scorrimento interno
                )
            ], spacing=0),
            border=ft.border.all(1, "#EAE1D8"),
            border_radius=12,
            padding=20,
        )
        
        return [timeline_container]
        
    def change_tab(e, tab_name):
        # Update colors of chips
        for c in tabs_row.controls:
            c.bgcolor = "#A9937E" if c.data == tab_name else bg_card
            c.content.color = "#FFFFFF" if c.data == tab_name else text_color
        
        tab_content.controls.clear()
        if tab_name == "Riepilogo":
            tab_content.controls.extend(render_riepilogo())
        elif tab_name == "Timeline":
            tab_content.controls.extend(render_timeline())
            
        page.update()

    def create_tab_chip(label, is_selected=False):
        return ft.Container(
            content=ft.Text(label, size=13, weight=ft.FontWeight.W_600, color="#FFFFFF" if is_selected else text_color),
            bgcolor="#A9937E" if is_selected else bg_card,
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            border_radius=20,
            on_click=lambda e: change_tab(e, label),
            data=label
        )

    tabs_row = ft.Row([
        create_tab_chip("Riepilogo", True),
        create_tab_chip("Timeline", False),
    ], spacing=10, alignment=ft.MainAxisAlignment.START)

    # Init content
    tab_content.controls.extend(render_riepilogo())

    return ft.Container(
        padding=ft.padding.only(left=20, right=20, top=20, bottom=80),
        content=ft.Column(
            controls=[
                header,
                ft.Container(height=10),
                title_row,
                ft.Container(height=10),
                hero_card,
                ft.Container(height=10),
                tabs_row,
                ft.Container(height=15),
                tab_content
            ],
            expand=True,
            spacing=0,
        )
    )
