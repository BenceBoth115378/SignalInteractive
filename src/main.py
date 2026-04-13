import os

import flet as ft

from components.data_classes import AppState
from components.module_menu import build_module_menu
from components.persistence import ModuleStatePersistence, WEB_UPLOAD_DIR
from components.router import Router


def main(page: ft.Page):
    page.title = "Signal Interactive"
    page.scroll = "auto"

    if hasattr(page, "window") and page.window is not None:
        page.window.width = 1600
        page.window.height = 1050
        page.window.min_width = 1400
        page.window.min_height = 900
    else:
        if hasattr(page, "window_width"):
            page.window_width = 1600
        if hasattr(page, "window_height"):
            page.window_height = 1050

    app_state = AppState()
    router = Router()
    status_text = ft.Text("", size=12, color=ft.Colors.BLUE)
    persistence: ModuleStatePersistence | None = None

    main_container = ft.Column(expand=True)

    def _set_status(message: str, is_error: bool = False) -> None:
        status_text.value = message
        status_text.color = ft.Colors.RED if is_error else ft.Colors.BLUE

    def _state_controls() -> ft.Row:
        if persistence is None:
            return ft.Row(controls=[], spacing=6)
        return persistence.build_controls()

    def refresh():
        main_container.controls.clear()

        if not app_state.current_module:
            main_container.controls.append(
                ft.Row(
                    controls=[
                        ft.Text("Signal Protocol Models", size=20, weight=ft.FontWeight.BOLD),
                        _state_controls(),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )
            if status_text.value:
                main_container.controls.append(status_text)
            main_container.controls.append(
                build_module_menu(router.get_module_cards(), on_select=_select_module)
            )
            page.update()
            return

        module = router.get_current_module(app_state)

        back_to_menu = ft.TextButton("Main menu", on_click=_back_to_menu)

        content = module.build(
            page,
            app_state,
        )
        main_container.controls.append(
            ft.Row(
                controls=[back_to_menu, _state_controls()],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        if status_text.value:
            main_container.controls.append(status_text)
        main_container.controls.append(ft.Divider(height=1))
        main_container.controls.append(content)

        page.update()

    def _back_to_menu(e):
        app_state.current_module = ""
        refresh()

    def _select_module(module_id: str) -> None:
        app_state.current_module = module_id
        app_state.perspective = "global"
        refresh()

    persistence = ModuleStatePersistence(page, app_state, router, refresh, _set_status)
    page.add(main_container)
    refresh()


WEB_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("FLET_SECRET_KEY", "signal-interactive-module-state-upload")
ft.run(main, upload_dir=str(WEB_UPLOAD_DIR))
