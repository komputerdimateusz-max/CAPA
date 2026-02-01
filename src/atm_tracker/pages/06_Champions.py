from __future__ import annotations

from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ALL_CHAMPIONS_LABEL = "All champions"


def _normalize_column_name(value: str) -> str:
    return "".join(value.lower().replace(" ", "").replace("_", "").split())


def _find_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized = {_normalize_column_name(col): col for col in columns}
    for candidate in candidates:
        key = _normalize_column_name(candidate)
        if key in normalized:
            return normalized[key]
    return None


def _load_actions_csv() -> pd.DataFrame:
    root_dir = Path(__file__).resolve().parents[3]
    csv_path = root_dir / "data" / "actions.csv"
    if not csv_path.exists():
        st.warning("Missing data/actions.csv; please add the actions export.")
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def _prepare_actions(df: pd.DataFrame) -> dict[str, str | None]:
    column_map = {
        "champion": _find_column(df.columns.tolist(), ["champion", "owner"]),
        "status": _find_column(df.columns.tolist(), ["status"]),
        "due_date": _find_column(df.columns.tolist(), ["due_date", "due"]),
        "closed_at": _find_column(df.columns.tolist(), ["closed_at", "closed_date"]),
        "created_at": _find_column(df.columns.tolist(), ["created_at", "date"]),
    }

    for key in ("due_date", "closed_at", "created_at"):
        col = column_map[key]
        if col:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return column_map


def _normalize_status(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower()


def _build_metrics(df: pd.DataFrame, column_map: dict[str, str | None]) -> dict[str, int | float | str]:
    status_col = column_map.get("status")
    due_col = column_map.get("due_date")
    closed_col = column_map.get("closed_at")
    created_col = column_map.get("created_at")

    total_actions = len(df)

    if status_col:
        status_values = _normalize_status(df[status_col])
        open_actions = (status_values != "closed").sum()
        closed_actions = (status_values == "closed").sum()
    else:
        open_actions = "N/A"
        closed_actions = "N/A"

    if status_col and due_col:
        status_values = _normalize_status(df[status_col])
        overdue_actions = ((status_values != "closed") & (df[due_col] < pd.Timestamp(date.today()))).sum()
    else:
        overdue_actions = "N/A"

    if status_col and due_col and closed_col:
        status_values = _normalize_status(df[status_col])
        on_time_actions = ((status_values == "closed") & (df[closed_col] <= df[due_col])).sum()
    else:
        on_time_actions = "N/A"

    if created_col and closed_col:
        time_to_close = (df[closed_col] - df[created_col]).dt.days
        avg_time_to_close = round(time_to_close.dropna().mean(), 1) if not time_to_close.dropna().empty else 0
    else:
        avg_time_to_close = "N/A"

    return {
        "total_actions": total_actions,
        "open_actions": open_actions,
        "closed_actions": closed_actions,
        "overdue_actions": overdue_actions,
        "on_time_actions": on_time_actions,
        "avg_time_to_close": avg_time_to_close,
    }


def _render_metrics(metrics: dict[str, int | float | str]) -> None:
    columns = st.columns(5)
    columns[0].metric("Total actions", metrics["total_actions"])
    columns[1].metric("Open actions", metrics["open_actions"])
    columns[2].metric("Closed actions", metrics["closed_actions"])
    columns[3].metric("Overdue actions", metrics["overdue_actions"])
    columns[4].metric("On-time close", metrics["on_time_actions"])

    if metrics["avg_time_to_close"] != "N/A":
        st.metric("Avg time to close (days)", metrics["avg_time_to_close"])


def _render_ranking_chart(df: pd.DataFrame, champion_col: str) -> None:
    summary = df.groupby(champion_col, dropna=False).size().reset_index(name="total_actions")
    summary = summary.sort_values(by="total_actions", ascending=False)

    chart = (
        alt.Chart(summary)
        .mark_bar()
        .encode(
            x=alt.X("total_actions:Q", title="Total actions"),
            y=alt.Y(f"{champion_col}:N", sort="-x", title="Champion"),
            tooltip=[champion_col, "total_actions"],
        )
        .properties(height=400)
    )

    st.altair_chart(chart, use_container_width=True)


def _render_on_time_chart(metrics: dict[str, int | float | str]) -> None:
    if metrics["overdue_actions"] == "N/A" or metrics["on_time_actions"] == "N/A":
        st.warning("Overdue/on-time breakdown requires status, due date, and closed date columns.")
        return

    chart_data = pd.DataFrame(
        {
            "status_group": ["On-time", "Overdue"],
            "count": [metrics["on_time_actions"], metrics["overdue_actions"]],
        }
    )

    chart = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            x=alt.X("status_group:N", title="Outcome"),
            y=alt.Y("count:Q", title="Actions"),
            tooltip=["status_group", "count"],
        )
        .properties(height=250)
    )

    st.altair_chart(chart, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="🏆 Champions", layout="wide")
    st.title("🏆 Champions")

    df = _load_actions_csv()
    if df.empty:
        return

    column_map = _prepare_actions(df)
    champion_col = column_map.get("champion")

    if not champion_col:
        st.warning("Champion/owner column missing; unable to build rankings.")
        st.dataframe(df)
        return

    df[champion_col] = df[champion_col].fillna("Unassigned")

    champions = sorted(df[champion_col].dropna().unique().tolist())
    champion_selection = st.selectbox("Champion", [ALL_CHAMPIONS_LABEL] + champions)

    if champion_selection != ALL_CHAMPIONS_LABEL:
        filtered_df = df[df[champion_col] == champion_selection].copy()
    else:
        filtered_df = df.copy()

    metrics = _build_metrics(filtered_df, column_map)
    _render_metrics(metrics)

    st.subheader("Champion ranking")
    _render_ranking_chart(filtered_df, champion_col)

    if champion_selection != ALL_CHAMPIONS_LABEL:
        st.subheader("On-time vs overdue")
        _render_on_time_chart(metrics)
        st.subheader("Action details")
        st.dataframe(filtered_df)
    else:
        st.subheader("Champion summary")
        summary = filtered_df.groupby(champion_col, dropna=False).size().reset_index(name="total_actions")
        summary = summary.sort_values(by="total_actions", ascending=False)
        st.dataframe(summary)


if __name__ == "__main__":
    main()
