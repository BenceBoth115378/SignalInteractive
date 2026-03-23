import flet as ft


def build_module_menu(module_cards: list[dict], on_select: callable) -> ft.Control:
    cards: list[ft.Control] = []

    for module in module_cards:
        module_id = module["id"]
        cards.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(module.get("title", module_id), size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(module.get("subtitle", ""), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Divider(height=10),
                        ft.Text(module.get("description", ""), size=13),
                        ft.Row(
                            controls=[
                                ft.Button(
                                    "Open",
                                    on_click=lambda e, mid=module_id: on_select(mid),
                                )
                            ],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ],
                    spacing=8,
                ),
                width=380,
                padding=16,
                border=ft.Border.all(1, ft.Colors.OUTLINE),
                border_radius=12,
            )
        )

    return ft.Column(
        controls=[
            ft.Text("Signal Protocol Models", size=34, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Choose a simulator module to explore.",
                size=14,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.ResponsiveRow(
                controls=[
                    ft.Container(content=card, col={"sm": 12, "md": 6, "lg": 6})
                    for card in cards
                ],
                run_spacing=12,
                spacing=12,
            ),
        ],
        spacing=14,
        expand=True,
    )
