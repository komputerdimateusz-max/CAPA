@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "BACKEND_DIR=%REPO_ROOT%\backend"
set "VENV_ACTIVATE=%REPO_ROOT%\.venv\Scripts\activate.bat"

if not exist "%VENV_ACTIVATE%" (
  echo [ERROR] Missing virtual environment activation script: %VENV_ACTIVATE%
  echo Create it first: cd /d "%REPO_ROOT%" ^&^& python -m venv .venv
  exit /b 1
)

call "%VENV_ACTIVATE%"
if errorlevel 1 (
  echo [ERROR] Failed to activate virtual environment.
  exit /b 1
)

python -c "import atm_tracker; print('[DEV] atm_tracker imported from:', atm_tracker.__file__)"
if errorlevel 1 (
  echo [ERROR] Could not import atm_tracker. Run: pip install -e .
  exit /b 1
)

cd /d "%BACKEND_DIR%"
uvicorn app.main:app --reload
