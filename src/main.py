import flet as ft
from components.data_classes import AppState
from components.router import Router
from components.startup_prompt import build_startup_prompt
from components.persistence import clear_state, has_saved_state, load_state, save_state
from components.session_payload import apply_payload, serialize_payload


def main(page: ft.Page):
    page.title = "Signal Protocol"
    page.scroll = "auto"

    if hasattr(page, "window") and page.window is not None:
        page.window.width = 1600
        page.window.height = 980
        page.window.min_width = 1400
        page.window.min_height = 900
    else:
        if hasattr(page, "window_width"):
            page.window_width = 1600
        if hasattr(page, "window_height"):
            page.window_height = 980

    app_state = AppState()
    router = Router()
    saved_state_exists = has_saved_state()
    autosave_enabled = not saved_state_exists
    waiting_for_startup_choice = saved_state_exists

    main_container = ft.Column(expand=True)

    def _persist_runtime_state() -> None:
        if not autosave_enabled:
            return

        save_state(serialize_payload(app_state, router))

    def _reset_application_state() -> None:
        nonlocal app_state, router
        nonlocal autosave_enabled, waiting_for_startup_choice

        clear_state()
        app_state = AppState()
        router = Router()
        autosave_enabled = True
        waiting_for_startup_choice = False

    def refresh():
        nonlocal waiting_for_startup_choice

        main_container.controls.clear()

        if waiting_for_startup_choice:
            startup_prompt = build_startup_prompt(
                on_start_new=_start_new,
                on_load_saved=_load_saved,
            )
            main_container.controls.append(startup_prompt)
            page.update()
            return

        module = router.get_current_module(app_state)

        def _on_perspective_change(e):
            app_state.perspective = e.control.value
            refresh()

        perspective_selector = ft.RadioGroup(
            value=app_state.perspective,
            content=ft.Row(
                controls=[
                    ft.Radio(value="global", label="Global"),
                    ft.Radio(value="alice", label="Alice"),
                    ft.Radio(value="bob", label="Bob"),
                    ft.Radio(value="attacker", label="Attacker"),
                ],
                spacing=10,
            ),
            on_change=_on_perspective_change,
        )

        content = module.build(
            page,
            app_state,
            perspective_selector=perspective_selector,
        )
        main_container.controls.append(content)

        page.update()
        _persist_runtime_state()

    def _start_new(e):
        _reset_application_state()

        refresh()

    def _load_saved(e):
        nonlocal autosave_enabled, waiting_for_startup_choice

        saved_state = load_state()
        if saved_state is None:
            autosave_enabled = True
            waiting_for_startup_choice = False
            refresh()
            return

        apply_payload(app_state, router, saved_state)
        autosave_enabled = True
        waiting_for_startup_choice = False

        refresh()

    page.add(main_container)
    refresh()


ft.run(main)
