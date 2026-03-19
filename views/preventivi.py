import flet as ft
from database import get_preventivi, format_date_it, format_eur
from datetime import datetime

def PreventiviView(page: ft.Page):
    """Componente per visualizzare la lista dei preventivi (Progetti) da Database - Stile RATIO"""
    text_color = "#3D3935"
    bg_card = "#E8E2D9"
    
    # 1. Header con logo, campanella e filtro
    header = ft.Row(
        controls=[
            ft.Image(src="logo_ratio.png", height=36, fit=ft.ImageFit.CONTAIN),
            ft.Row([
                 ft.Container(
                    content=ft.Icon(ft.icons.FILTER_LIST, color=text_color, size=20),
                    bgcolor=bg_card,
                    padding=8,
                    border_radius=20
                )
            ], spacing=10)
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    # 2. Titolo "Progetti"
    title_row = ft.Text("Progetti", size=28, weight=ft.FontWeight.W_600, color=text_color)
    
    # 3. Search Bar
    # Creiamo uno state per filtri e ricerca
    state = {
        "filter": "Confermati",
        "search": ""
    }
    
    def on_search_change(e):
        state["search"] = e.control.value.lower()
        update_list()

    search_field = ft.TextField(
        hint_text="Cerca progetti...",
        border=ft.InputBorder.NONE,
        height=40,
        color=text_color,
        hint_style=ft.TextStyle(color="#A19A8F"),
        content_padding=ft.padding.only(left=5, top=2, bottom=2, right=5),
        on_change=on_search_change,
        expand=True
    )
        
    search_bar = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.SEARCH, color="#A19A8F", size=20),
            search_field
        ]),
        bgcolor="#FAFAFA", # Quasi bianco per il campo di ricerca
        border=ft.border.all(1, "#EAE1D8"),
        border_radius=12,
        padding=ft.padding.symmetric(horizontal=12, vertical=0),
    )

    # 4. Chips orizzontali
    def update_chips():
        for chip in chips_row.controls:
            label = chip.data
            is_selected = (label == state["filter"])
            chip.bgcolor = "#A9937E" if is_selected else bg_card
            chip.content.color = "#FFFFFF" if is_selected else text_color
        page.update()

    def on_chip_click(e):
        state["filter"] = e.control.data
        update_chips()
        update_list()

    def create_chip(label, is_selected=False):
        return ft.Container(
            content=ft.Text(label, size=13, weight=ft.FontWeight.W_600, color="#FFFFFF" if is_selected else text_color),
            bgcolor="#A9937E" if is_selected else bg_card,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border_radius=20,
            on_click=on_chip_click,
            data=label
        )

    chips_row = ft.Row(
        controls=[
            create_chip("Confermati", True),
            create_chip("Bozze", False),
        ],
        scroll=ft.ScrollMode.HIDDEN,
        spacing=8,
    )

    # 5. Lista Progetti (Database Data)
    preventivi_data = get_preventivi()
    
    list_view = ft.ListView(
        expand=True, 
        spacing=0, 
        padding=0,
        auto_scroll=False,
    )

    def update_list():
        list_view.controls.clear()
        filtered_data = []
        
        for row in preventivi_data:
            nome_cliente = row.get("nome_cliente") or "Sconosciuto"
            status = row.get("status") or "N/A"
            status_upper = status.upper()
            
            # Filtro per Status (Tab)
            # FATTURATO potrebbe venire dal database come stato a sé stante.
            if state["filter"] == "Confermati" and status_upper != "CONFERMATO":
                continue
            if state["filter"] == "Bozze" and status_upper != "BOZZA":
                continue
                
            # Filtro di Ricerca (Search bar)
            if state["search"]:
                q = state["search"]
                # cerca nel nome cliente o nell'ID
                if q not in nome_cliente.lower() and q not in str(row.get('id', '')):
                    continue
                    
            filtered_data.append(row)

        if not filtered_data:
            list_view.controls.append(
                ft.Container(
                    content=ft.Text("Nessun progetto trovato.", color=text_color),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )
        else:
            for row in filtered_data:
                # Formattazione Dati
                nome_cliente = row.get("nome_cliente") or "Sconosciuto"
                status = row.get("status") or "N/A"
                totale = row.get("totale_generale") or 0.0
                id_proj = row.get('id', '?')
                data_creazione = format_date_it(row.get("data_creazione"))
                
                # Badge logic RATIO
                status_upper = status.upper()
                if status_upper == "CONFERMATO":
                    status_text = "Confermato"
                    status_bg = "#80B98A" # Verde RATIO
                elif status_upper == "BOZZA":
                    status_text = "Bozza"
                    status_bg = "#EBA661" # Arancio/Giallo RATIO
                else:
                    status_text = "Completato"
                    status_bg = "#8A837C" # Grigio RATIO
                
                card = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(f"{nome_cliente} (Progetto {id_proj})", weight=ft.FontWeight.W_600, color=text_color, size=15),
                                    ft.Container(
                                        content=ft.Text(status_text, size=10, weight=ft.FontWeight.W_600, color="#FFFFFF"),
                                        bgcolor=status_bg,
                                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                        border_radius=12,
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Container(height=2),
                            ft.Row(
                                controls=[
                                    ft.Column([
                                        ft.Text(f"Creato il {data_creazione}", size=11, color="#A19A8F"),
                                        ft.Text(f"Totale {format_eur(totale)}", size=13, color=text_color),
                                    ], spacing=2),
                                    ft.Icon(ft.icons.CHEVRON_RIGHT, color="#C7C0B8", size=20)
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            )
                        ],
                        spacing=0,
                    ),
                    padding=ft.padding.symmetric(vertical=15, horizontal=0),
                    border=ft.border.only(bottom=ft.BorderSide(1, "#EAE1D8")),
                    on_click=lambda e, pid=id_proj: page.navigate_to_dettaglio(pid)
                )
                list_view.controls.append(card)
        page.update()

    # Initial render
    update_list()

    return ft.Container(
        padding=ft.padding.only(left=20, right=20, top=20),
        content=ft.Column(
            controls=[
                header,
                ft.Container(height=10),
                ft.Row([title_row, ft.Container()], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), # Header wrapper per tenere l'icona a dx in futuro
                ft.Container(height=15),
                search_bar,
                ft.Container(height=15),
                chips_row,
                ft.Container(height=10),
                list_view
            ],
            expand=True,
            spacing=0,
        )
    )
