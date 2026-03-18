import flet as ft
from database import get_all_scadenze, parse_date, format_date_it
from datetime import datetime

mesi_it = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile", 5: "Maggio", 6: "Giugno",
    7: "Luglio", 8: "Agosto", 9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
}

def ScadenzeView(page: ft.Page):
    """Componente per la vista Scadenze Intero Calendario."""
    text_color = "#3D3935"
    bg_card = "#EAE1D8"
    
    # Stato dei filtri
    state = {
        "fornitore": None,
        "cliente": None
    }
    
    # Estrazione Dati e Normalizzazione
    raw_data = get_all_scadenze()
    all_events = []
    
    fornitore_set = set()
    cliente_set = set()
    
    for r in raw_data:
        cliente = r.get("nome_cliente") or "Sconosciuto"
        fornitore = r.get("fornitore") or "Sconosciuto"
        articolo = r.get("descrizione") or r.get("ambiente") or "Articolo"
        qta = r.get("quantita") or 1
        pid = r.get("preventivo_id")
        
        cliente_set.add(cliente)
        fornitore_set.add(fornitore)
        
        # Scadenza Consegna
        if r.get("data_consegna"):
            dt = parse_date(r.get("data_consegna"))
            if dt:
                all_events.append({
                    "date_obj": dt,
                    "data_str": format_date_it(dt),
                    "tipo": "Consegna",
                    "cliente": cliente,
                    "fornitore": fornitore,
                    "articolo": articolo,
                    "quantita": qta,
                    "project_id": pid
                })
        
        # Scadenza Installazione
        if r.get("data_installazione"):
            dt = parse_date(r.get("data_installazione"))
            if dt:
                all_events.append({
                    "date_obj": dt,
                    "data_str": format_date_it(dt),
                    "tipo": "Montaggio",
                    "cliente": cliente,
                    "fornitore": fornitore,
                    "articolo": articolo,
                    "quantita": qta,
                    "project_id": pid
                })

    # Ordinamento cronologico
    all_events.sort(key=lambda x: x["date_obj"])

    # HEADER & FILTRI
    
    def on_filter_change(e):
        state["fornitore"] = fornitore_dropdown.value
        state["cliente"] = cliente_dropdown.value
        update_list()
        
    def reset_filters(e):
        fornitore_dropdown.value = None
        cliente_dropdown.value = None
        state["fornitore"] = None
        state["cliente"] = None
        page.update()
        update_list()

    fornitore_dropdown = ft.Dropdown(
        label="Filtra Fornitore",
        options=[ft.dropdown.Option(f) for f in sorted(list(fornitore_set))],
        width=160,
        height=50,
        content_padding=10,
        text_size=12,
        on_change=on_filter_change
    )
    
    cliente_dropdown = ft.Dropdown(
        label="Filtra Cliente",
        options=[ft.dropdown.Option(c) for c in sorted(list(cliente_set))],
        width=160,
        height=50,
        content_padding=10,
        text_size=12,
        on_change=on_filter_change
    )

    header = ft.Row([
        ft.Text("Scadenze & Timeline", size=22, weight=ft.FontWeight.W_600, color=text_color),
    ])
    
    filter_row = ft.Container(
        content=ft.Column([
            ft.Row([
                fornitore_dropdown,
                cliente_dropdown,
            ], scroll=ft.ScrollMode.ADAPTIVE),
            ft.Row([
                ft.TextButton(
                    "Resetta Filtri",
                    icon=ft.icons.FILTER_ALT_OFF,
                    style=ft.ButtonStyle(color="#C25925"),
                    on_click=reset_filters
                )
            ], alignment=ft.MainAxisAlignment.END)
        ], spacing=5),
        padding=ft.padding.only(top=10, bottom=10)
    )

    # VIEW LISTA MESE/EVENTI
    list_view = ft.ListView(expand=True, spacing=0, padding=0, auto_scroll=False)

    def event_card(event):
        bg_col = "#FFFFFF"
        return ft.Container(
            content=ft.Column([
                # riga 1: Data e Tipo
                ft.Row([
                    ft.Text(event["data_str"], size=13, weight=ft.FontWeight.BOLD, color=text_color),
                    ft.Text(event["tipo"], size=11, color="#8F8A84", italic=True)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                # riga 2: Fornitore (Badge) e Cliente
                ft.Container(height=2),
                ft.Row([
                    ft.Container(
                        content=ft.Text(event["fornitore"][:20], size=10, color="#6C665F"),
                        bgcolor=bg_card,
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        border_radius=10,
                    ),
                    ft.Text(event["cliente"], size=13, weight=ft.FontWeight.W_600, color=text_color),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                # riga 3: Articolo e freccia (quantità)
                ft.Container(height=4),
                ft.Row([
                    ft.Container(
                        content=ft.Text(event["articolo"], size=12, color="#7B746C", no_wrap=True),
                        width=250, # taglia testo troppo lungo
                    ),
                    ft.Row([
                        ft.Text(f"QTA: {event['quantita']}", size=11, color="#A19A8F"),
                        ft.Icon(ft.icons.CHEVRON_RIGHT, color="#C7C0B8", size=20)
                    ])
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]),
            bgcolor=bg_col,
            padding=15,
            border_radius=12,
            margin=ft.padding.only(bottom=10),
            on_click=lambda e: page.navigate_to_dettaglio(event["project_id"])
        )

    def update_list():
        list_view.controls.clear()
        
        # Filtro
        filtered_events = []
        for e in all_events:
            if state["fornitore"] and state["fornitore"] != e["fornitore"]:
                continue
            if state["cliente"] and state["cliente"] != e["cliente"]:
                continue
            filtered_events.append(e)

        if not filtered_events:
            list_view.controls.append(
                ft.Container(content=ft.Text("Nessuna scadenza trovata.", color=text_color), padding=20, alignment=ft.alignment.center)
            )
        else:
            current_month_year = None
            
            for event in filtered_events:
                # Intestazione mese
                m_y = f"{mesi_it[event['date_obj'].month]} {event['date_obj'].year}"
                if m_y != current_month_year:
                    if current_month_year is not None:
                        list_view.controls.append(ft.Container(height=10)) # separatore dai mesi precedenti
                    list_view.controls.append(
                        ft.Container(
                            content=ft.Text(m_y, size=15, weight=ft.FontWeight.BOLD, color="#B66035"),
                            padding=ft.padding.only(left=5, bottom=8, top=5)
                        )
                    )
                    current_month_year = m_y
                
                # Render singola card
                list_view.controls.append(event_card(event))
                
        page.update()

    update_list()

    return ft.Container(
        content=ft.Column(
            controls=[
                header,
                ft.Text("Monitoraggio consegne e installazioni", size=12, color="#8F8A84"),
                filter_row,
                ft.Divider(color="#E8E2D9"),
                ft.Container(height=5),
                list_view
            ],
            spacing=0
        ),
        expand=True,
        padding=20,
        bgcolor="#FAF8F5"
    )
