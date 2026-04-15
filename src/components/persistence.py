from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import flet as ft

from common import BASE_DIR, PERSPECTIVE_SET
from components.data_classes import AppState

MODULE_STATE_FORMAT = "signal-interactive-module-state.v2"
DESKTOP_STATE_SUBDIR = Path("SignalInteractive") / "module_states"
WEB_UPLOAD_DIR = BASE_DIR.parent / "build" / "module_state_uploads"


def build_module_snapshot(app_state: AppState, router) -> dict[str, Any] | None:
    module_id = app_state.current_module
    if not module_id:
        return None

    module = router.modules.get(module_id)
    if module is None or not hasattr(module, "export_state"):
        return None

    module_state = module.export_state()
    if not isinstance(module_state, dict):
        return None

    return {
        "format": MODULE_STATE_FORMAT,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "module_id": module_id,
        "perspective": app_state.perspective,
        "module_state": module_state,
    }


def parse_module_snapshot(payload: Any) -> tuple[str, dict[str, Any], str]:
    if not isinstance(payload, dict):
        raise ValueError("Selected file is not a valid module snapshot.")

    if payload.get("format") != MODULE_STATE_FORMAT:
        raise ValueError("Selected file is not a supported module snapshot.")

    module_id = payload.get("module_id")
    module_state = payload.get("module_state")
    perspective = payload.get("perspective", "global")

    if not isinstance(module_id, str) or not module_id:
        raise ValueError("Module snapshot is missing a module id.")
    if not isinstance(module_state, dict):
        raise ValueError("Module snapshot does not contain module state data.")
    if not isinstance(perspective, str) or perspective not in PERSPECTIVE_SET:
        perspective = "global"

    return module_id, module_state, perspective


class ModuleStatePersistence:
    def __init__(
        self,
        page: ft.Page,
        app_state: AppState,
        router,
        refresh_callback: Callable[[], None],
        set_status: Callable[[str, bool], None],
    ):
        self.page = page
        self.app_state = app_state
        self.router = router
        self.refresh_callback = refresh_callback
        self.set_status = set_status
        self.file_picker = ft.FilePicker()
        self.page.services.append(self.file_picker)

    def build_controls(self) -> ft.Row:
        save_disabled = not bool(self.app_state.current_module)
        return ft.Row(
            controls=[
                ft.TextButton("Save module state", on_click=self._on_save_clicked, disabled=save_disabled),
                ft.TextButton("Load module state", on_click=self._on_load_clicked),
            ],
            spacing=6,
        )

    def _on_save_clicked(self, e) -> None:
        self.page.run_task(self.save_current_module_state)

    def _on_load_clicked(self, e) -> None:
        self.page.run_task(self.load_module_state)

    async def _desktop_state_root(self) -> Path:
        try:
            documents_dir = await ft.StoragePaths(self.page).get_application_documents_directory()
        except Exception:
            documents_dir = str(Path.cwd())
        return Path(documents_dir)

    def _module_file_name(self, module_id: str) -> str:
        return f"{module_id}.json"

    async def save_current_module_state(self) -> None:
        snapshot = build_module_snapshot(self.app_state, self.router)
        if snapshot is None:
            self.set_status("Open a module before saving its state.", is_error=True)
            self.page.update()
            return

        module_id = str(snapshot["module_id"])
        payload_bytes = json.dumps(snapshot, indent=2, ensure_ascii=False).encode("utf-8")
        file_name = self._module_file_name(module_id)

        try:
            if self.page.web or self.page.platform.is_mobile():
                await self.file_picker.save_file(
                    dialog_title="Save module state",
                    file_name=file_name,
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["json"],
                    src_bytes=payload_bytes,
                )
                self.set_status(f"Prepared download for {module_id}.")
            else:
                root = await self._desktop_state_root()
                root.mkdir(parents=True, exist_ok=True)
                target_path = await self.file_picker.save_file(
                    dialog_title="Save module state",
                    file_name=file_name,
                    initial_directory=str(root),
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["json"],
                )
                if not target_path:
                    self.set_status("Save cancelled.")
                    self.page.update()
                    return

                target_path = Path(target_path)
                target_path.write_bytes(payload_bytes)
                self.set_status(f"Saved module state to {target_path}.")
        except Exception as exc:
            self.set_status(f"Save failed: {exc}", is_error=True)

        self.page.update()

    async def _resolve_loaded_file_path(self, selected_file: ft.FilePickerFile) -> Path:
        if selected_file.path:
            return Path(selected_file.path)

        if not self.page.web:
            raise ValueError("Selected file does not expose a local path.")

        upload_root = WEB_UPLOAD_DIR / "loads"
        upload_root.mkdir(parents=True, exist_ok=True)
        relative_upload_path = Path("loads") / f"{uuid4().hex}_{Path(selected_file.name).name}"
        upload_url = self.page.get_upload_url(relative_upload_path.as_posix(), 60)

        completion = asyncio.Event()
        upload_error: dict[str, str | None] = {"message": None}
        loop = asyncio.get_running_loop()
        previous_handler = self.file_picker.on_upload

        def _mark_finished(error_message: str | None = None) -> None:
            if error_message is not None:
                upload_error["message"] = error_message
            if not completion.is_set():
                completion.set()

        def _handle_upload(event: ft.FilePickerUploadEvent) -> None:
            if previous_handler is not None:
                previous_handler(event)

            if event.error:
                loop.call_soon_threadsafe(_mark_finished, event.error)
                return

            if event.file_name == selected_file.name and event.progress == 1.0:
                loop.call_soon_threadsafe(_mark_finished)

        self.file_picker.on_upload = _handle_upload
        try:
            await self.file_picker.upload(
                [
                    ft.FilePickerUploadFile(
                        upload_url=upload_url,
                        id=selected_file.id,
                        name=selected_file.name,
                    )
                ]
            )
            await asyncio.wait_for(completion.wait(), timeout=60)
        finally:
            self.file_picker.on_upload = previous_handler

        if upload_error["message"]:
            raise ValueError(upload_error["message"])

        target_path = WEB_UPLOAD_DIR / relative_upload_path
        if not target_path.exists():
            raise FileNotFoundError(f"Uploaded file was not found at {target_path}.")

        return target_path

    async def _open_load_dialog(self) -> list[ft.FilePickerFile]:
        initial_directory = None
        if not self.page.web:
            state_root = await self._desktop_state_root()
            state_root.mkdir(parents=True, exist_ok=True)
            initial_directory = str(state_root)

        return await self.file_picker.pick_files(
            dialog_title="Load module state",
            initial_directory=initial_directory,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["json"],
            allow_multiple=False,
        )

    async def load_module_state(self) -> None:
        loaded_path: Path | None = None
        try:
            picked_files = await self._open_load_dialog()
        except Exception as exc:
            self.set_status(f"Load failed: {exc}", is_error=True)
            self.page.update()
            return

        if not picked_files:
            self.set_status("Load cancelled.")
            self.page.update()
            return

        selected_file = picked_files[0]
        try:
            loaded_path = await self._resolve_loaded_file_path(selected_file)
            payload = json.loads(loaded_path.read_text(encoding="utf-8"))
            module_id, module_state, saved_perspective = parse_module_snapshot(payload)
        except Exception as exc:
            self.set_status(f"Load failed: {exc}", is_error=True)
            self.page.update()
            return
        finally:
            if self.page.web and loaded_path is not None:
                with contextlib.suppress(Exception):
                    loaded_path.unlink(missing_ok=True)

        module = self.router.modules.get(module_id)
        if module is None or not hasattr(module, "import_state"):
            self.set_status(f"Unknown module in snapshot: {module_id}", is_error=True)
            self.page.update()
            return

        try:
            module.import_state(module_state)
        except Exception as exc:
            self.set_status(f"Could not import module state: {exc}", is_error=True)
            self.page.update()
            return

        if self.app_state.current_module == module_id:
            self.app_state.perspective = saved_perspective

        self.set_status(f"Loaded module state for '{module_id}'.")
        self.refresh_callback()
        self._show_switch_module_dialog(module_id, saved_perspective)

    def _show_switch_module_dialog(self, module_id: str, saved_perspective: str) -> None:
        def _close(switch_to_loaded: bool) -> None:
            dialog.open = False
            if switch_to_loaded:
                self.app_state.current_module = module_id
                self.app_state.perspective = saved_perspective
                self.set_status(f"Switched to loaded module: {module_id}.")
            self.refresh_callback()
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Enter loaded module?"),
            content=ft.Text(f"State for module '{module_id}' was loaded. Do you want to enter it now?"),
            actions=[
                ft.TextButton("No", on_click=lambda e: _close(False)),
                ft.TextButton("Yes", on_click=lambda e: _close(True)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
