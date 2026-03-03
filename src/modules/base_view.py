import flet as ft


def format_key(value) -> str:
    if value is None:
        return "None"
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return str(value)
    if hasattr(value, "public"):
        return str(value.public)
    return str(value)


def last_n_chars(value: str, n: int) -> str:
    return value[-n:] if len(value) > n else value


def get_clipboard_service(page: ft.Page) -> ft.Clipboard:
    for service in page.services:
        if isinstance(service, ft.Clipboard):
            return service

    clipboard = ft.Clipboard()
    page.services.append(clipboard)
    return clipboard


async def copy_to_clipboard(page: ft.Page, label: str, value: str) -> None:
    clipboard = get_clipboard_service(page)
    await clipboard.set(value)
    page.snack_bar = ft.SnackBar(ft.Text(f"Copied {label} to clipboard"))
    page.snack_bar.open = True
    page.update()


def make_copy_handler(page: ft.Page, label: str, full_value: str):
    async def _handler(e):
        await copy_to_clipboard(page, label, full_value)

    return _handler
