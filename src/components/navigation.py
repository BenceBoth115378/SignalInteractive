import flet as ft


def build_navigation(
    page,
    app_state,
    router,
    refresh_callback,
    save_as_callback=None,
    load_file_callback=None,
):

    def send_alice_to_bob(e):
        module = router.get_current_module(app_state)
        if hasattr(module, "send_message"):
            module.send_message(app_state, sender="alice")
            refresh_callback()

    def send_bob_to_alice(e):
        module = router.get_current_module(app_state)
        if hasattr(module, "send_message"):
            module.send_message(app_state, sender="bob")
            refresh_callback()

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
