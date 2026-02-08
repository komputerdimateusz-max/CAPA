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

### Apply migrations

Run migrations before starting the server, especially when reusing an existing SQLite database.

```bash
alembic upgrade head
```

Windows PowerShell:

```powershell
alembic upgrade head
```

### Run the API

```bash
uvicorn app.main:app --reload
```

OpenAPI docs will be available at http://localhost:8000/docs.

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
