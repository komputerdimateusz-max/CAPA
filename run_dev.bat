@echo off
setlocal
cd /d C:\CAPA\backend

call .venv\Scripts\activate

REM --- DEV env ---
set AUTH_ENABLED=true
set SECRET_KEY=dev-secret-change-me-please-32-chars-min

REM --- Make src packages importable (atm_tracker lives in C:\CAPA\src) ---
set PYTHONPATH=C:\CAPA\src;C:\CAPA\backend

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause
endlocal
