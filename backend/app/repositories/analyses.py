from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import re
from typing import Iterable

import pandas as pd

ANALYSIS_TYPES = ["5WHY", "ISHIKAWA", "8D", "A3"]
ANALYSIS_STATUSES = ["Open", "Closed"]

BASE_COLUMNS = [
    "analysis_id",
    "type",
    "title",
    "description",
    "champion",
    "status",
    "created_at",
    "closed_at",
]

WHY_FIELDS = [
    "problem_statement",
    "why1",
    "why2",
    "why3",
    "why4",
    "why5",
    "root_cause",
    "solution",
]

EIGHT_D_FIELDS = [
    "d1_team",
    "d2_problem_description",
    "d3_interim_containment_actions",
    "d4_root_cause",
    "d5_corrective_actions",
    "d6_verification_effectiveness",
    "d7_preventive_actions",
    "d8_closure_lessons_learned",
]

A3_FIELDS = [
    "a3_plan_problem",
    "a3_plan_analysis",
    "a3_plan_target",
    "a3_plan_root_cause",
    "a3_do_actions_description",
    "a3_check_results_verification",
    "a3_act_standardization_lessons",
]

ANALYSIS_COLUMNS = BASE_COLUMNS + WHY_FIELDS + EIGHT_D_FIELDS + A3_FIELDS
ANALYSIS_ACTIONS_COLUMNS = ["analysis_id", "action_id"]


def _get_data_dir() -> Path:
    env_value = os.environ.get("CAPA_DATA_DIR")
    if env_value:
        return Path(env_value)
    return Path(__file__).resolve().parents[3] / "data"


def _analysis_file() -> Path:
    return _get_data_dir() / "analyses.csv"


def _analysis_actions_file() -> Path:
    return _get_data_dir() / "analysis_actions.csv"


def _ensure_storage() -> None:
    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    analysis_file = _analysis_file()
    actions_file = _analysis_actions_file()
    if not analysis_file.exists():
        pd.DataFrame(columns=ANALYSIS_COLUMNS).to_csv(analysis_file, index=False)
    if not actions_file.exists():
        pd.DataFrame(columns=ANALYSIS_ACTIONS_COLUMNS).to_csv(actions_file, index=False)


def _load_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    _ensure_storage()
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=columns)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[columns + [col for col in df.columns if col not in columns]]
    return df


def _save_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[columns + [col for col in df.columns if col not in columns]]
    df.to_csv(path, index=False)


def list_analyses() -> list[dict[str, object]]:
    df = _load_csv(_analysis_file(), ANALYSIS_COLUMNS)
    for col in ("created_at", "closed_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
            df[col] = df[col].apply(lambda value: value if pd.notna(value) else None)
    for col in df.columns:
        if col not in {"created_at", "closed_at"}:
            df[col] = df[col].fillna("")
    if df.empty:
        return []
    return [row._asdict() for row in df.itertuples(index=False)]


def get_analysis(analysis_id: str) -> dict[str, object] | None:
    analyses = list_analyses()
    for row in analyses:
        if str(row.get("analysis_id")) == str(analysis_id):
            return row
    return None


def upsert_analysis(payload: dict[str, object]) -> None:
    df = _load_csv(_analysis_file(), ANALYSIS_COLUMNS)
    analysis_id = str(payload.get("analysis_id") or "").strip()
    if not analysis_id:
        raise ValueError("analysis_id is required.")
    row = {col: payload.get(col, "") for col in ANALYSIS_COLUMNS}
    row["analysis_id"] = analysis_id
    if analysis_id in df["analysis_id"].astype(str).tolist():
        df.loc[df["analysis_id"].astype(str) == analysis_id, ANALYSIS_COLUMNS] = [row[col] for col in ANALYSIS_COLUMNS]
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _save_csv(df, _analysis_file(), ANALYSIS_COLUMNS)


def close_analysis(analysis_id: str, closed_at: date | None = None) -> None:
    df = _load_csv(_analysis_file(), ANALYSIS_COLUMNS)
    if df.empty:
        return
    closed_value = closed_at or date.today()
    mask = df["analysis_id"].astype(str) == str(analysis_id)
    df.loc[mask, "status"] = "Closed"
    df.loc[mask, "closed_at"] = closed_value.isoformat()
    _save_csv(df, _analysis_file(), ANALYSIS_COLUMNS)


def list_linked_action_ids(analysis_id: str) -> list[int]:
    df = _load_csv(_analysis_actions_file(), ANALYSIS_ACTIONS_COLUMNS)
    if df.empty:
        return []
    matches = df[df["analysis_id"].astype(str) == str(analysis_id)]
    if matches.empty:
        return []
    return [int(value) for value in matches["action_id"].tolist() if str(value).isdigit()]


def generate_analysis_id(analysis_type: str, existing_ids: Iterable[str] | None = None) -> str:
    if analysis_type not in ANALYSIS_TYPES:
        raise ValueError("Invalid analysis type.")
    current_year = date.today().year
    prefix = f"{analysis_type}-{current_year}-"
    if existing_ids is None:
        existing_ids = [str(row.get("analysis_id", "")) for row in list_analyses()]
    pattern = re.compile(rf"^{re.escape(prefix)}(\d{{4}})$")
    max_seq = 0
    for value in existing_ids:
        match = pattern.match(str(value))
        if match:
            max_seq = max(max_seq, int(match.group(1)))
    return f"{prefix}{max_seq + 1:04d}"


__all__ = [
    "A3_FIELDS",
    "ANALYSIS_ACTIONS_COLUMNS",
    "ANALYSIS_COLUMNS",
    "ANALYSIS_STATUSES",
    "ANALYSIS_TYPES",
    "EIGHT_D_FIELDS",
    "WHY_FIELDS",
    "close_analysis",
    "generate_analysis_id",
    "get_analysis",
    "list_analyses",
    "list_linked_action_ids",
    "upsert_analysis",
]
