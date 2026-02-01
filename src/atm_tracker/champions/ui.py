from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd
import streamlit as st

from atm_tracker.actions.db import init_db
from atm_tracker.actions.repo import list_actions, list_all_tasks
from atm_tracker.analyses.repo import list_analyses, list_analysis_actions
from atm_tracker.champions.repo import list_champions, save_champion_score_log
from atm_tracker.scoring.champion_scoring import compute_ranking, compute_score_log
from atm_tracker.ui.layout import footer, page_header, section
from atm_tracker.ui.styles import inject_global_styles, muted

ALL_CHAMPIONS_LABEL = "All champions"


def _normalize_column_name(value: str) -> str:
    return "".join(value.lower().replace(" ", "").replace("_", "").split())


def _find_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    normalized = {_normalize_column_name(col): col for col in columns}
    for candidate in candidates:
        key = _normalize_column_name(candidate)
        if key in normalized:
            return normalized[key]
    return None


def _prepare_actions(df: pd.DataFrame) -> dict[str, str | None]:
    column_map = {
        "champion": _find_column(df.columns, ["champion", "owner", "responsible"]),
        "status": _find_column(df.columns, ["status", "state"]),
        "due_date": _find_column(df.columns, ["due_date", "due", "target_date", "targetdate"]),
        "closed_at": _find_column(df.columns, ["closed_at", "closed_date", "closed", "closedon"]),
        "created_at": _find_column(df.columns, ["created_at", "created_date", "created", "date"]),
    }

    for key in ("due_date", "closed_at", "created_at"):
        col = column_map[key]
        if col:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return column_map


def _normalize_status(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower()


def _is_closed(series: pd.Series, closed_values: set[str]) -> pd.Series:
    return _normalize_status(series).isin(closed_values)


def _format_metric(value: float | int | str | None) -> str | int | float:
    if value is None:
        return "N/A"
    return value


def _build_metrics(df: pd.DataFrame, column_map: dict[str, str | None]) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []

    status_col = column_map.get("status")
    due_col = column_map.get("due_date")
    closed_col = column_map.get("closed_at")
    created_col = column_map.get("created_at")

    total_actions = len(df)

    open_actions: int | None
    closed_actions: int | None
    overdue_actions: int | None
    on_time_actions: int | None
    on_time_rate: float | None
    avg_time_to_close: float | None

    if status_col:
        status_values = _normalize_status(df[status_col])
        open_actions = int((status_values != "closed").sum())
        closed_actions = int((status_values == "closed").sum())
    else:
        warnings.append("Status column missing; open/closed KPIs unavailable.")
        open_actions = None
        closed_actions = None

    if status_col and due_col:
        status_values = _normalize_status(df[status_col])
        overdue_actions = int(
            ((status_values != "closed") & (df[due_col] < pd.Timestamp(date.today()))).sum()
        )
    else:
        warnings.append("Status or due date column missing; overdue KPI unavailable.")
        overdue_actions = None

    if status_col and due_col and closed_col:
        status_values = _normalize_status(df[status_col])
        on_time_actions = int(((status_values == "closed") & (df[closed_col] <= df[due_col])).sum())
        closed_count = int((status_values == "closed").sum())
        on_time_rate = (on_time_actions / closed_count) if closed_count > 0 else 0.0
    else:
        warnings.append("Status, due date, or closed date column missing; on-time KPI unavailable.")
        on_time_actions = None
        on_time_rate = None

    if created_col and closed_col:
        time_to_close = (df[closed_col] - df[created_col]).dt.days
        avg_time_to_close = float(time_to_close.dropna().mean()) if not time_to_close.dropna().empty else 0.0
    else:
        avg_time_to_close = None

    metrics = {
        "total_actions": total_actions,
        "open_actions": open_actions,
        "closed_actions": closed_actions,
        "overdue_actions": overdue_actions,
        "on_time_actions": on_time_actions,
        "on_time_rate": on_time_rate,
        "avg_time_to_close": avg_time_to_close,
    }

    return metrics, warnings


def _prepare_subtasks(
    tasks_df: pd.DataFrame,
    actions_df: pd.DataFrame,
    action_column_map: dict[str, str | None],
    champions_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, str | None], list[str]]:
    warnings: list[str] = []
    column_map = {
        "action_id": _find_column(tasks_df.columns, ["action_id", "action", "actionid", "parent_id"]),
        "champion": _find_column(
            tasks_df.columns,
            [
                "assignee_champion_id",
                "assignee_champion",
                "assignee",
                "champion",
                "owner",
                "responsible",
            ],
        ),
        "status": _find_column(tasks_df.columns, ["status", "state"]),
        "due_date": _find_column(tasks_df.columns, ["target_date", "due_date", "due", "targetdate"]),
        "closed_at": _find_column(tasks_df.columns, ["done_at", "closed_at", "closed_date", "done_date"]),
        "created_at": _find_column(tasks_df.columns, ["created_at", "created_date", "created", "date"]),
    }

    for key in ("due_date", "closed_at", "created_at"):
        col = column_map[key]
        if col:
            tasks_df[col] = pd.to_datetime(tasks_df[col], errors="coerce")

    champion_col = column_map.get("champion")
    resolved_col: str | None = None
    if champion_col:
        resolved_col = "champion_resolved"
        if champion_col.endswith("_id"):
            name_col = None
            if not champions_df.empty:
                if "name_display" in champions_df.columns:
                    name_col = "name_display"
                elif "name" in champions_df.columns:
                    name_col = "name"
            if name_col and "id" in champions_df.columns:
                id_map = champions_df.set_index("id")[name_col].to_dict()
                tasks_df[resolved_col] = tasks_df[champion_col].map(id_map)
            else:
                tasks_df[resolved_col] = tasks_df[champion_col]
        else:
            tasks_df[resolved_col] = tasks_df[champion_col]

    action_id_col = column_map.get("action_id")
    actions_id_col = _find_column(actions_df.columns, ["id", "action_id", "actionid"])
    action_champion_col = action_column_map.get("champion")

    if action_id_col and actions_id_col and action_champion_col:
        actions_lookup = actions_df[[actions_id_col, action_champion_col]].rename(
            columns={actions_id_col: action_id_col, action_champion_col: "action_champion"},
        )
        tasks_df = tasks_df.merge(actions_lookup, on=action_id_col, how="left")
        if resolved_col:
            tasks_df[resolved_col] = tasks_df[resolved_col].fillna("")
            tasks_df["action_champion"] = tasks_df["action_champion"].fillna("")
            tasks_df[resolved_col] = tasks_df[resolved_col].where(
                tasks_df[resolved_col].astype(str).str.strip() != "",
                tasks_df["action_champion"],
            )
        else:
            resolved_col = "action_champion"
    elif not champion_col:
        warnings.append("Sub-task champion/owner column missing; using parent action champions when available.")

    if not action_id_col:
        warnings.append("Sub-task action_id column missing; unable to inherit champions from actions.")

    if resolved_col:
        tasks_df[resolved_col] = tasks_df[resolved_col].fillna("Unassigned")

    column_map["champion"] = resolved_col
    return tasks_df, column_map, warnings


def _build_subtask_metrics(
    df: pd.DataFrame, column_map: dict[str, str | None]
) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []

    status_col = column_map.get("status")
    due_col = column_map.get("due_date")
    closed_col = column_map.get("closed_at")
    created_col = column_map.get("created_at")
    closed_values = {"done", "closed"}

    total_subtasks = len(df)

    open_subtasks: int | None
    closed_subtasks: int | None
    overdue_subtasks: int | None
    on_time_subtasks: int | None
    subtask_on_time_rate: float | None
    avg_subtask_time_to_close: float | None

    if status_col:
        closed_mask = _is_closed(df[status_col], closed_values)
        open_subtasks = int((~closed_mask).sum())
        closed_subtasks = int(closed_mask.sum())
    else:
        warnings.append("Sub-task status column missing; open/closed KPIs unavailable.")
        open_subtasks = None
        closed_subtasks = None

    if status_col and due_col:
        closed_mask = _is_closed(df[status_col], closed_values)
        overdue_subtasks = int(((~closed_mask) & (df[due_col] < pd.Timestamp(date.today()))).sum())
    else:
        warnings.append("Sub-task status or due date column missing; overdue KPI unavailable.")
        overdue_subtasks = None

    if status_col and due_col and closed_col:
        closed_mask = _is_closed(df[status_col], closed_values)
        on_time_subtasks = int((closed_mask & (df[closed_col] <= df[due_col])).sum())
        closed_count = int(closed_mask.sum())
        subtask_on_time_rate = (on_time_subtasks / closed_count) if closed_count > 0 else 0.0
    else:
        warnings.append("Sub-task status, due date, or closed date column missing; on-time KPI unavailable.")
        on_time_subtasks = None
        subtask_on_time_rate = None

    if created_col and closed_col:
        time_to_close = (df[closed_col] - df[created_col]).dt.days
        avg_subtask_time_to_close = float(time_to_close.dropna().mean()) if not time_to_close.dropna().empty else 0.0
    else:
        avg_subtask_time_to_close = None

    metrics = {
        "total_subtasks": total_subtasks,
        "open_subtasks": open_subtasks,
        "closed_subtasks": closed_subtasks,
        "overdue_subtasks": overdue_subtasks,
        "on_time_subtasks": on_time_subtasks,
        "subtask_on_time_rate": subtask_on_time_rate,
        "avg_subtask_time_to_close": avg_subtask_time_to_close,
    }
    return metrics, warnings


def _format_rate(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.0%}"


def _build_action_on_time_rate(df: pd.DataFrame, column_map: dict[str, str | None]) -> float | None:
    status_col = column_map.get("status")
    due_col = column_map.get("due_date")
    closed_col = column_map.get("closed_at")
    if not status_col or not due_col or not closed_col or df.empty:
        return None
    status_values = _normalize_status(df[status_col])
    closed_mask = status_values == "closed"
    closed_with_due = closed_mask & df[due_col].notna() & df[closed_col].notna()
    total_closed = int(closed_with_due.sum())
    if total_closed == 0:
        return None
    on_time = int((closed_with_due & (df[closed_col] <= df[due_col])).sum())
    return on_time / total_closed


def _build_analysis_metrics(
    analyses_df: pd.DataFrame,
    links_df: pd.DataFrame,
    actions_df: pd.DataFrame,
    champion_col: str,
    champion_selection: str,
) -> dict[str, int]:
    if analyses_df.empty:
        open_count = 0
        closed_count = 0
    else:
        filtered = analyses_df.copy()
        if champion_selection != ALL_CHAMPIONS_LABEL:
            filtered = filtered[filtered["champion"] == champion_selection]
        status_normalized = filtered["status"].fillna("").astype(str).str.lower()
        closed_count = int((status_normalized == "closed").sum())
        open_count = int((status_normalized != "closed").sum())

    linked_action_count = 0
    if not links_df.empty and not actions_df.empty:
        links_df = links_df.copy()
        links_df["action_id"] = pd.to_numeric(links_df["action_id"], errors="coerce")
        links_df = links_df.dropna(subset=["action_id"])
        if champion_selection != ALL_CHAMPIONS_LABEL:
            action_ids = actions_df[actions_df[champion_col] == champion_selection]["id"].tolist()
            linked_action_count = int(
                links_df[links_df["action_id"].isin(action_ids)]["action_id"].nunique()
            )
        else:
            linked_action_count = int(links_df["action_id"].nunique())

    return {
        "analyses_open": open_count,
        "analyses_closed": closed_count,
        "linked_actions": linked_action_count,
    }


def _build_champion_summary(
    df: pd.DataFrame,
    column_map: dict[str, str | None],
) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    champion_col = column_map.get("champion")
    status_col = column_map.get("status")
    due_col = column_map.get("due_date")
    closed_col = column_map.get("closed_at")

    if not champion_col:
        return pd.DataFrame(), ["Champion/owner column missing; unable to build rankings."]

    summary = df.groupby(champion_col, dropna=False).size().reset_index(name="total_actions")
    summary = summary.rename(columns={champion_col: "champion"})

    if status_col:
        status_values = _normalize_status(df[status_col])
        summary["open_actions"] = (status_values != "closed").groupby(df[champion_col]).sum().values
        summary["closed_actions"] = (status_values == "closed").groupby(df[champion_col]).sum().values
    else:
        warnings.append("Status column missing; open/closed KPIs unavailable.")

    if status_col and due_col:
        status_values = _normalize_status(df[status_col])
        summary["overdue_actions"] = (
            (status_values != "closed") & (df[due_col] < pd.Timestamp(date.today()))
        ).groupby(df[champion_col]).sum().values
    else:
        warnings.append("Status or due date column missing; overdue KPI unavailable.")

    if status_col and due_col and closed_col:
        status_values = _normalize_status(df[status_col])
        on_time = ((status_values == "closed") & (df[closed_col] <= df[due_col]))
        summary["on_time_actions"] = on_time.groupby(df[champion_col]).sum().values
        closed_counts = (status_values == "closed").groupby(df[champion_col]).sum().values
        summary["on_time_rate"] = [
            (on_time_count / closed_count) if closed_count > 0 else 0.0
            for on_time_count, closed_count in zip(summary["on_time_actions"], closed_counts)
        ]
    else:
        warnings.append("Status, due date, or closed date column missing; on-time KPI unavailable.")

    return summary, warnings


def _build_subtask_summary(
    df: pd.DataFrame, column_map: dict[str, str | None]
) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    champion_col = column_map.get("champion")
    status_col = column_map.get("status")
    due_col = column_map.get("due_date")
    closed_col = column_map.get("closed_at")
    closed_values = {"done", "closed"}

    if not champion_col:
        return pd.DataFrame(), ["Sub-task champion/owner column missing; unable to build sub-task rankings."]

    summary = df.groupby(champion_col, dropna=False).size().reset_index(name="total_subtasks")
    summary = summary.rename(columns={champion_col: "champion"})

    if status_col:
        closed_mask = _is_closed(df[status_col], closed_values)
        summary["open_subtasks"] = (~closed_mask).groupby(df[champion_col]).sum().values
        summary["closed_subtasks"] = closed_mask.groupby(df[champion_col]).sum().values
    else:
        warnings.append("Sub-task status column missing; open/closed KPIs unavailable.")

    if status_col and due_col:
        closed_mask = _is_closed(df[status_col], closed_values)
        summary["overdue_subtasks"] = (
            (~closed_mask) & (df[due_col] < pd.Timestamp(date.today()))
        ).groupby(df[champion_col]).sum().values
    else:
        warnings.append("Sub-task status or due date column missing; overdue KPI unavailable.")

    if status_col and due_col and closed_col:
        closed_mask = _is_closed(df[status_col], closed_values)
        on_time = closed_mask & (df[closed_col] <= df[due_col])
        summary["on_time_subtasks"] = on_time.groupby(df[champion_col]).sum().values
        closed_counts = closed_mask.groupby(df[champion_col]).sum().values
        summary["subtask_on_time_rate"] = [
            (on_time_count / closed_count) if closed_count > 0 else 0.0
            for on_time_count, closed_count in zip(summary["on_time_subtasks"], closed_counts)
        ]
    else:
        warnings.append("Sub-task status, due date, or closed date column missing; on-time KPI unavailable.")

    return summary, warnings


def _sort_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary

    summary = summary.copy()
    overdue_actions = summary.get("overdue_actions", pd.Series(0, index=summary.index)).fillna(0)
    overdue_subtasks = summary.get("overdue_subtasks", pd.Series(0, index=summary.index)).fillna(0)
    closed_actions = summary.get("closed_actions", pd.Series(0, index=summary.index)).fillna(0)
    closed_subtasks = summary.get("closed_subtasks", pd.Series(0, index=summary.index)).fillna(0)
    on_time_actions = summary.get("on_time_actions", pd.Series(0, index=summary.index)).fillna(0)
    on_time_subtasks = summary.get("on_time_subtasks", pd.Series(0, index=summary.index)).fillna(0)
    total_actions = summary.get("total_actions", pd.Series(0, index=summary.index)).fillna(0)
    total_subtasks = summary.get("total_subtasks", pd.Series(0, index=summary.index)).fillna(0)

    summary["total_overdue"] = overdue_actions + overdue_subtasks
    summary["total_items"] = total_actions + total_subtasks
    closed_total = closed_actions + closed_subtasks
    summary["combined_on_time_rate"] = [
        (on_time / closed) if closed > 0 else 0.0
        for on_time, closed in zip(on_time_actions + on_time_subtasks, closed_total)
    ]

    summary = summary.sort_values(
        by=["total_overdue", "combined_on_time_rate", "total_items"],
        ascending=[True, False, False],
    )
    summary = summary.drop(columns=["total_overdue", "combined_on_time_rate", "total_items"], errors="ignore")
    return summary


def _normalize_table_height(height: int | float | str | None) -> int | str | None:
    if height is None:
        return None
    if isinstance(height, float):
        height = int(height)
    if isinstance(height, int):
        return height if height > 0 else None
    if isinstance(height, str):
        if height in {"stretch", "content"}:
            return height
    raise ValueError("Height must be an int or one of {'stretch', 'content'}.")


def _render_data_table(df: pd.DataFrame, *, height: int | float | str | None = None) -> None:
    normalized_height = _normalize_table_height(height)
    common = {"use_container_width": True, "hide_index": True}
    if normalized_height is None:
        st.dataframe(df, **common)
    else:
        st.dataframe(df, height=normalized_height, **common)


def _render_action_table(df: pd.DataFrame, column_map: dict[str, str | None]) -> None:
    desired_columns = [
        _find_column(df.columns, ["id", "action_id"]),
        _find_column(df.columns, ["title", "action_title"]),
        column_map.get("champion"),
        column_map.get("status"),
        column_map.get("due_date"),
        column_map.get("closed_at"),
        column_map.get("created_at"),
        _find_column(df.columns, ["project_or_family", "project"]),
    ]
    selected = [col for col in desired_columns if col and col in df.columns]
    _render_data_table(df[selected] if selected else df)


def _render_analysis_table(df: pd.DataFrame) -> None:
    desired_columns = [
        _find_column(df.columns, ["analysis_id", "id"]),
        _find_column(df.columns, ["type", "analysis_type"]),
        _find_column(df.columns, ["title", "analysis_title"]),
        _find_column(df.columns, ["champion", "owner"]),
        _find_column(df.columns, ["status"]),
        _find_column(df.columns, ["created_at", "created"]),
        _find_column(df.columns, ["closed_at", "closed"]),
    ]
    selected = [col for col in desired_columns if col and col in df.columns]
    _render_data_table(df[selected] if selected else df)


def _render_kpi_metrics_row(
    metrics: list[tuple[str, str | int | float]],
    *,
    n_cols: int,
) -> None:
    if n_cols <= 0:
        return
    with st.container():
        columns = st.columns(n_cols)
        for index in range(n_cols):
            if index < len(metrics):
                label, value = metrics[index]
                columns[index].metric(label, value)
            else:
                columns[index].empty()


def render_champions_dashboard() -> None:
    init_db()
    inject_global_styles()

    page_header(
        "🏆 Champions",
        "Champion ranking and action outcome signals across the portfolio.",
    )
    st.divider()

    actions_df = list_actions()
    analyses_df = list_analyses()
    analysis_links_df = list_analysis_actions()
    champions_df = list_champions(active_only=True)
    subtasks_df = pd.DataFrame()
    subtasks_available = True
    subtask_load_warning: str | None = None
    try:
        subtasks_df = list_all_tasks()
    except Exception:
        subtasks_available = False
        subtask_load_warning = "Sub-tasks source not available; showing actions-only metrics."

    score_log_df = compute_score_log(actions_df, analyses_df, date.today())
    save_champion_score_log(score_log_df)
    ranking_df = compute_ranking(score_log_df, actions_df, analyses_df)

    if "champion_filter" not in st.session_state:
        st.session_state["champion_filter"] = ALL_CHAMPIONS_LABEL

    if actions_df.empty:
        main_col, side_col = st.columns([3, 1], gap="large")
        with main_col:
            st.warning("No actions found; add actions to see champion metrics.")
        with side_col:
            with st.expander("🔍 Filters", expanded=True):
                st.selectbox(
                    "Champion",
                    [ALL_CHAMPIONS_LABEL],
                    key="champion_filter",
                )
        footer("Action-to-Money Tracker • Champion performance needs clean action data.")
        return

    column_map = _prepare_actions(actions_df)
    champion_col = column_map.get("champion")

    if not champion_col:
        main_col, side_col = st.columns([3, 1], gap="large")
        with main_col:
            st.warning("Champion/owner column missing; unable to build rankings.")
            _render_data_table(actions_df)
        with side_col:
            with st.expander("🔍 Filters", expanded=True):
                st.selectbox(
                    "Champion",
                    [ALL_CHAMPIONS_LABEL],
                    key="champion_filter",
                )
        footer("Action-to-Money Tracker • Champion performance needs clean action data.")
        return

    actions_df[champion_col] = actions_df[champion_col].fillna("Unassigned")

    champion_options_set = set()
    if not champions_df.empty and "name_display" in champions_df.columns:
        champion_options_set.update(champions_df["name_display"].dropna().unique().tolist())
    if not actions_df.empty and champion_col:
        champion_options_set.update(actions_df[champion_col].dropna().unique().tolist())
    if not analyses_df.empty and "champion" in analyses_df.columns:
        champion_options_set.update(analyses_df["champion"].dropna().unique().tolist())
    if not ranking_df.empty and "champion" in ranking_df.columns:
        champion_options_set.update(ranking_df["champion"].dropna().unique().tolist())

    champion_options = sorted(champion_options_set)

    if st.session_state["champion_filter"] not in [ALL_CHAMPIONS_LABEL] + champion_options:
        st.session_state["champion_filter"] = ALL_CHAMPIONS_LABEL

    champion_selection = st.session_state["champion_filter"]

    if champion_selection != ALL_CHAMPIONS_LABEL:
        filtered_df = actions_df[actions_df[champion_col] == champion_selection].copy()
    else:
        filtered_df = actions_df.copy()

    metrics, metric_warnings = _build_metrics(filtered_df, column_map)
    analysis_metrics = _build_analysis_metrics(
        analyses_df,
        analysis_links_df,
        actions_df,
        champion_col,
        champion_selection,
    )
    subtask_metrics: dict[str, object] = {
        "total_subtasks": None,
        "open_subtasks": None,
        "closed_subtasks": None,
        "overdue_subtasks": None,
        "on_time_subtasks": None,
        "subtask_on_time_rate": None,
        "avg_subtask_time_to_close": None,
    }
    subtask_column_map: dict[str, str | None] = {}
    subtask_warnings: list[str] = []
    filtered_subtasks = pd.DataFrame()

    if subtasks_available:
        subtasks_df, subtask_column_map, prep_warnings = _prepare_subtasks(
            subtasks_df,
            actions_df,
            column_map,
            champions_df,
        )
        subtask_warnings.extend(prep_warnings)
        subtask_champion_col = subtask_column_map.get("champion")
        if subtask_champion_col:
            subtasks_df[subtask_champion_col] = subtasks_df[subtask_champion_col].fillna("Unassigned")
            if champion_selection != ALL_CHAMPIONS_LABEL:
                filtered_subtasks = subtasks_df[subtasks_df[subtask_champion_col] == champion_selection].copy()
            else:
                filtered_subtasks = subtasks_df.copy()
        else:
            filtered_subtasks = subtasks_df.copy()
        subtask_metrics, subtask_metric_warnings = _build_subtask_metrics(filtered_subtasks, subtask_column_map)
        subtask_warnings.extend(subtask_metric_warnings)

    on_time_rate = metrics.get("on_time_rate")
    on_time_display = f"{on_time_rate:.0%}" if isinstance(on_time_rate, (float, int)) else "N/A"
    subtask_on_time_rate = subtask_metrics.get("subtask_on_time_rate")
    subtask_on_time_display = (
        f"{subtask_on_time_rate:.0%}" if isinstance(subtask_on_time_rate, (float, int)) else "N/A"
    )

    main_col, side_col = st.columns([3, 1], gap="large")
    with main_col:
        _render_kpi_metrics_row(
            [
                ("Total actions", _format_metric(metrics["total_actions"])),
                ("Open actions", _format_metric(metrics["open_actions"])),
                ("Closed actions", _format_metric(metrics["closed_actions"])),
                ("Overdue actions", _format_metric(metrics["overdue_actions"])),
                ("On-time rate", on_time_display),
            ],
            n_cols=5,
        )
        _render_kpi_metrics_row(
            [
                ("Analyses open", _format_metric(analysis_metrics["analyses_open"])),
                ("Analyses closed", _format_metric(analysis_metrics["analyses_closed"])),
                ("Actions linked to analyses", _format_metric(analysis_metrics["linked_actions"])),
            ],
            n_cols=5,
        )
        st.markdown(muted("Sub-task KPIs"), unsafe_allow_html=True)
        _render_kpi_metrics_row(
            [
                ("Total sub-tasks", _format_metric(subtask_metrics["total_subtasks"])),
                ("Open sub-tasks", _format_metric(subtask_metrics["open_subtasks"])),
                ("Closed sub-tasks", _format_metric(subtask_metrics["closed_subtasks"])),
                ("Overdue sub-tasks", _format_metric(subtask_metrics["overdue_subtasks"])),
                ("On-time rate", subtask_on_time_display),
            ],
            n_cols=5,
        )
        st.divider()

        if subtask_load_warning:
            st.warning(subtask_load_warning)
        for warning in metric_warnings:
            st.warning(warning)
        for warning in subtask_warnings:
            st.warning(warning)

        st.markdown(
            muted("KPIs are derived from the actions and sub-task data used in the Actions module."),
            unsafe_allow_html=True,
        )

        section("Champion scoring (v1.0)")
        st.markdown(
            muted("Scores include action points, analysis points, and aging penalties with SLA-by-type."),
            unsafe_allow_html=True,
        )
        if ranking_df.empty:
            st.warning("No champion score data available yet.")
        else:
            _render_data_table(ranking_df)

        if champion_selection != ALL_CHAMPIONS_LABEL:
            section("Champion scoring details")
            champion_score_log = score_log_df[score_log_df["champion"] == champion_selection].copy()
            champion_total_score = int(champion_score_log["points"].sum()) if not champion_score_log.empty else 0
            champion_actions = filtered_df.copy()
            action_on_time_rate = _build_action_on_time_rate(champion_actions, column_map)
            champion_analyses = analyses_df.copy()
            if "champion" in champion_analyses.columns:
                champion_analyses = champion_analyses[champion_analyses["champion"] == champion_selection].copy()
            analyses_open = 0
            analyses_closed = 0
            if not champion_analyses.empty and "status" in champion_analyses.columns:
                status_values = champion_analyses["status"].astype(str).str.lower().str.strip()
                analyses_closed = int((status_values == "closed").sum())
                analyses_open = int((status_values != "closed").sum())

            score_kpis = st.columns(4)
            score_kpis[0].metric("Total score", champion_total_score)
            score_kpis[1].metric("Action on-time rate", _format_rate(action_on_time_rate))
            score_kpis[2].metric("Analyses closed", analyses_closed)
            score_kpis[3].metric("Analyses open", analyses_open)

            if champion_score_log.empty:
                st.info("No score events recorded yet for this champion.")
            else:
                _render_data_table(
                    champion_score_log[
                        [
                            "as_of_date",
                            "item_type",
                            "item_id",
                            "rule_code",
                            "points",
                            "details",
                        ]
                    ]
                )

            section("Champion analyses and linked actions")
            if champion_analyses.empty:
                st.info("No analyses found for this champion.")
            else:
                _render_analysis_table(champion_analyses)

            linked_actions = pd.DataFrame()
            if not champion_analyses.empty and not analysis_links_df.empty:
                analysis_ids = champion_analyses["analysis_id"].astype(str).tolist()
                linked = analysis_links_df[analysis_links_df["analysis_id"].astype(str).isin(analysis_ids)].copy()
                action_id_col = _find_column(actions_df.columns, ["id", "action_id", "actionid"])
                if action_id_col and not linked.empty:
                    linked_ids = linked["action_id"].astype(str).tolist()
                    linked_actions = actions_df[actions_df[action_id_col].astype(str).isin(linked_ids)].copy()

            if linked_actions.empty:
                st.info("No linked actions found for this champion's analyses.")
            else:
                _render_action_table(linked_actions, column_map)

            section("Action details")
            _render_action_table(filtered_df, column_map)
    with side_col:
        with st.expander("🔍 Filters", expanded=True):
            st.selectbox(
                "Champion",
                [ALL_CHAMPIONS_LABEL] + champion_options,
                key="champion_filter",
            )
        if metrics.get("avg_time_to_close") is not None:
            section("Cycle time")
            st.metric("Avg time to close (days)", f"{metrics['avg_time_to_close']:.1f}")
        if subtask_metrics.get("avg_subtask_time_to_close") is not None:
            section("Sub-task cycle time")
            st.metric(
                "Avg sub-task time to close (days)",
                f"{subtask_metrics['avg_subtask_time_to_close']:.1f}",
            )
    footer("Action-to-Money Tracker • Champion performance needs clean action data.")


__all__ = ["render_champions_dashboard"]
