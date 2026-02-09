@echo off
setlocal

set "REPO_ROOT=%~dp0"
set "BACKEND_DIR=%REPO_ROOT%backend"
set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
  echo [ERROR] Missing backend virtualenv python: %VENV_PYTHON%
  echo Create it first: cd /d "%BACKEND_DIR%" ^&^& python -m venv .venv
  exit /b 1
)

cd /d "%BACKEND_DIR%"
set "AUTH_ENABLED=true"
set "SECRET_KEY=dev_secret_key_123"
set "LOG_LEVEL=debug"
set "DEV_DEBUG_UI_ERRORS=true"

"%VENV_PYTHON%" -m uvicorn app.main:app --reload --port 8000 --log-level debug
