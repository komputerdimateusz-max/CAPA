from __future__ import annotations

from datetime import date
from pathlib import Path
import re
from typing import Iterable

import pandas as pd


DATA_DIR = Path.cwd() / "data"
ANALYSES_FILE = DATA_DIR / "analyses.csv"
ANALYSIS_ACTIONS_FILE = DATA_DIR / "analysis_actions.csv"

ANALYSIS_TYPES = ["5WHY", "8D", "A3"]
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


def _ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not ANALYSES_FILE.exists():
        pd.DataFrame(columns=ANALYSIS_COLUMNS).to_csv(ANALYSES_FILE, index=False)
    if not ANALYSIS_ACTIONS_FILE.exists():
        pd.DataFrame(columns=ANALYSIS_ACTIONS_COLUMNS).to_csv(ANALYSIS_ACTIONS_FILE, index=False)


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


def list_analyses() -> pd.DataFrame:
    df = _load_csv(ANALYSES_FILE, ANALYSIS_COLUMNS)
    for col in ("created_at", "closed_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
            df[col] = df[col].apply(lambda value: value if pd.notna(value) else None)
    return df


def get_analysis(analysis_id: str) -> dict[str, object] | None:
    df = list_analyses()
    if df.empty:
        return None
    matches = df[df["analysis_id"] == analysis_id]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()


def upsert_analysis(payload: dict[str, object]) -> None:
    df = _load_csv(ANALYSES_FILE, ANALYSIS_COLUMNS)
    analysis_id = str(payload.get("analysis_id") or "").strip()
    if not analysis_id:
        raise ValueError("analysis_id is required.")
    row = {col: payload.get(col, "") for col in ANALYSIS_COLUMNS}
    row["analysis_id"] = analysis_id
    if analysis_id in df["analysis_id"].astype(str).tolist():
        df.loc[df["analysis_id"].astype(str) == analysis_id, ANALYSIS_COLUMNS] = [row[col] for col in ANALYSIS_COLUMNS]
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _save_csv(df, ANALYSES_FILE, ANALYSIS_COLUMNS)


def close_analysis(analysis_id: str, closed_at: date | None = None) -> None:
    df = _load_csv(ANALYSES_FILE, ANALYSIS_COLUMNS)
    if df.empty:
        return
    closed_value = closed_at or date.today()
    mask = df["analysis_id"].astype(str) == str(analysis_id)
    df.loc[mask, "status"] = "Closed"
    df.loc[mask, "closed_at"] = closed_value.isoformat()
    _save_csv(df, ANALYSES_FILE, ANALYSIS_COLUMNS)


def list_analysis_actions() -> pd.DataFrame:
    df = _load_csv(ANALYSIS_ACTIONS_FILE, ANALYSIS_ACTIONS_COLUMNS)
    return df


def link_action_to_analysis(analysis_id: str, action_id: int) -> None:
    df = _load_csv(ANALYSIS_ACTIONS_FILE, ANALYSIS_ACTIONS_COLUMNS)
    analysis_value = str(analysis_id)
    action_value = str(action_id)
    exists = (
        (df["analysis_id"].astype(str) == analysis_value) & (df["action_id"].astype(str) == action_value)
    ).any()
    if not exists:
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "analysis_id": analysis_value,
                            "action_id": action_value,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        _save_csv(df, ANALYSIS_ACTIONS_FILE, ANALYSIS_ACTIONS_COLUMNS)


def list_linked_action_ids(analysis_id: str) -> list[int]:
    df = _load_csv(ANALYSIS_ACTIONS_FILE, ANALYSIS_ACTIONS_COLUMNS)
    if df.empty:
        return []
    matches = df[df["analysis_id"].astype(str) == str(analysis_id)]
    if matches.empty:
        return []
    return [int(value) for value in matches["action_id"].tolist() if str(value).isdigit()]


def list_linked_analysis_ids(action_id: int) -> list[str]:
    df = _load_csv(ANALYSIS_ACTIONS_FILE, ANALYSIS_ACTIONS_COLUMNS)
    if df.empty:
        return []
    matches = df[df["action_id"].astype(str) == str(action_id)]
    if matches.empty:
        return []
    return [str(value) for value in matches["analysis_id"].tolist() if str(value)]


def generate_analysis_id(analysis_type: str, existing_ids: Iterable[str] | None = None) -> str:
    if analysis_type not in ANALYSIS_TYPES:
        raise ValueError("Invalid analysis type.")
    current_year = date.today().year
    prefix = f"{analysis_type}-{current_year}-"
    if existing_ids is None:
        df = list_analyses()
        existing_ids = df["analysis_id"].astype(str).tolist() if not df.empty else []
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
    "link_action_to_analysis",
    "list_analyses",
    "list_analysis_actions",
    "list_linked_action_ids",
    "list_linked_analysis_ids",
    "upsert_analysis",
]
