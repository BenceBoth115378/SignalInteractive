import flet as ft


def build_startup_prompt(on_start_new, on_load_saved):
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    "Resume previous session?",
                    size=20,
                    weight="bold",
                ),
                ft.Text(
                    "A saved simulator state was found. "
                    "Load it or start from zero."
                ),
                ft.Row(
                    [
                        ft.Button("Start new", on_click=on_start_new),
                        ft.Button("Load saved", on_click=on_load_saved),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=10,
        ),
        padding=16,
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        border_radius=8,
        margin=ft.Margin.only(bottom=12),
    )
