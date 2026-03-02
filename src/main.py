import flet as ft
from state import AppState
from router import Router
from components.navigation import build_navigation
from persistence import clear_state, has_saved_state, load_state, save_state


PERSPECTIVES = {"global", "alice", "bob", "attacker"}


def main(page: ft.Page):
    page.title = "Signal Protocol"
    page.window_width = 1100
    page.window_height = 750
    page.scroll = "auto"

    app_state = AppState()
    router = Router()
    saved_state_exists = has_saved_state()
    autosave_enabled = not saved_state_exists
    
    

    main_container = ft.Column(expand=True)

    def _serialize_app_state() -> dict:
        return {
            "current_module": app_state.current_module,
            "current_step": app_state.current_step,
            "perspective": app_state.perspective,
        }

    def _apply_app_state(data: dict) -> None:
        app_state.current_module = data.get(
            "current_module", app_state.current_module
        )

        current_step = data.get("current_step", app_state.current_step)
        if isinstance(current_step, int) and current_step >= 0:
            app_state.current_step = current_step

        perspective = data.get("perspective", app_state.perspective)
        if perspective in PERSPECTIVES:
            app_state.perspective = perspective

    def _persist_runtime_state() -> None:
        if not autosave_enabled:
            return

        save_state(
            {
                "app_state": _serialize_app_state(),
                "modules": router.export_state(),
            }
        )

    def refresh():
        main_container.controls.clear()

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
        nonlocal app_state, router, autosave_enabled

        clear_state()
        app_state = AppState()
        router = Router()
        autosave_enabled = True

        page.dialog.open = False
        refresh()

    def _load_saved(e):
        nonlocal autosave_enabled

        saved_state = load_state()
        if saved_state is None:
            autosave_enabled = True
            refresh()
            return

        _apply_app_state(saved_state.get("app_state", {}))
        router.import_state(saved_state.get("modules", {}))
        autosave_enabled = True

        page.dialog.open = False
        refresh()

    def _show_startup_choice() -> None:
        page.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Resume previous session?"),
            content=ft.Text(
                "A saved simulator state was found. "
                "Load it or start from zero."
            ),
            actions=[
                ft.Button("Start new", on_click=_start_new),
                ft.Button("Load saved", on_click=_load_saved),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog.open = True
        page.update()

    page.add(main_container)
    refresh()
    if saved_state_exists:
        _show_startup_choice()


ft.run(main)
