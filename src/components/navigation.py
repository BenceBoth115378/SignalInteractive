import flet as ft

from components.data_classes import AppState


def build_navigation(page: ft.Page, app_state: AppState, router: any, refresh_callback: callable) -> ft.Column:

    def perspective_changed(e):
        app_state.perspective = e.control.value
        refresh_callback()

    perspective_selector = ft.RadioGroup(
        value=app_state.perspective,
        content=ft.Row(
            [
                ft.Radio(value="global", label="Global"),
                ft.Radio(value="alice", label="Alice"),
                ft.Radio(value="bob", label="Bob"),
                ft.Radio(value="attacker", label="Attacker"),
            ]
        ),
        on_change=perspective_changed,
    )

    return ft.Column(
        [
            ft.Divider(),
            perspective_selector,
        ]
    )
