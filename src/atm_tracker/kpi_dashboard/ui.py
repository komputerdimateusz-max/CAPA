from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import importlib.util
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from atm_tracker.actions.db import init_db
from atm_tracker.actions.repo import get_actions_days_late, list_actions
from atm_tracker.analyses.repo import list_analyses
from atm_tracker.ui.layout import footer, kpi_row, main_grid, page_header, section
from atm_tracker.ui.styles import inject_global_styles, muted


@dataclass(frozen=True)
class WeeklyMetric:
    name: str
    label: str
    target_key: str | None = None


TARGET_KEYS = {
    "open_actions": "target_open_actions",
    "closed_actions": "target_closed_actions",
    "open_analysis": "target_open_analysis",
    "closed_analysis": "target_closed_analysis",
}


def to_week_index(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    if date_col not in df.columns:
        return df
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.date
    iso = pd.to_datetime(df[date_col], errors="coerce").dt.isocalendar()
    df["iso_year"] = iso["year"].astype("Int64")
    df["iso_week"] = iso["week"].astype("Int64")
    df["week_label"] = "CW" + iso["week"].astype(str)
    df["week_start_date"] = df.apply(
        lambda row: _week_start_date(row.get("iso_year"), row.get("iso_week")), axis=1
    )
    return df


def build_weekly_series(
    df: pd.DataFrame,
    date_col: str,
    *,
    all_weeks: pd.DataFrame,
    value_name: str,
    mask: pd.Series | None = None,
) -> pd.DataFrame:
    if df.empty or date_col not in df.columns or all_weeks.empty:
        return _empty_weekly_series(all_weeks, value_name)

    working = df.copy()
    if mask is not None:
        working = working[mask]
    if working.empty:
        return _empty_weekly_series(all_weeks, value_name)

    working = to_week_index(working, date_col)
    working = working.dropna(subset=["iso_year", "iso_week"])
    if working.empty:
        return _empty_weekly_series(all_weeks, value_name)

    grouped = (
        working.groupby(["iso_year", "iso_week"], dropna=False)
        .size()
        .reset_index(name=value_name)
    )
    merged = all_weeks.merge(grouped, on=["iso_year", "iso_week"], how="left")
    merged[value_name] = merged[value_name].fillna(0).astype(int)
    return merged


def build_dashboard_dataset(
    actions_df: pd.DataFrame,
    analyses_df: pd.DataFrame,
    *,
    warnings: list[str],
) -> pd.DataFrame:
    start_date = _min_date(actions_df, analyses_df, warnings=warnings)
    end_date = _max_end_date(actions_df, analyses_df)
    if not start_date or not end_date:
        return pd.DataFrame()

    all_weeks = _build_week_index(start_date, end_date)
    if all_weeks.empty:
        return pd.DataFrame()

    actions_status = _normalized_status(actions_df.get("status"))
    analyses_status = _normalized_status(analyses_df.get("status"))
    open_actions_mask = actions_status != "closed" if actions_status is not None else None
    closed_actions_mask = actions_status == "closed" if actions_status is not None else None
    open_analysis_mask = analyses_status != "closed" if analyses_status is not None else None
    closed_analysis_mask = analyses_status == "closed" if analyses_status is not None else None

    if actions_status is None:
        warnings.append("Actions status column missing; open/closed action series unavailable.")
    if analyses_status is None:
        warnings.append("Analysis status column missing; open/closed analysis series unavailable.")

    open_actions = build_weekly_series(
        actions_df,
        "created_at",
        all_weeks=all_weeks,
        value_name="open_actions",
        mask=open_actions_mask,
    )
    closed_actions = build_weekly_series(
        actions_df,
        "closed_at",
        all_weeks=all_weeks,
        value_name="closed_actions",
        mask=closed_actions_mask,
    )
    open_analysis = build_weekly_series(
        analyses_df,
        "created_at",
        all_weeks=all_weeks,
        value_name="open_analysis",
        mask=open_analysis_mask,
    )
    closed_analysis = build_weekly_series(
        analyses_df,
        "closed_at",
        all_weeks=all_weeks,
        value_name="closed_analysis",
        mask=closed_analysis_mask,
    )

    champion_col = _find_column(actions_df.columns, ["champion", "owner"])
    champions_mask: pd.Series | None = None
    if champion_col and actions_status is not None:
        champions_mask = open_actions_mask & actions_df[champion_col].fillna("").astype(str).ne("")
    else:
        warnings.append("Champion column missing; champion open actions series unavailable.")

    champions_open = build_weekly_series(
        actions_df,
        "created_at",
        all_weeks=all_weeks,
        value_name="champions_open_actions",
        mask=champions_mask,
    )

    dataset = all_weeks.copy()
    for frame in [open_actions, closed_actions, open_analysis, closed_analysis, champions_open]:
        dataset = dataset.merge(
            frame[["iso_year", "iso_week", frame.columns[-1]]],
            on=["iso_year", "iso_week"],
            how="left",
        )

    for col in [
        "open_actions",
        "closed_actions",
        "open_analysis",
        "closed_analysis",
        "champions_open_actions",
    ]:
        if col not in dataset.columns:
            dataset[col] = 0
    dataset[
        [
            "open_actions",
            "closed_actions",
            "open_analysis",
            "closed_analysis",
            "champions_open_actions",
        ]
    ] = dataset[
        [
            "open_actions",
            "closed_actions",
            "open_analysis",
            "closed_analysis",
            "champions_open_actions",
        ]
    ].fillna(0)
    return dataset


def render_kpi_dashboard() -> None:
    init_db()
    inject_global_styles()

    page_header(
        "📊 KPI Dashboard",
        "Weekly signals across actions, analyses, and champions (read-only).",
    )
    view = st.radio(
        "View",
        ["Both", "Actions", "Analysis"],
        horizontal=True,
        key="kpi_dashboard_view",
    )
    st.divider()

    actions_df = list_actions()
    analyses_df = list_analyses()
    warnings: list[str] = []
    dataset = build_dashboard_dataset(actions_df, analyses_df, warnings=warnings)

    totals = _build_totals(actions_df, analyses_df, warnings=warnings)
    _render_kpi_tiles(view, totals)
    st.divider()

    targets = _render_targets_expander()

    charts: dict[str, go.Figure] = {}
    if dataset.empty:
        st.info("No KPI time series available yet.")
    else:
        week_order = dataset["week_label"].tolist()

        if view in ("Both", "Actions"):
            section("Actions throughput")
            actions_fig = _build_chart(
                dataset,
                week_order,
                [
                    WeeklyMetric("open_actions", "Open actions", TARGET_KEYS["open_actions"]),
                    WeeklyMetric("closed_actions", "Closed actions", TARGET_KEYS["closed_actions"]),
                ],
                targets,
                y_title="Actions",
            )
            st.plotly_chart(actions_fig, use_container_width=True)
            charts["Actions throughput"] = actions_fig

            section("Champions with open actions")
            champions_fig = _build_chart(
                dataset,
                week_order,
                [WeeklyMetric("champions_open_actions", "Open actions with champions")],
                targets,
                y_title="Open actions",
            )
            st.plotly_chart(champions_fig, use_container_width=True)
            charts["Champions open actions"] = champions_fig

        if view in ("Both", "Analysis"):
            section("Analysis throughput")
            analysis_fig = _build_chart(
                dataset,
                week_order,
                [
                    WeeklyMetric("open_analysis", "Open analyses", TARGET_KEYS["open_analysis"]),
                    WeeklyMetric("closed_analysis", "Closed analyses", TARGET_KEYS["closed_analysis"]),
                ],
                targets,
                y_title="Analyses",
            )
            st.plotly_chart(analysis_fig, use_container_width=True)
            charts["Analysis throughput"] = analysis_fig

    if warnings:
        for warning in warnings:
            st.warning(warning)

    with st.expander("Export", expanded=False):
        if dataset.empty:
            st.info("No data to export yet.")
        else:
            export_df = dataset[
                [
                    "week_label",
                    "week_start_date",
                    "open_actions",
                    "closed_actions",
                    "open_analysis",
                    "closed_analysis",
                    "champions_open_actions",
                ]
            ].copy()
            st.download_button(
                "Download weekly KPI data (CSV)",
                export_df.to_csv(index=False),
                file_name="kpi_weekly_summary.csv",
                mime="text/csv",
            )

        if not charts:
            st.caption("Chart export available when charts are visible.")
        elif not _png_export_available():
            st.caption("Chart PNG export unavailable (install kaleido to enable).")
        else:
            chart_name = st.selectbox("Select chart", list(charts.keys()))
            fig = charts.get(chart_name)
            if fig:
                png_bytes = fig.to_image(format="png")
                st.download_button(
                    "Download chart image (PNG)",
                    png_bytes,
                    file_name=f"{chart_name.lower().replace(' ', '_')}.png",
                    mime="image/png",
                )

    footer("Action-to-Money Tracker • Weekly KPIs are directional, not ROI.")


def _render_kpi_tiles(view: str, totals: dict[str, int]) -> None:
    tiles: list[tuple[str, int]] = []
    if view in ("Both", "Actions"):
        tiles.extend(
            [
                ("Total open actions", totals.get("open_actions", 0)),
                ("Total overdue actions", totals.get("overdue_actions", 0)),
                ("Total closed actions", totals.get("closed_actions", 0)),
                ("Champions with open actions", totals.get("champions_open", 0)),
            ]
        )
    if view in ("Both", "Analysis"):
        tiles.extend(
            [
                ("Total open analysis", totals.get("open_analysis", 0)),
                ("Total closed analysis", totals.get("closed_analysis", 0)),
            ]
        )
    kpi_row(tiles)


def _build_totals(
    actions_df: pd.DataFrame,
    analyses_df: pd.DataFrame,
    *,
    warnings: list[str],
) -> dict[str, int]:
    totals: dict[str, int] = {
        "open_actions": 0,
        "closed_actions": 0,
        "overdue_actions": 0,
        "open_analysis": 0,
        "closed_analysis": 0,
        "champions_open": 0,
    }

    actions_status = _normalized_status(actions_df.get("status"))
    if actions_status is None:
        warnings.append("Actions status column missing; open/closed totals unavailable.")
    else:
        totals["open_actions"] = int((actions_status != "closed").sum())
        totals["closed_actions"] = int((actions_status == "closed").sum())

    analyses_status = _normalized_status(analyses_df.get("status"))
    if analyses_status is None:
        warnings.append("Analysis status column missing; open/closed totals unavailable.")
    else:
        totals["open_analysis"] = int((analyses_status != "closed").sum())
        totals["closed_analysis"] = int((analyses_status == "closed").sum())

    if not actions_df.empty:
        totals["overdue_actions"] = _compute_overdue_actions(actions_df, actions_status, warnings)
        totals["champions_open"] = _compute_champions_open(actions_df, actions_status, warnings)

    return totals


def _compute_overdue_actions(
    actions_df: pd.DataFrame,
    actions_status: pd.Series | None,
    warnings: list[str],
) -> int:
    if actions_status is None:
        return 0
    if "id" in actions_df.columns:
        action_ids = [int(value) for value in actions_df["id"].dropna().tolist() if str(value).isdigit()]
        days_late = get_actions_days_late(action_ids)
        if not action_ids:
            return 0
        return int(sum(1 for value in action_ids if days_late.get(int(value), 0) > 0))

    due_col = _find_column(actions_df.columns, ["target_date", "due_date"])
    if due_col:
        due_dates = pd.to_datetime(actions_df[due_col], errors="coerce").dt.date
        return int(((due_dates < date.today()) & (actions_status != "closed")).sum())

    warnings.append("Due date column missing; overdue actions unavailable.")
    return 0


def _compute_champions_open(
    actions_df: pd.DataFrame,
    actions_status: pd.Series | None,
    warnings: list[str],
) -> int:
    champion_col = _find_column(actions_df.columns, ["champion", "owner"])
    if actions_status is None:
        return 0
    if not champion_col:
        warnings.append("Champion column missing; champions with open actions unavailable.")
        return 0
    open_mask = actions_status != "closed"
    champions = actions_df.loc[open_mask, champion_col].fillna("").astype(str)
    return int(champions[champions.str.strip().ne("")].nunique())


def _render_targets_expander() -> dict[str, float | None]:
    targets: dict[str, float | None] = {}
    if "kpi_targets" not in st.session_state:
        st.session_state["kpi_targets"] = {
            key: None for key in TARGET_KEYS.values()
        }

    with st.expander("Targets", expanded=False):
        st.caption("Optional weekly targets (session-only).")
        for label, key in [
            ("Open actions weekly target", TARGET_KEYS["open_actions"]),
            ("Closed actions weekly target", TARGET_KEYS["closed_actions"]),
            ("Open analysis weekly target", TARGET_KEYS["open_analysis"]),
            ("Closed analysis weekly target", TARGET_KEYS["closed_analysis"]),
        ]:
            enabled_key = f"{key}_enabled"
            current_value = st.session_state["kpi_targets"].get(key)
            if enabled_key not in st.session_state:
                st.session_state[enabled_key] = current_value is not None

            enabled = st.checkbox(label, key=enabled_key)
            if enabled:
                default_value = 0.0 if current_value is None else float(current_value)
                value = st.number_input(
                    "Target value",
                    min_value=0.0,
                    step=1.0,
                    value=default_value,
                    key=key,
                )
                targets[key] = float(value)
                st.session_state["kpi_targets"][key] = float(value)
            else:
                targets[key] = None
                st.session_state["kpi_targets"][key] = None

    return targets


def _build_chart(
    dataset: pd.DataFrame,
    week_order: Iterable[str],
    metrics: list[WeeklyMetric],
    targets: dict[str, float | None],
    *,
    y_title: str,
) -> go.Figure:
    fig = go.Figure()
    for metric in metrics:
        if metric.name not in dataset.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=dataset["week_label"],
                y=dataset[metric.name],
                mode="lines+markers",
                name=metric.label,
                hovertemplate=f"Week %{{x}}<br>{metric.label}: %{{y}}<extra></extra>",
            )
        )
        if metric.target_key and targets.get(metric.target_key) is not None:
            target_value = float(targets[metric.target_key] or 0)
            fig.add_trace(
                go.Scatter(
                    x=dataset["week_label"],
                    y=[target_value] * len(dataset),
                    mode="lines",
                    name=f"{metric.label} target",
                    line=dict(dash="dash"),
                    hovertemplate=f"Week %{{x}}<br>{metric.label} target: {target_value}<extra></extra>",
                )
            )

    fig.update_layout(
        height=360,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(
        title=None,
        type="category",
        categoryorder="array",
        categoryarray=list(week_order),
    )
    fig.update_yaxes(title=y_title, rangemode="tozero")
    return fig


def _min_date(
    actions_df: pd.DataFrame,
    analyses_df: pd.DataFrame,
    *,
    warnings: list[str],
) -> date | None:
    dates: list[date] = []
    for df, name in [(actions_df, "actions"), (analyses_df, "analyses")]:
        if "created_at" not in df.columns:
            warnings.append(f"{name.title()} created_at column missing; timeline start may be incomplete.")
            continue
        series = pd.to_datetime(df["created_at"], errors="coerce").dt.date
        series = series.dropna()
        if not series.empty:
            dates.append(series.min())
    if not dates:
        return None
    return min(dates)


def _max_end_date(actions_df: pd.DataFrame, analyses_df: pd.DataFrame) -> date | None:
    today = date.today()
    dates: list[date] = [today]
    for df in [actions_df, analyses_df]:
        if "closed_at" in df.columns:
            series = pd.to_datetime(df["closed_at"], errors="coerce").dt.date
            series = series.dropna()
            if not series.empty:
                dates.append(series.max())
    return max(dates) if dates else None


def _build_week_index(start_date: date, end_date: date) -> pd.DataFrame:
    start_monday = start_date - timedelta(days=start_date.weekday())
    end_monday = end_date - timedelta(days=end_date.weekday())
    week_starts = pd.date_range(start=start_monday, end=end_monday, freq="W-MON").date
    if len(week_starts) == 0:
        return pd.DataFrame()
    df = pd.DataFrame({"week_start_date": week_starts})
    iso = pd.to_datetime(df["week_start_date"]).dt.isocalendar()
    df["iso_year"] = iso["year"].astype(int)
    df["iso_week"] = iso["week"].astype(int)
    df["week_label"] = "CW" + df["iso_week"].astype(str)
    return df


def _week_start_date(year: int | None, week: int | None) -> date | None:
    if not year or not week:
        return None
    try:
        return date.fromisocalendar(int(year), int(week), 1)
    except ValueError:
        return None


def _empty_weekly_series(all_weeks: pd.DataFrame, value_name: str) -> pd.DataFrame:
    if all_weeks.empty:
        return pd.DataFrame(columns=["iso_year", "iso_week", value_name])
    df = all_weeks[["iso_year", "iso_week"]].copy()
    df[value_name] = 0
    return df


def _normalized_status(series: pd.Series | None) -> pd.Series | None:
    if series is None:
        return None
    return series.astype(str).str.strip().str.lower()


def _find_column(columns: Iterable[str], candidates: list[str]) -> str | None:
    lower = {col.lower(): col for col in columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def _png_export_available() -> bool:
    return importlib.util.find_spec("kaleido") is not None


__all__ = [
    "render_kpi_dashboard",
    "to_week_index",
    "build_weekly_series",
    "build_dashboard_dataset",
]
