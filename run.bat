cd C:\CAPA\backend
call .venv\Scripts\activate
pip uninstall -y passlib bcrypt
pip install "passlib[bcrypt]" "bcrypt<4"
set AUTH_ENABLED=true
set SECRET_KEY=dev_dsad234325
set ADMIN_USERNAME=admin
set ADMIN_PASSWORD=admin123
python -m uvicorn app.main:app --reload --port 8000