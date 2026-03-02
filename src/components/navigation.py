import flet as ft


def build_navigation(
    page,
    app_state,
    router,
    refresh_callback,
    save_as_callback=None,
    load_file_callback=None,
):

    def next_clicked(e):
        module = router.get_current_module(app_state)
        module.next_step(app_state)
        refresh_callback()

    def back_clicked(e):
        module = router.get_current_module(app_state)
        module.prev_step(app_state)
        refresh_callback()

    def perspective_changed(e):
        app_state.perspective = e.control.value
        refresh_callback()

    perspective_selector = ft.RadioGroup(
        value=app_state.perspective,
        content=ft.Row([
            ft.Radio(value="global", label="Global"),
            ft.Radio(value="alice", label="Alice"),
            ft.Radio(value="bob", label="Bob"),
            ft.Radio(value="attacker", label="Attacker"),
        ]),
        on_change=perspective_changed
    )

    navigation_buttons = ft.Row(
        [
            ft.Button("Back", on_click=back_clicked),
            ft.Button("Next", on_click=next_clicked),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
    )

    return ft.Column([
        ft.Divider(),
        perspective_selector,
        navigation_buttons
    ])
