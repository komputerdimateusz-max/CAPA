# CAPA Backend (FastAPI)

## Quickstart

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

On Windows, keep `bcrypt` pinned to `<4` (already specified in the backend dependencies) because `passlib` expects the legacy interface provided by `bcrypt<4`.

### Configure database

By default the backend uses a SQLite database stored at `data/actions_api.db` in the repo root.
Override with `DATABASE_URL`:

```bash
export DATABASE_URL=sqlite:////absolute/path/to/actions_api.db
```


### Run Alembic migrations

After creating the virtual environment and before running the API, migrate the database:

```bash
alembic upgrade head
```

**Windows PowerShell**
```powershell
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

If startup reports missing Champion columns (for example `first_name`/`last_name`), your DB is behind and this command is required.

### Run the API

```bash
uvicorn app.main:app --reload
```

OpenAPI docs will be available at http://localhost:8000/docs.

### Debugging UI 500 errors in development

To surface full traceback details for unhandled `/ui` exceptions during development:

```bash
export DEV_DEBUG_UI_ERRORS=true
export LOG_LEVEL=debug
uvicorn app.main:app --reload --log-level debug
```

**Windows PowerShell**
```powershell
$env:DEV_DEBUG_UI_ERRORS="true"
$env:LOG_LEVEL="debug"
uvicorn app.main:app --reload --log-level debug
```

With `DEV_DEBUG_UI_ERRORS=true`, unhandled exceptions on `/ui` routes render an HTML error page with exception details and traceback, and exceptions are logged to the console. API behavior is unchanged.


### Run tests

```bash
pytest
```

## CSV Import

If you have CSV files (e.g. `actions.csv`, `projects.csv`, `subtasks.csv`, `champions.csv`) you can import them once:

```bash
python scripts/import_csv_to_sqlite.py --data-dir ../data
```

CSV columns are mapped by header name. Unknown columns are ignored. The importer will create missing tables.

## Notes
- SQLite is the default backend, but the SQLAlchemy models are portable to PostgreSQL.
- Dates are returned as ISO strings (YYYY-MM-DD) and datetimes as ISO 8601.
