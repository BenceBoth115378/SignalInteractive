from common import PERSPECTIVE_SET
from components.data_classes import AppState


def serialize_app_state(app_state: AppState) -> dict:
    return {
        "current_module": app_state.current_module,
        "perspective": app_state.perspective,
        "x3dh_to_dr_bootstrap": app_state.x3dh_to_dr_bootstrap,
    }


def apply_app_state(app_state: AppState, data: dict) -> None:
    app_state.current_module = data.get("current_module", app_state.current_module)

    perspective = data.get("perspective", app_state.perspective)
    if perspective in PERSPECTIVE_SET:
        app_state.perspective = perspective

    bootstrap = data.get("x3dh_to_dr_bootstrap")
    app_state.x3dh_to_dr_bootstrap = bootstrap if isinstance(bootstrap, dict) else None


def serialize_payload(app_state: AppState, router) -> dict:
    return {
        "app_state": serialize_app_state(app_state),
        "modules": router.export_state(),
    }


def apply_payload(app_state: AppState, router, payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False

    apply_app_state(app_state, payload.get("app_state", {}))
    router.import_state(payload.get("modules", {}))
    return True
