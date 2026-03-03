import flet as ft
import os
from views.dashboard import DashboardView
from views.preventivi import PreventiviView
from views.dettaglio_progetto import DettaglioProgettoView
from views.scadenze import ScadenzeView
from views.gantt import GanttView

def main(page: ft.Page):
    # Configurazione della pagina per simulare un dispositivo Mobile
    page.title = "RATIO Gestionale"
    page.window_width = 390
    page.window_height = 844
    page.window_resizable = False
    
    # Colori Tema principale basati sul mockup (Crema / Beige chiaro)
    page.bgcolor = "#FAF8F5"
    page.padding = 0
    
    page.theme = ft.Theme(
        color_scheme_seed="#3D3935",
        visual_density=ft.ThemeVisualDensity.COMFORTABLE,
        font_family="Inter", # O il font di default sans-serif
    )

    # Il design non ha una AppBar standard di Flet ma un header custom in ogni pagina
    page.appbar = None

    # Container principale del corpo della pagina (usa SafeArea)
    body_container = ft.SafeArea(
        expand=True,
        content=ft.Container(
            expand=True,
            content=DashboardView(page) # Vista di default
        )
    )
    
    page.add(body_container)

    # Gestione navigazione
    def change_tab(e=None, index=None):
        selected_index = index if index is not None else e.control.selected_index
        if selected_index == 0:
            body_container.content.content = DashboardView(page)
        elif selected_index == 1:
            body_container.content.content = PreventiviView(page)
        elif selected_index == 2:
            body_container.content.content = GanttView(page)
        elif selected_index == 3:
            body_container.content.content = ScadenzeView(page)
        else:
            body_container.content.content = ft.Container(
                content=ft.Text("In Sviluppo...", color="#3D3935"), 
                alignment=ft.alignment.center
            )
        page.update()

    def go_back_to_previous():
        # Ripristina la view basata sull'ultimo tab attivo
        change_tab(index=page.navigation_bar.selected_index)

    def navigate_to_dettaglio(pid):
        # Sostituisce la vista corrente con il Dettaglio
        body_container.content.content = DettaglioProgettoView(page, pid, go_back_to_previous)
        page.update()

    # Esportiamo la funzione sulla page per richiamarla dai vari componenti
    page.navigate_to_dettaglio = navigate_to_dettaglio

    # Navigazione inferiore (stile iOS/Material) - Icone aggiornate
    page.navigation_bar = ft.NavigationBar(
        bgcolor="#FAF8F5",
        indicator_color="#E8E2D9",
        destinations=[
            ft.NavigationDestination(icon=ft.icons.HOME_OUTLINED, selected_icon=ft.icons.HOME, label="Home"),
            ft.NavigationDestination(icon=ft.icons.FOLDER_OUTLINED, selected_icon=ft.icons.FOLDER, label="Progetti"),
            ft.NavigationDestination(icon=ft.icons.BAR_CHART_OUTLINED, selected_icon=ft.icons.BAR_CHART, label="Gantt"),
            ft.NavigationDestination(icon=ft.icons.CALENDAR_TODAY_OUTLINED, selected_icon=ft.icons.CALENDAR_MONTH, label="Scadenze"),
        ],
        on_change=change_tab,
        selected_index=0,
    )

    page.update()

if __name__ == "__main__":
    porta_web = int(os.getenv("PORT", 8550))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=porta_web, assets_dir="assets", web_renderer="html")
