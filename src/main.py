import flet as ft
from components.data_classes import AppState
from components.router import Router
from components.navigation import build_navigation
from components.startup_prompt import build_startup_prompt
from components.persistence import clear_state, has_saved_state, load_state, save_state
from components.session_payload import apply_payload, serialize_payload


def main(page: ft.Page):
    page.title = "Signal Protocol"
    page.window_width = 1100
    page.window_height = 850
    page.scroll = "auto"

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
        content = module.build(page, app_state)

        navigation = build_navigation(
            page, app_state, router, refresh
        )

        main_container.controls.append(content)
        main_container.controls.append(navigation)

        page.update()
        _persist_runtime_state()

    def _start_new(e):
        nonlocal app_state, router
        nonlocal autosave_enabled, waiting_for_startup_choice

        clear_state()
        app_state = AppState()
        router = Router()
        autosave_enabled = True
        waiting_for_startup_choice = False

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
