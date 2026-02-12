# Action-to-Money Tracker (CAPA ROI)

Action-to-Money Tracker is a **decision-intelligence layer** between shopfloor data and management.
It links **corrective actions (CAPA / actions)** with **production metrics** (scrap, downtime, OEE) and converts
their impact into **real money (€), time, ROI and payback**.

This is **not** a QMS/MES/ERP replacement.
It’s the missing layer that answers one question:

> Which actions actually save money — and which ones are just “closed” on paper?

---

## Core Value

- **Money-first decisions**: rank and prioritize actions by **€ savings**, not by status.
- **Before/After impact**: every action is evaluated against a baseline.
- **Confidence & auditability**: show uncertainty and explain every number.
- **Champion ranking**: reward people for *real impact*, not activity.
- **Management PDF**: 1–3 pages executive summary.

---

## MVP Scope

✅ Before/After analysis (scrap, downtime, OEE)  
✅ Savings calculation in € + time recovered  
✅ ROI + payback time  
✅ Champion ranking (weighted by confidence)  
✅ PDF report for management  

---

## Run the backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

### Primary UI (FastAPI)

Primary UI: /ui (FastAPI)
Legacy UI: Streamlit (archived)

The production UI is served from FastAPI. Open: `http://127.0.0.1:8000/ui/actions`.

### Streamlit (legacy/dev-only)

**Windows CMD**
```cmd
set USE_API=true
set API_BASE_URL=http://127.0.0.1:8000
streamlit run app.py
```

**PowerShell**
```powershell
$env:USE_API="true"
$env:API_BASE_URL="http://127.0.0.1:8000"
streamlit run app.py
```


### Run database migrations

Before starting the backend, apply Alembic migrations so the SQLite schema matches the code (including the Champion refactor fields):

```bash
cd backend
alembic upgrade head
```

**Windows PowerShell**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

## Data Inputs (MVP)

### 1) Actions (CAPA)
Minimal fields:
- `id, title, line, project_or_family, owner, champion`
- `implemented_at, closed_at`
- optional: `cost_internal_hours, cost_external_eur, cost_material_eur`

### 2) Production metrics (daily)
Minimal fields:
- `date, line, project_or_family`
- `produced_qty`
- `scrap_qty, scrap_cost_eur`
- `downtime_min`
- optional: `oee`

---

## KPI Logic (High level)

- **Scrap savings (€)**: reduced scrap rate or scrap cost (before vs after)
- **Downtime savings (€)**: reduced downtime minutes × cost per minute
- **ROI**: `total_savings / total_action_cost`
- **Payback**: `total_action_cost / savings_per_day`
- **Confidence score**: heuristic score based on window length, number of production days, stability, overlaps

Detailed formulas live in: `docs/02_kpis_formulas.md`

---

## Repo Structure (planned)


## DEV Troubleshooting: Settings UI still looks old

If Settings still renders an older UI after pulling latest code, verify Python is loading the repo module (not a stale site-packages install).

1. **Verify resolved module path**

```bash
python -c "import atm_tracker.settings.ui as m; print(m.__file__)"
```

Expected: path points to `<repo>/src/atm_tracker/settings/ui.py`.

2. **Reinstall editable package**

```bash
pip install -e .
```

On this repo, `run_dev.bat` now auto-runs editable install when module resolution is not under the local `src/` tree.

3. **Restart dev runtime**

- Stop running server/process (`Ctrl+C`).
- Start again (`run_dev.bat` for backend, or your Streamlit dev command).
- Reload the browser page.

