@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "BACKEND_DIR=%REPO_ROOT%\backend"
set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
  echo [ERROR] Missing backend virtualenv python: %VENV_PYTHON%
  echo Create it first: cd /d "%BACKEND_DIR%" ^&^& python -m venv .venv
  exit /b 1
)

set "NEEDS_EDITABLE=0"
"%VENV_PYTHON%" -c "import importlib.util, pathlib; repo = pathlib.Path(r'%REPO_ROOT%').resolve(); spec = importlib.util.find_spec('atm_tracker.settings.ui'); module_path = pathlib.Path(spec.origin).resolve() if spec and spec.origin else None; expected_src = repo / 'src'; print(f'[DEV] atm_tracker.settings.ui resolved to: {module_path or "<missing>"}'); raise SystemExit(0 if module_path and expected_src in module_path.parents else 1)"
if errorlevel 1 set "NEEDS_EDITABLE=1"

if "%NEEDS_EDITABLE%"=="1" (
  echo [DEV] Installing repository package in editable mode...
  "%VENV_PYTHON%" -m pip install -e "%REPO_ROOT%"
  if errorlevel 1 (
    echo [ERROR] Failed to install editable package from %REPO_ROOT%
    exit /b 1
  )
)

cd /d "%BACKEND_DIR%"
set "AUTH_ENABLED=true"
set "SECRET_KEY=dev_secret_key_123"
set "LOG_LEVEL=debug"
set "DEV_DEBUG_UI_ERRORS=true"

"%VENV_PYTHON%" -m uvicorn app.main:app --reload --port 8000 --log-level debug
