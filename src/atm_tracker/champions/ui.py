from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd
import streamlit as st

from atm_tracker.actions.db import init_db
from atm_tracker.actions.repo import list_actions
from atm_tracker.champions.repo import list_champions
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


def _render_metrics(metrics: dict[str, object]) -> None:
    columns = st.columns(5)
    columns[0].metric("Total actions", _format_metric(metrics["total_actions"]))
    columns[1].metric("Open actions", _format_metric(metrics["open_actions"]))
    columns[2].metric("Closed actions", _format_metric(metrics["closed_actions"]))
    columns[3].metric("Overdue actions", _format_metric(metrics["overdue_actions"]))

    on_time_rate = metrics.get("on_time_rate")
    if isinstance(on_time_rate, (float, int)):
        on_time_display = f"{on_time_rate:.0%}"
    else:
        on_time_display = "N/A"
    columns[4].metric("On-time rate", on_time_display)

    if metrics.get("avg_time_to_close") is not None:
        st.metric("Avg time to close (days)", f"{metrics['avg_time_to_close']:.1f}")


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


def _sort_summary(summary: pd.DataFrame) -> pd.DataFrame:
    sort_columns: list[str] = []
    ascending: list[bool] = []

    if "overdue_actions" in summary.columns:
        sort_columns.append("overdue_actions")
        ascending.append(True)
    if "on_time_rate" in summary.columns:
        sort_columns.append("on_time_rate")
        ascending.append(False)
    if "total_actions" in summary.columns:
        sort_columns.append("total_actions")
        ascending.append(False)

    if sort_columns:
        summary = summary.sort_values(by=sort_columns, ascending=ascending)
    return summary


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
    st.dataframe(df[selected] if selected else df)


def render_champions_dashboard() -> None:
    init_db()
    inject_global_styles()

    st.title("🏆 Champions")
    st.caption("Champion ranking and action outcome signals across the portfolio.")
    st.markdown(muted("KPIs are derived from the same actions data used in the Actions module."), unsafe_allow_html=True)

    actions_df = list_actions()
    champions_df = list_champions(active_only=True)

    if actions_df.empty:
        st.warning("No actions found; add actions to see champion metrics.")
        return

    column_map = _prepare_actions(actions_df)
    champion_col = column_map.get("champion")

    if not champion_col:
        st.warning("Champion/owner column missing; unable to build rankings.")
        st.dataframe(actions_df)
        return

    actions_df[champion_col] = actions_df[champion_col].fillna("Unassigned")

    if not champions_df.empty and "name_display" in champions_df.columns:
        champion_options = sorted(champions_df["name_display"].dropna().unique().tolist())
    else:
        champion_options = sorted(actions_df[champion_col].dropna().unique().tolist())

    champion_selection = st.selectbox("Champion", [ALL_CHAMPIONS_LABEL] + champion_options)

    if champion_selection != ALL_CHAMPIONS_LABEL:
        filtered_df = actions_df[actions_df[champion_col] == champion_selection].copy()
    else:
        filtered_df = actions_df.copy()

    metrics, metric_warnings = _build_metrics(filtered_df, column_map)
    for warning in metric_warnings:
        st.warning(warning)

    _render_metrics(metrics)

    st.markdown("### Champion ranking")
    summary, summary_warnings = _build_champion_summary(actions_df, column_map)
    for warning in summary_warnings:
        st.warning(warning)

    if summary.empty:
        return

    summary = _sort_summary(summary)
    st.dataframe(summary, use_container_width=True)

    if champion_selection != ALL_CHAMPIONS_LABEL:
        st.markdown("### Action details")
        _render_action_table(filtered_df, column_map)


__all__ = ["render_champions_dashboard"]
