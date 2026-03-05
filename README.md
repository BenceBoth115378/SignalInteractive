# Signal Interactive

Interactive application built with [Flet](https://flet.dev/) and Python.

## Prerequisites

- Python 3.12 installed (3.10+ is supported by this project)
- `pip` available (comes with standard Python install)
- Git installed

## 1) (Optional, recommended) Create and activate a virtual environment

Using a virtual environment is optional, but recommended so dependencies stay local to this project.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```


### Windows (cmd)

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2) Install dependencies

Upgrade packaging tools first:

```bash
python -m pip install --upgrade pip setuptools wheel
```

Preferred: install from `requirements.txt` (simple and widely used):

```bash
python -m pip install -r requirements.txt
```

`pyproject.toml` is also available for users who prefer a TOML-based workflow.


## 3) Run the app

From the project root (with virtualenv activated):

### Desktop app

```bash
flet run
```

<!-- ### Web app

```bash
flet run --web
```

If `flet` command is not found, use:

```bash
python -m flet run
python -m flet run --web
```

## 5) Build packages (optional)

Run these from the activated virtual environment.

### Android

```bash
flet build apk -v
```

For more details on building and signing `.apk` or `.aab`, refer to the [Android Packaging Guide](https://docs.flet.dev/publish/android/).

### iOS

```bash
flet build ipa -v
```

For more details on building and signing `.ipa`, refer to the [iOS Packaging Guide](https://docs.flet.dev/publish/ios/).

### macOS

```bash
flet build macos -v
```

For more details on building macOS package, refer to the [macOS Packaging Guide](https://docs.flet.dev/publish/macos/).

### Linux

```bash
flet build linux -v
```

For more details on building Linux package, refer to the [Linux Packaging Guide](https://docs.flet.dev/publish/linux/).

### Windows

```bash
flet build windows -v
```

Packaging guides:

- Android: https://docs.flet.dev/publish/android/
- iOS: https://docs.flet.dev/publish/ios/
- macOS: https://docs.flet.dev/publish/macos/
- Linux: https://docs.flet.dev/publish/linux/
- Windows: https://docs.flet.dev/publish/windows/

## Troubleshooting

- `ModuleNotFoundError`: make sure virtualenv is activated and run `python -m pip install -r requirements.txt` (or `python -m pip install .`) again.
- `flet` not recognized: use `python -m flet ...` or reinstall with `python -m pip install .[dev]`.
- Wrong Python interpreter in IDE: select `.venv` interpreter for this workspace.

## Useful cleanup/deactivation commands

- Deactivate virtualenv:

	```bash
	deactivate
	```

- Recreate environment from scratch:

	1. Delete `.venv`
	2. Repeat setup steps 2 and 3 -->