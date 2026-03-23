import flet as ft
from components.data_classes import AppState
from components.module_menu import build_module_menu
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

    main_container = ft.Column(expand=True)

    def refresh():
        main_container.controls.clear()

        if not app_state.current_module:
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
                controls=[back_to_menu],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
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

    page.add(main_container)
    refresh()


ft.run(main)
