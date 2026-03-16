import flet as ft
from database import get_dashboard_stats, get_preventivi, get_upcoming_scadenze, parse_date, get_redditivita_stats
import datetime

def DashboardView(page: ft.Page):
    """Componente per la vista della Dashboard - Stile RATIO."""
    
    text_color = "#3D3935"
    bg_card = "#EAE1D8"
    
    # Preleva i dat dal DB
    stats = get_dashboard_stats()
    preventivi_data = get_preventivi()
    
    # 6. Dialogo Redditività (Grafico a Torta)
    redditivita_data = get_redditivita_stats()
    
    # Colori per le fette di torta (Palette fissa RATIO-like e variazioni)
    palette = ["#3B8FEA", "#65B951", "#EBA661", "#C25925", "#80B98A", "#A9937E", "#8A837C"]
    
    chart_view_mode = "utile_netto" # Può essere "utile_netto" o "fatturato_no_iva"
    
    def generate_pie_chart():
        if not redditivita_data:
            return ft.Text("Nessun dato fatturato disponibile per le metriche.", color=text_color, text_align=ft.TextAlign.CENTER)
            
        totale_globale = sum(float(r[chart_view_mode] or 0) for r in redditivita_data)
        if totale_globale == 0:
            return ft.Text("Valori aggregati a zero.", color=text_color, text_align=ft.TextAlign.CENTER)

        sections = []
        legen_items = []
        for i, row in enumerate(redditivita_data):
            valore = float(row[chart_view_mode] or 0)
            if valore <= 0: continue
            
            percent = (valore / totale_globale) * 100
            col = palette[i % len(palette)]
            
            sections.append(
                ft.PieChartSection(
                    valore,
                    color=col,
                    radius=50,
                    title=f"{percent:.1f}%",
                    title_style=ft.TextStyle(size=10, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
                    badge=ft.Container(
                        content=ft.Text(row['categoria'][:10], size=8, color=text_color),
                        bgcolor="#FFFFFF", padding=ft.padding.all(2), border=ft.border.all(0.5, "#EAE1D8"), border_radius=4
                    ),
                    badge_position=1.1
                )
            )
            legen_items.append(
                ft.Row([
                    ft.Container(width=10, height=10, bgcolor=col, border_radius=2),
                    ft.Text(f"{row['categoria']}: € {valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=10, color=text_color)
                ], spacing=4)
            )
            
        chart = ft.PieChart(
            sections=sections,
            sections_space=1,
            center_space_radius=30,
            expand=True
        )
        
        return ft.Column([
            ft.Text(f"Totale {chart_view_mode.replace('_', ' ').title()}: € {totale_globale:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=14, weight=ft.FontWeight.BOLD, color=text_color),
            ft.Container(content=chart, height=220, alignment=ft.alignment.center),
            ft.Container(height=10),
            ft.Text("Dettaglio Categorie:", size=11, weight=ft.FontWeight.W_600, color="#8F8A84"),
            ft.Column(legen_items, spacing=2, scroll=ft.ScrollMode.ADAPTIVE, height=80)
        ], spacing=0)

    chart_dialog_content = ft.Container()
    
    def on_segment_change(e):
        nonlocal chart_view_mode
        chart_view_mode = list(e.control.selected)[0] if e.control.selected else "utile_netto"
        chart_dialog_content.content = generate_pie_chart()
        page.update()

    segmented_btn = ft.SegmentedButton(
        selected={"utile_netto"},
        allow_empty_selection=False,
        on_change=on_segment_change,
        segments=[
            ft.Segment(value="utile_netto", label=ft.Text("Utile", size=11)),
            ft.Segment(value="fatturato_no_iva", label=ft.Text("Fatturato", size=11)),
        ],
        selected_icon=ft.Icon(ft.icons.CHECK, size=14)
    )
    
    chart_dialog_content.content = generate_pie_chart()

    def open_redditivita_dialog():
        dlg = ft.AlertDialog(
            title=ft.Text("Statistiche Redditività", size=16, weight=ft.FontWeight.BOLD, color=text_color),
            content=ft.Container(
                content=ft.Column([
                    ft.Container(content=segmented_btn, alignment=ft.alignment.center, padding=ft.padding.only(bottom=15)),
                    chart_dialog_content
                ], spacing=0, tight=True, width=300),
                height=420
            ),
            bgcolor="#FAF8F5",
            actions=[ft.TextButton("Chiudi", on_click=lambda e: chiudi_dialog(dlg))]
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def chiudi_dialog(d):
        d.open = False
        page.update()
    
    # 1. Header Row
    header = ft.Row([
        ft.Image(src="logo_ratio.png", height=45, fit=ft.ImageFit.CONTAIN)
    ], alignment=ft.MainAxisAlignment.CENTER)
    
    # 3. Alert Scadenze Critiche (COLLEGATO AL DB - RIGHE)
    oggi = datetime.date.today()
    domani = oggi + datetime.timedelta(days=1)
    
    scadenze_oggi = 0
    scadenze_domani = 0
    scadenze_oggi_list = []
    scadenze_domani_list = []
    
    # Contatori per le card statistiche in basso
    totale_scadenze_future = 0
    scadenze_in_ritardo = 0
    consegne_imminenti = 0
    
    scadenze_righe = get_upcoming_scadenze()
    if scadenze_righe:
        for r in scadenze_righe:
            for col in ["data_consegna", "data_installazione"]:
                dt_str = r.get(col)
                if dt_str:
                    dt = parse_date(dt_str)
                    if dt:
                        # Scadenze critiche alert superiore
                        if dt == oggi:
                            scadenze_oggi += 1
                            nome = r.get("ambiente") or r.get("descrizione") or "Articolo"
                            cliente = r.get("nome_cliente") or "Cliente"
                            tipo = "Consegna" if col == "data_consegna" else "Montaggio"
                            scadenze_oggi_list.append({"text": f"{cliente} - {nome} ({tipo})", "id": r.get("preventivo_id")})
                        elif dt == domani:
                            scadenze_domani += 1
                            nome = r.get("ambiente") or r.get("descrizione") or "Articolo"
                            cliente = r.get("nome_cliente") or "Cliente"
                            tipo = "Consegna" if col == "data_consegna" else "Montaggio"
                            scadenze_domani_list.append({"text": f"{cliente} - {nome} ({tipo})", "id": r.get("preventivo_id")})
                            
                        # Scadenze statistiche inferiori
                        if dt >= oggi:
                            totale_scadenze_future += 1
                        if dt < oggi:
                            scadenze_in_ritardo += 1
                        if oggi <= dt <= oggi + datetime.timedelta(days=7):
                            consegne_imminenti += 1

    # Generiamo il testo dinamico multi-riga
    alert_content = [
        ft.Text("Scadenze Critiche", size=14, weight=ft.FontWeight.BOLD, color=text_color),
    ]
    
    if scadenze_oggi == 0 and scadenze_domani == 0:
        alert_content.append(ft.Text("(Nessuna a breve)", size=12, color=text_color))
    else:
        if scadenze_oggi > 0:
            alert_content.append(ft.Text(f"{scadenze_oggi} Oggi:", size=12, weight=ft.FontWeight.BOLD, color=text_color))
            for item in scadenze_oggi_list:
                alert_content.append(
                    ft.Container(
                        content=ft.Text(f"• {item['text']}", size=12, color=text_color, style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE)),
                        on_click=lambda e, pid=item['id']: page.navigate_to_dettaglio(pid),
                        padding=ft.padding.only(left=5, bottom=2)
                    )
                )
        if scadenze_domani > 0:
            alert_content.append(ft.Text(f"{scadenze_domani} Domani:", size=12, weight=ft.FontWeight.BOLD, color=text_color))
            for item in scadenze_domani_list:
                alert_content.append(
                    ft.Container(
                        content=ft.Text(f"• {item['text']}", size=12, color=text_color, style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE)),
                        on_click=lambda e, pid=item['id']: page.navigate_to_dettaglio(pid),
                        padding=ft.padding.only(left=5, bottom=2)
                    )
                )

    alert_box = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color="#C25925", size=24),
            ft.Column(alert_content, spacing=2)
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START),
        bgcolor="#F6DCD0",
        padding=15,
        border_radius=12,
        border=ft.border.all(1, "#EBBF9B")
    )
    
    # 4. Statistiche Split View
    stats_row = ft.Row(
        controls=[
            # Bottone/Preview Redditività (Sostituisce Riassunto Settimana)
            ft.Container(
                height=175,
                content=ft.Column([
                    ft.Text("Redditività", size=13, weight=ft.FontWeight.W_600, color=text_color),
                    ft.Container(height=5),
                    ft.Icon(ft.icons.PIE_CHART_ROUNDED, size=50, color="#C25925"),
                    ft.Container(height=5),
                    ft.Text("Mappa Utile / Fatturato", size=11, color=text_color, weight=ft.FontWeight.BOLD),
                    ft.Text("Tocca per espandere", size=10, color="#8F8A84")
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=bg_card,
                padding=12,
                border_radius=16,
                expand=True,
                ink=True,
                on_click=lambda e: open_redditivita_dialog()
            ),
            # Spazio fittizio o margine tra le due schede
            ft.Container(width=10),
            # Statistiche Rapide
            ft.Container(
                height=175,
                content=ft.Column([
                    ft.Text("Statistiche Rapide", size=13, weight=ft.FontWeight.W_600, color=text_color),
                    ft.Container(height=5),
                    ft.Row([
                        ft.Container(width=4, height=35, bgcolor="#C25925", border_radius=4),
                        ft.Column([
                            ft.Text(f"{scadenze_in_ritardo}", size=20, weight=ft.FontWeight.BOLD, color=text_color, height=22),
                            ft.Text("Date In Ritardo", size=11, color=text_color)
                        ], spacing=0)
                    ]),
                    ft.Container(height=5),
                    ft.Row([
                        ft.Container(width=4, height=35, bgcolor="#D08852", border_radius=4),
                        ft.Column([
                            ft.Text(f"{consegne_imminenti}", size=20, weight=ft.FontWeight.BOLD, color=text_color, height=22),
                            ft.Text("Imminenti (7gg)", size=11, color=text_color)
                        ], spacing=0)
                    ]),
                ]),
                bgcolor=bg_card,
                padding=12,
                border_radius=16,
                expand=True,
            ),
        ],
        spacing=0,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
    )

    # 5. Lista Progetti Recenti (Reali dal DB, max 3) - ORA CON CORNICETTA INTERA
    def recent_project_item(name, client, status_text, status_color, total, id_proj):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(name, weight=ft.FontWeight.W_600, color=text_color, size=15),
                    ft.Container(
                        content=ft.Text(status_text, size=10, weight=ft.FontWeight.W_600, color="#FFFFFF"),
                        bgcolor=status_color,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=12,
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text(f"Cliente {client}", color=text_color, size=13),
                    ft.Text(f"Total €{total}", color=text_color, size=13, weight=ft.FontWeight.W_500),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]),
            padding=15,
            border=ft.border.all(1, "#EAE1D8"),
            border_radius=12,
            margin=ft.padding.only(bottom=10),
            bgcolor=page.bgcolor, # Stesso colore di sfondo della pagina per la cornicetta vuota
            on_click=lambda e: page.navigate_to_dettaglio(id_proj) # AZIONE DI NAVIGAZIONE
        )
        
    recent_projects_controls = [
        ft.Text("Ultimi Progetti Attivi", size=18, weight=ft.FontWeight.BOLD, color=text_color),
        ft.Container(height=5),
    ]
    
    if preventivi_data:
        # Filtriamo per escludere le Bozze, mostrando solo i progetti reali
        progetti_attivi = [r for r in preventivi_data if str(r.get("status", "")).upper() in ("CONFERMATO", "FATTURATO")]
        
        # Prende solo gli ultimi 3 per la home
        if not progetti_attivi:
            recent_projects_controls.append(ft.Text("Nessun progetto attivo trovato.", color=text_color))
        for row in progetti_attivi[:3]:
            nome_cliente = row.get("nome_cliente") or "Sconosciuto"
            status = row.get("status") or "N/A"
            totale = row.get("totale_generale") or 0.0
            id_proj = row.get('id', '?')
            
            # Formatta totali ed eventuale logica
            totale_str = f"{totale:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            # Logica colori identica
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
                
            recent_projects_controls.append(
                recent_project_item(f"Progetto {id_proj}", nome_cliente, status_text, status_bg, totale_str, id_proj)
            )
    else:
        recent_projects_controls.append(ft.Text("Nessun progetto trovato.", color=text_color))

    recent_projects_section = ft.Column(recent_projects_controls, spacing=0)

    return ft.Container(
        padding=20,
        content=ft.Column(
            controls=[
                header,
                ft.Container(height=15),
                alert_box,
                ft.Container(height=20),
                stats_row,
                ft.Container(height=25),
                recent_projects_section,
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        )
    )
