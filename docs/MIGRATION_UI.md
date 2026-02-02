# UI Migration Map (Streamlit → FastAPI UI)

## Scope & guiding rules
- **Strangler pattern**: migrate one module at a time; Streamlit stays as legacy until parity is achieved.
- **No HTTP calls to `/api` from `/ui`**; UI routes must call internal services/repositories directly.
- **Business rules must remain stable**, especially:
  - Days late calculation
  - Time-to-close (TTC)
  - On‑time close rate
  - Daily KPI per unique production day
  - Explorer axis formatting

---

## Module-by-module migration map

### 1) Actions (Streamlit: `atm_tracker/actions/ui.py`)
**Feature summary**
- Wizard-style **Add Action** (template + multi-step form) and **Actions list** view with KPIs.
- **Action details** view with status, dates, tags, analysis notes, and subtasks.

**Inputs / filters**
- Status (multi-select), Champion, Project/Family, Search (ID/title), Due date range.
- Add Action wizard fields: title, project, champion, owner/team, status, created/due/closed dates, cost fields, tags.

**Outputs / tables / charts**
- KPI row: open actions, overdue actions, average days late, on-time close rate.
- Actions table with status, champion, project/family, target date, closed date, days late.
- Export CSV (from filtered list).
- Action detail and subtask list.

**Data sources**
- CSV/SQLite via `atm_tracker.actions.repo`.
- Optional API via `action_tracking.api_client` (when `USE_API` enabled).
- Subtasks from `action_tasks` table.

**Business rules**
- Days late: sum subtask overdue days (if subtasks exist) else action overdue days; zero if closed.
- On-time close rate: closed actions with closed date ≤ due date.
- Days late and TTC logic is a **core KPI dependency** for Champions/KPI pages.

**UI target route**
- `/ui/actions` (list + KPIs + filters + pagination)
- `/ui/actions/{id}` (details + subtasks)

**API/service dependencies**
- `backend/app/repositories/actions.py`
- `backend/app/services/metrics.py` and `backend/app/services/kpi.py`

**Migration complexity**: **L** (largest surface + forms + KPIs + subtasks + export)

**Dependencies**
- Settings (Champions/Projects) for lookup lists.
- Analyses (optional links from Action details).

---

### 2) Analyses (Streamlit: `atm_tracker/analyses/ui.py`)
**Feature summary**
- Analysis templates: **5 Why**, **8D**, **A3**.
- List, add, and detail views.
- Link analyses to actions; add actions from analysis details.

**Inputs / filters**
- Analysis type selector; template-specific text areas.
- Status (Open/Closed), date range, search.
- Link action selector.

**Outputs / tables / charts**
- Analysis list table (status, type, owner/champion, created/updated).
- Analysis detail view with filled template sections.

**Data sources**
- `atm_tracker.analyses.repo` for analysis records.
- `atm_tracker.actions.repo` to link actions and show action metadata.
- `atm_tracker.champions.repo`, `atm_tracker.projects.repo` for reference fields.

**Business rules**
- Analysis IDs are generated and linked to actions (1-to-many mapping).
- Analysis status controls close date and visibility.

**UI target route**
- `/ui/analyses` (list)
- `/ui/analyses/{id}` (details)

**API/service dependencies**
- `backend/app/repositories/analyses.py` (or equivalent module)

**Migration status**: ✅ **Completed** (templates + list/detail; action linking pending)

**Migration complexity**: **M** (form-heavy but mostly text)

**Dependencies**
- Actions (link/unlink; create action from analysis).
- Settings (champion/project lookup).

**Notes / differences**
- Ishikawa template is available as a placeholder; detailed sections and action linking are TODOs.

---

### 3) Projects (Streamlit: `atm_tracker/projects/ui.py`)
**Feature summary**
- Project list with rollups (open/overdue actions, days late).
- Project details with KPI cards and related actions.

**Inputs / filters**
- Search by name, status, sort by due date/open actions, pagination.
- Project detail filters for only open/overdue actions.

**Outputs / tables / charts**
- Project list table (name, status, due, rollups).
- Project detail KPIs + related actions table.

**Data sources**
- `backend/app/repositories/projects.py` + `backend/app/repositories/actions.py`.
- KPI rollups via `backend/app/services/projects.py`.

**Business rules**
- Days late and KPI metrics reuse core Actions logic (subtask-aware).

**UI target route**
- `/ui/projects` (list + filters + pagination)
- `/ui/projects/{id}` (detail + actions)

**Migration status**: ✅ **Completed**

---

### 4) KPI Dashboard (Streamlit: `atm_tracker/kpi_dashboard/ui.py`)
**Feature summary**
- Global KPI summary for actions (open/overdue/closed/on-time, days late).
- Filters for project, champion, status, search, date range.
- Plotly charts for trends and breakdowns.

**Inputs / filters**
- Project, Champion, Status, Search, Date range.

**Outputs / tables / charts**
- KPI cards, trend charts (Plotly), insights panel.
- Export panel for filtered dataset.

**Data sources**
- `atm_tracker.actions.repo` for actions + days late map.

**Business rules**
- Uses the same Days late + TTC logic as Actions.
- Ensures KPI counts align with action status rules.

**UI target route**
- `/ui/kpi` (MVP table view; charts pending)
- `/ui/explorer` (MVP table view; charts pending)

**API/service dependencies**
- `backend/app/repositories/actions.py`
- `backend/app/services/metrics.py`

**Migration status**: 🚧 **In progress** (MVP tables shipped; charts pending)

**Migration complexity**: **M/L** (charting + insight logic)

**Dependencies**
- Actions module (core data source).

---

### 5) Champions (Streamlit: `atm_tracker/champions/ui.py`)
**Feature summary**
- Champion ranking based on actions and subtasks.
- Drill-down into action and analysis contributors.
- Score log/audit trail for ranking.

**Inputs / filters**
- Date range, action status, champion selection.
- Toggle between action vs subtask scoring.

**Outputs / tables / charts**
- Ranking table + KPIs (open/closed/overdue/avg TTC).
- Drill-down table of actions & analyses tied to champion.
- Score log saved for auditability.

**Data sources**
- `atm_tracker.actions.repo` (actions + tasks)
- `atm_tracker.analyses.repo` (analysis links)
- `atm_tracker.champions.repo` (champion reference)
- `atm_tracker.scoring.champion_scoring` (scoring logic)

**Business rules**
- Champion scoring uses weighted KPIs (open/closed/overdue/time to close).
- Score log supports auditability and transparency.

**UI target route**
- `/ui/champions` (ranking)
- `/ui/champions/{id}` (drill-down)

**API/service dependencies**
- `backend/app/repositories/champions.py`
- `backend/app/services/scoring.py` (or similar)

**Migration notes**
- Current FastAPI UI scoring is actions-only (analyses scoring will be added when analyses are migrated).

**Migration status**: ✅ **Completed** (actions-only scoring; see note above)

**Migration complexity**: **L** (ranking logic + drill-down + audit log)

---

### 6) Settings (Streamlit: `atm_tracker/settings/ui.py`)
**Feature summary**
- Manage Champions and Projects reference data.
- Add and edit records used across Actions and KPIs.

**Inputs / filters**
- Champion name field.
- Project name, status, and due date fields.

**Outputs / tables / charts**
- Champion list with edit links.
- Project list with edit links.

**Data sources**
- `backend/app/models/champion.py`
- `backend/app/models/project.py`

**UI target route**
- `/ui/settings`

**API/service dependencies**
- `backend/app/services/settings.py`

**Migration status**: ✅ **Completed** (add/edit flows)

**Notes / differences**
- No soft-delete/inactive toggles yet; the UI focuses on add/edit for the current SQL schema.

**Dependencies**
- Actions + Analyses.
- Settings (champion reference data).

---

### Supporting modules (non-UI but required)

#### Projects (Streamlit: `atm_tracker/projects/repo.py`)
- Used for action/project filters and settings maintenance.
- UI currently lives under Settings in Streamlit.

#### Scoring (Streamlit: `atm_tracker/scoring/champion_scoring.py`)
- Champion ranking and scoring logic used by Champions UI.
- Must remain consistent during migration (auditability requirement).

#### Shared UI utilities (Streamlit: `atm_tracker/ui/*`)
- Layout, styles, KPI row widgets, and table helpers.
- Translate to Jinja templates and HTMX partials over time.

---

## Module dependencies (high-level)
- **Settings** → provides Champions/Projects used everywhere.
- **Actions** → source of truth for KPIs, Champions ranking, and KPI dashboard.
- **Analyses** → links to Actions; contributes to Champions drill-downs.
- **Champions** → relies on Actions + Analyses + Scoring.
- **KPI Dashboard / Explorer** → relies on Actions and KPI business rules.

---

## UI Route status (as of this migration step)
- **Ready**: `/ui/actions`, `/ui/actions/{id}`, `/ui/projects`, `/ui/projects/{id}`, `/ui/champions`, `/ui/champions/{id}`, `/ui/explorer`, `/ui/kpi`, `/ui/analyses`, `/ui/analyses/{id}`, `/ui/settings`
