PERSPECTIVES = {"global", "alice", "bob", "attacker"}


def serialize_app_state(app_state) -> dict:
    return {
        "current_module": app_state.current_module,
        "current_step": app_state.current_step,
        "perspective": app_state.perspective,
    }


def apply_app_state(app_state, data: dict) -> None:
    app_state.current_module = data.get(
        "current_module", app_state.current_module
    )

    current_step = data.get("current_step", app_state.current_step)
    if isinstance(current_step, int) and current_step >= 0:
        app_state.current_step = current_step

    perspective = data.get("perspective", app_state.perspective)
    if perspective in PERSPECTIVES:
        app_state.perspective = perspective


def serialize_payload(app_state, router) -> dict:
    return {
        "app_state": serialize_app_state(app_state),
        "modules": router.export_state(),
    }


def apply_payload(app_state, router, payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False

    apply_app_state(app_state, payload.get("app_state", {}))
    router.import_state(payload.get("modules", {}))
    return True
