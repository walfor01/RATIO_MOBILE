import flet as ft
from database import get_all_scadenze, format_date_it, parse_date
import datetime
from collections import defaultdict

def GanttView(page: ft.Page):
    """Componente per la vista Gantt - Raggruppamento per Ordine (Mobile-friendly)."""
    text_color = "#3D3935"
    bg_card = "#EAE1D8"
    
    raw_data = get_all_scadenze()
    
    mesi_it_short = {
        1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
        7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
    }
    
    current_year = datetime.date.today().year
    stats_per_month = defaultdict(int)
    
    # Raggruppiamo i dati per Ordine (preventivo_id)
    projects = {}
    for r in raw_data:
        pid = r.get("preventivo_id")
        cliente = r.get("nome_cliente") or "Sconosciuto"
        
        if pid not in projects:
            projects[pid] = {
                "id": pid,
                "cliente": cliente,
                "items": []
            }
            
        # Determiniamo data consegna e montaggio formattate
        dt_cons = "N/A"
        if r.get("data_consegna"):
            parsed = format_date_it(r.get("data_consegna"))
            if parsed != "Data non valida":
                dt_cons = parsed
            dt_obj = parse_date(r.get("data_consegna"))
            if dt_obj and dt_obj.year == current_year:
                stats_per_month[dt_obj.month] += 1

        dt_inst = "N/A"
        if r.get("data_installazione"):
            parsed = format_date_it(r.get("data_installazione"))
            if parsed != "Data non valida":
                dt_inst = parsed
            dt_obj = parse_date(r.get("data_installazione"))
            if dt_obj and dt_obj.year == current_year:
                stats_per_month[dt_obj.month] += 1
        
        articolo = r.get("descrizione") or r.get("ambiente") or "Articolo"
        
        projects[pid]["items"].append({
            "articolo": articolo,
            "consegna": dt_cons,
            "montaggio": dt_inst,
            "fornitore": r.get("fornitore") or "Nessun Fornitore"
        })
        
    # Ordiniamo i progetti per ID decrescente
    sorted_projects = sorted(projects.values(), key=lambda x: str(x["id"]), reverse=True)
    
    list_view = ft.ListView(expand=True, spacing=15, padding=0, auto_scroll=False)
    
    for proj in sorted_projects:
        # Generiamo le righe interne degli articoli
        internal_rows = []
        for idx, item in enumerate(proj["items"]):
            internal_rows.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"{item['articolo']}", size=13, weight=ft.FontWeight.W_600, color=text_color),
                        ft.Row([
                            ft.Text(f"Fornitore: {item['fornitore'][:20]}", size=11, color="#8F8A84")
                        ]),
                        ft.Container(height=4),
                        ft.Row([
                            # Badge Consegna
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.LOCAL_SHIPPING_OUTLINED, size=14, color="#A9937E"), 
                                    ft.Text(f" {item['consegna']}", size=12, color=text_color, weight=ft.FontWeight.BOLD)
                                ], spacing=2),
                                bgcolor="#F0EBE1", padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=6
                            ),
                            # Badge Montaggio
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.BUILD_OUTLINED, size=14, color="#A9937E"), 
                                    ft.Text(f" {item['montaggio']}", size=12, color=text_color, weight=ft.FontWeight.BOLD)
                                ], spacing=2),
                                bgcolor="#E4DFD5", padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=6
                            )
                        ], spacing=10)
                    ]),
                    padding=ft.padding.only(left=15, right=15, bottom=10, top=10)
                )
            )
            # Aggiungiamo un separatore tranne che all'ultimo elemento
            if idx < len(proj["items"]) - 1:
                internal_rows.append(ft.Divider(height=1, color="#E8E2D9"))
            
        tile = ft.ExpansionTile(
            title=ft.Text(f"Ordine #{proj['id']} - {proj['cliente']}", size=14, weight=ft.FontWeight.BOLD, color=text_color),
            subtitle=ft.Text(f"{len(proj['items'])} Scadenze programmate", size=11, color="#A19A8F"),
            collapsed_bgcolor="#FFFFFF",
            bgcolor="#FAF8F5",
            collapsed_text_color=text_color,
            text_color=text_color,
            controls=internal_rows,
            initially_expanded=False,
            shape=ft.RoundedRectangleBorder(radius=8),
            collapsed_shape=ft.RoundedRectangleBorder(radius=8)
        )
        
        # Inseriamo il tile in una card/container per dare bordi visibili
        list_view.controls.append(ft.Container(
            content=tile,
            border=ft.border.all(1, "#E8E2D9"),
            border_radius=8,
            clip_behavior=ft.ClipBehavior.HARD_EDGE, # Taglia bordi arrotondati se tile sfonda
            bgcolor="#FFFFFF"
        ))

    if not list_view.controls:
        list_view.controls.append(ft.Container(content=ft.Text("Nessun ordine con date.", color=text_color), padding=20, alignment=ft.alignment.center))


    # Costruzione del grafico a barre
    chart_groups = []
    max_val = max(stats_per_month.values()) if stats_per_month else 1
    
    for i in range(1, 13):
        val = stats_per_month.get(i, 0)
        chart_groups.append(
            ft.BarChartGroup(
                x=i-1,
                bar_rods=[
                    ft.BarChartRod(
                        from_y=0,
                        to_y=val,
                        width=12,
                        color="#C25925" if val > 0 else "#EAE1D8",
                        tooltip=f"{mesi_it_short[i]}: {val} task",
                        border_radius=4,
                    )
                ]
            )
        )

    chart = ft.BarChart(
        bar_groups=chart_groups,
        border=ft.border.all(0, ft.colors.TRANSPARENT),
        left_axis=ft.ChartAxis(
            labels_size=20,
            title=ft.Text("QTA", size=9, color="#8F8A84"),
            labels_interval=max(1, max_val // 4)
        ),
        bottom_axis=ft.ChartAxis(
            labels=[
                ft.ChartAxisLabel(value=i-1, label=ft.Text(mesi_it_short[i], size=9, color="#6C665F"))
                for i in range(1, 13)
            ],
            labels_size=20,
        ),
        horizontal_grid_lines=ft.ChartGridLines(
            color="#EAE1D8", width=1, dash_pattern=[3, 3]
        ),
        tooltip_bgcolor="#FAF8F5",
        max_y=max_val + (max_val * 0.2), # margine del 20% in alto
        interactive=True,
    )
    
    chart_container = ft.Container(
        content=ft.Column([
            ft.Text(f"Carico di Lavoro ({current_year})", size=14, weight=ft.FontWeight.BOLD, color=text_color),
            ft.Container(content=chart, height=140)
        ]),
        bgcolor="#FFFFFF",
        padding=15,
        border_radius=12,
        border=ft.border.all(1, "#E8E2D9"),
        margin=ft.padding.only(bottom=15)
    )

    header = ft.Row([
        ft.Text("Gantt & Ordini", size=22, weight=ft.FontWeight.W_600, color=text_color)
    ])

    return ft.Container(
        content=ft.Column(
            controls=[
                header,
                ft.Text("Date operative raggruppate per progetto", size=12, color="#8F8A84"),
                ft.Container(height=10),
                chart_container,
                list_view
            ],
            spacing=0
        ),
        expand=True,
        padding=20,
        bgcolor="#FAF8F5"
    )
