from __future__ import annotations

from contextlib import contextmanager
import importlib.util
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from atm_tracker.actions.db import init_db
from atm_tracker.actions.repo import get_actions_days_late, list_actions
from atm_tracker.ui.layout import footer, kpi_row, main_grid, page_header
from atm_tracker.ui.styles import card, inject_global_styles, muted, pill


FILTER_KEYS = {
    "project": "analysis_filter_project",
    "champion": "analysis_filter_champion",
    "status": "analysis_filter_status",
    "search": "analysis_filter_search",
    "date_from": "analysis_filter_date_from",
    "date_to": "analysis_filter_date_to",
}


@contextmanager
def card_section(title: str, caption: str | None = None) -> Iterable[None]:
    st.markdown("<div class='ds-card'>", unsafe_allow_html=True)
    st.markdown(f"#### {title}")
    if caption:
        st.caption(caption)
    yield
    st.markdown("</div>", unsafe_allow_html=True)


def render_kpi_dashboard() -> None:
    init_db()
    inject_global_styles()

    export_available = True

    def _render_header_actions() -> None:
        col_left, col_right = st.columns(2)
        with col_left:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        if export_available:
            with col_right:
                if st.button("⬇️ Export", use_container_width=True):
                    st.session_state["analysis_export_open"] = True

    page_header(
        "🧠 Analysis",
        "Explore trends, drivers, and CAPA effectiveness.",
        actions=_render_header_actions,
    )
    st.divider()

    actions_df = list_actions()
    column_map = _find_action_columns(actions_df.columns)
    _initialize_filter_state(actions_df, column_map)
    filtered_df = _apply_filters(actions_df, column_map)
    _append_days_late(filtered_df)

    _render_kpi_row(filtered_df, column_map)
    st.divider()

    _render_filters(actions_df, column_map)
    st.divider()

    with main_grid("split") as (main, side):
        with main:
            if actions_df.empty:
                st.markdown(muted("📭 No data available for Analysis."), unsafe_allow_html=True)
            elif filtered_df.empty:
                st.markdown(
                    muted("📭 No results for current filters. Adjust filters or date range."),
                    unsafe_allow_html=True,
                )
            else:
                charts = _render_charts(filtered_df, column_map)
                if not charts:
                    st.markdown(muted("No chart-ready data available yet."), unsafe_allow_html=True)
        with side:
            _render_insights_panel(filtered_df, column_map)
            _render_export_panel(filtered_df, export_available)

    footer("Action-to-Money Tracker • Insight first, action second.")


def _find_action_columns(columns: Iterable[str]) -> dict[str, str | None]:
    return {
        "project": _find_column(columns, ["project_or_family", "project", "family"]),
        "champion": _find_column(columns, ["champion", "owner", "responsible"]),
        "status": _find_column(columns, ["status", "state"]),
        "created_at": _find_column(columns, ["created_at", "created", "date"]),
        "closed_at": _find_column(columns, ["closed_at", "closed", "done_at"]),
        "due_date": _find_column(columns, ["target_date", "due_date", "due"]),
        "title": _find_column(columns, ["title", "action_title", "name"]),
        "id": _find_column(columns, ["id", "action_id"]),
    }


def _find_column(columns: Iterable[str], candidates: list[str]) -> str | None:
    lower = {col.lower(): col for col in columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def _initialize_filter_state(actions_df: pd.DataFrame, column_map: dict[str, str | None]) -> None:
    project_col = column_map.get("project")
    champion_col = column_map.get("champion")
    status_col = column_map.get("status")

    if FILTER_KEYS["project"] not in st.session_state:
        st.session_state[FILTER_KEYS["project"]] = "All"
    if FILTER_KEYS["champion"] not in st.session_state:
        st.session_state[FILTER_KEYS["champion"]] = "All"
    if FILTER_KEYS["status"] not in st.session_state:
        st.session_state[FILTER_KEYS["status"]] = []
    if FILTER_KEYS["search"] not in st.session_state:
        st.session_state[FILTER_KEYS["search"]] = ""
    if FILTER_KEYS["date_from"] not in st.session_state:
        st.session_state[FILTER_KEYS["date_from"]] = None
    if FILTER_KEYS["date_to"] not in st.session_state:
        st.session_state[FILTER_KEYS["date_to"]] = None

    if project_col and project_col in actions_df.columns:
        options = actions_df[project_col].dropna().astype(str).tolist()
        if st.session_state[FILTER_KEYS["project"]] not in ["All"] + options:
            st.session_state[FILTER_KEYS["project"]] = "All"

    if champion_col and champion_col in actions_df.columns:
        options = actions_df[champion_col].dropna().astype(str).tolist()
        if st.session_state[FILTER_KEYS["champion"]] not in ["All"] + options:
            st.session_state[FILTER_KEYS["champion"]] = "All"

    if status_col and status_col in actions_df.columns:
        if not isinstance(st.session_state[FILTER_KEYS["status"]], list):
            st.session_state[FILTER_KEYS["status"]] = []


def _apply_filters(actions_df: pd.DataFrame, column_map: dict[str, str | None]) -> pd.DataFrame:
    filtered = actions_df.copy()

    project_col = column_map.get("project")
    champion_col = column_map.get("champion")
    status_col = column_map.get("status")
    title_col = column_map.get("title")
    id_col = column_map.get("id")

    selected_project = st.session_state.get(FILTER_KEYS["project"], "All")
    selected_champion = st.session_state.get(FILTER_KEYS["champion"], "All")
    selected_status = st.session_state.get(FILTER_KEYS["status"], [])
    search_text = st.session_state.get(FILTER_KEYS["search"], "")

    if selected_project != "All" and project_col:
        filtered = filtered[filtered[project_col] == selected_project]

    if selected_champion != "All" and champion_col:
        filtered = filtered[filtered[champion_col] == selected_champion]

    if selected_status and status_col:
        filtered = filtered[filtered[status_col].isin(selected_status)]

    if search_text and (title_col or id_col):
        search_lower = search_text.strip().lower()
        matches = pd.Series([False] * len(filtered), index=filtered.index)
        if id_col:
            matches = matches | filtered[id_col].astype(str).str.contains(search_lower, case=False, na=False)
        if title_col:
            matches = matches | filtered[title_col].astype(str).str.contains(search_lower, case=False, na=False)
        filtered = filtered[matches]

    date_col = _choose_date_column(column_map)
    if date_col and (FILTER_KEYS["date_from"] in st.session_state or FILTER_KEYS["date_to"] in st.session_state):
        date_from = st.session_state.get(FILTER_KEYS["date_from"])
        date_to = st.session_state.get(FILTER_KEYS["date_to"])
        date_series = pd.to_datetime(filtered[date_col], errors="coerce").dt.date
        if date_from:
            filtered = filtered[date_series >= date_from]
        if date_to:
            filtered = filtered[date_series <= date_to]

    return filtered


def _append_days_late(actions_df: pd.DataFrame) -> None:
    id_col = "id" if "id" in actions_df.columns else None
    if not id_col:
        return
    action_ids = [int(value) for value in actions_df[id_col].dropna().tolist() if str(value).isdigit()]
    if not action_ids:
        return
    days_late_map = get_actions_days_late(action_ids)
    actions_df["days_late"] = actions_df[id_col].map(lambda action_id: days_late_map.get(int(action_id), 0))


def _render_kpi_row(actions_df: pd.DataFrame, column_map: dict[str, str | None]) -> None:
    if actions_df.empty:
        kpi_row([])
        return

    status_col = column_map.get("status")
    closed_col = column_map.get("closed_at")

    items: list[tuple[str, str | int | float]] = []
    items.append(("Total actions", int(len(actions_df))))

    if status_col:
        status_values = _normalize_status(actions_df[status_col])
        items.append(("Open actions", int((status_values != "closed").sum())))
    if "days_late" in actions_df.columns:
        items.append(("Overdue actions", int((actions_df["days_late"] > 0).sum())))
    if "days_late" in actions_df.columns and closed_col:
        if status_col:
            closed_mask = _normalize_status(actions_df[status_col]) == "closed"
        else:
            closed_mask = actions_df[closed_col].notna()
        closed_count = int(closed_mask.sum())
        if closed_count:
            on_time_rate = (actions_df.loc[closed_mask, "days_late"] <= 0).sum() / closed_count
            items.append(("On-time close rate", f"{on_time_rate * 100:.0f}%"))

    kpi_row(items)


def _render_filters(actions_df: pd.DataFrame, column_map: dict[str, str | None]) -> None:
    project_col = column_map.get("project")
    champion_col = column_map.get("champion")
    status_col = column_map.get("status")
    title_col = column_map.get("title")
    id_col = column_map.get("id")

    date_col = _choose_date_column(column_map)

    with st.expander("🔍 Filters", expanded=True):
        filter_cols = st.columns(4)
        if project_col:
            project_options = sorted(actions_df[project_col].dropna().astype(str).unique().tolist())
            with filter_cols[0]:
                st.selectbox("Project", options=["All"] + project_options, key=FILTER_KEYS["project"])
        if champion_col:
            champion_options = sorted(actions_df[champion_col].dropna().astype(str).unique().tolist())
            with filter_cols[1]:
                st.selectbox("Champion", options=["All"] + champion_options, key=FILTER_KEYS["champion"])
        if status_col:
            status_options = sorted(actions_df[status_col].dropna().astype(str).unique().tolist())
            with filter_cols[2]:
                st.multiselect("Status", options=status_options, key=FILTER_KEYS["status"])
        if title_col or id_col:
            with filter_cols[3]:
                st.text_input(
                    "Search (ID or title)",
                    placeholder="e.g. 42 or coating defect",
                    key=FILTER_KEYS["search"],
                )

        if date_col:
            date_label = {
                "created_at": "Created",
                "closed_at": "Closed",
                "due_date": "Due",
            }.get(_normalize_date_key(column_map, date_col), "Date")
            date_cols = st.columns(2)
            with date_cols[0]:
                st.date_input(f"{date_label} from", value=None, key=FILTER_KEYS["date_from"])
            with date_cols[1]:
                st.date_input(f"{date_label} to", value=None, key=FILTER_KEYS["date_to"])


def _normalize_date_key(column_map: dict[str, str | None], date_col: str) -> str:
    for key, value in column_map.items():
        if value == date_col:
            return key
    return "date"


def _choose_date_column(column_map: dict[str, str | None]) -> str | None:
    return column_map.get("created_at") or column_map.get("due_date") or column_map.get("closed_at")


def _normalize_status(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower()


def _render_charts(actions_df: pd.DataFrame, column_map: dict[str, str | None]) -> dict[str, go.Figure]:
    charts: dict[str, go.Figure] = {}
    project_col = column_map.get("project")
    champion_col = column_map.get("champion")
    status_col = column_map.get("status")
    created_col = column_map.get("created_at")
    closed_col = column_map.get("closed_at")

    if project_col and "days_late" in actions_df.columns:
        overdue = actions_df[actions_df["days_late"] > 0]
        if not overdue.empty:
            grouped = overdue.groupby(project_col).size().sort_values(ascending=False)
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=grouped.index.astype(str),
                        y=grouped.values,
                        marker_color="#D97706",
                    )
                ]
            )
            fig.update_layout(
                height=320,
                margin=dict(l=20, r=20, t=10, b=20),
                xaxis_title="Project",
                yaxis_title="Overdue actions",
            )
            with card_section("Overdue actions by project", "Where are actions slipping the most?"):
                st.plotly_chart(fig, use_container_width=True)
            charts["Overdue actions by project"] = fig

    if created_col and closed_col:
        fig = _build_created_closed_chart(actions_df, created_col, closed_col)
        if fig is not None:
            with card_section("Actions created vs closed over time", "Are we closing as fast as we open?"):
                st.plotly_chart(fig, use_container_width=True)
            charts["Actions created vs closed over time"] = fig

    if champion_col and status_col:
        open_mask = _normalize_status(actions_df[status_col]) != "closed"
        open_df = actions_df[open_mask]
        if not open_df.empty:
            grouped = open_df.groupby(champion_col).size().sort_values(ascending=False)
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=grouped.index.astype(str),
                        y=grouped.values,
                        marker_color="#1F2937",
                    )
                ]
            )
            fig.update_layout(
                height=320,
                margin=dict(l=20, r=20, t=10, b=20),
                xaxis_title="Champion",
                yaxis_title="Open actions",
            )
            with card_section("Champion workload (open actions)", "Who is carrying the open workload?"):
                st.plotly_chart(fig, use_container_width=True)
            charts["Champion workload (open actions)"] = fig

    return charts


def _build_created_closed_chart(
    actions_df: pd.DataFrame,
    created_col: str,
    closed_col: str,
) -> go.Figure | None:
    created_series = pd.to_datetime(actions_df[created_col], errors="coerce").dropna()
    closed_series = pd.to_datetime(actions_df[closed_col], errors="coerce").dropna()
    if created_series.empty and closed_series.empty:
        return None

    min_date = min(
        filter(
            pd.notna,
            [
                created_series.min() if not created_series.empty else pd.NaT,
                closed_series.min() if not closed_series.empty else pd.NaT,
            ],
        )
    )
    max_date = max(
        filter(
            pd.notna,
            [
                created_series.max() if not created_series.empty else pd.NaT,
                closed_series.max() if not closed_series.empty else pd.NaT,
            ],
        )
    )
    if pd.isna(min_date) or pd.isna(max_date):
        return None

    timeline = pd.date_range(start=min_date, end=max_date, freq="W-MON")
    if timeline.empty:
        return None

    created_counts = created_series.dt.to_period("W").dt.start_time.value_counts().sort_index()
    closed_counts = closed_series.dt.to_period("W").dt.start_time.value_counts().sort_index()

    summary = pd.DataFrame({"week": timeline})
    summary["created"] = summary["week"].map(created_counts).fillna(0).astype(int)
    summary["closed"] = summary["week"].map(closed_counts).fillna(0).astype(int)
    summary["label"] = summary["week"].dt.strftime("%Y-%m-%d")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=summary["label"],
            y=summary["created"],
            mode="lines+markers",
            name="Created",
            line=dict(color="#2563EB"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summary["label"],
            y=summary["closed"],
            mode="lines+markers",
            name="Closed",
            line=dict(color="#16A34A"),
        )
    )
    fig.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=10, b=20),
        xaxis_title="Week",
        yaxis_title="Actions",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_yaxes(rangemode="tozero")
    return fig


def _render_insights_panel(actions_df: pd.DataFrame, column_map: dict[str, str | None]) -> None:
    insights = _build_insights(actions_df, column_map)
    if insights:
        with card_section("Insight", "Signals pulled from current filters."):
            st.markdown("\n\n".join(insights))

    legend_items = "".join(
        [
            f"<li>{pill('Open')} Open action</li>",
            f"<li>{pill('Closed')} Closed action</li>",
            f"<li>{pill('Overdue')} Overdue action</li>",
        ]
    )
    st.markdown(card(f"<h4>Legend</h4><ul class='ds-list'>{legend_items}</ul>"), unsafe_allow_html=True)

    breakdown_html = _build_breakdown_table(actions_df, column_map)
    if breakdown_html:
        st.markdown(card(breakdown_html), unsafe_allow_html=True)

    notes = """<h4>Notes / Interpretation</h4>
    <ul class='ds-list'>
        <li>Trends are directional; validate root causes before actioning.</li>
        <li>Use overdue clusters to prioritize coaching or unblockers.</li>
    </ul>
    """
    st.markdown(card(notes), unsafe_allow_html=True)


def _build_insights(actions_df: pd.DataFrame, column_map: dict[str, str | None]) -> list[str]:
    if actions_df.empty:
        return []

    insights: list[str] = []
    project_col = column_map.get("project")
    champion_col = column_map.get("champion")
    status_col = column_map.get("status")

    if project_col and "days_late" in actions_df.columns:
        overdue = actions_df[actions_df["days_late"] > 0]
        if not overdue.empty:
            grouped = overdue[project_col].fillna("Unassigned").astype(str).value_counts()
            top_project = grouped.index[0]
            share = grouped.iloc[0] / grouped.sum() * 100
            insights.append(f"⚠ {share:.0f}% of overdue actions are in {top_project}.")

    if champion_col and status_col:
        open_df = actions_df[_normalize_status(actions_df[status_col]) != "closed"]
        if not open_df.empty:
            grouped = open_df[champion_col].fillna("Unassigned").astype(str).value_counts()
            top_champion = grouped.index[0]
            insights.append(f"Top open-action champion: {top_champion} ({grouped.iloc[0]} actions).")

    return insights[:2]


def _build_breakdown_table(actions_df: pd.DataFrame, column_map: dict[str, str | None]) -> str | None:
    project_col = column_map.get("project")
    if not project_col or "days_late" not in actions_df.columns:
        return None

    overdue = actions_df[actions_df["days_late"] > 0]
    if overdue.empty:
        return None

    grouped = overdue.groupby(project_col).size().sort_values(ascending=False).head(5)
    rows = "".join(
        f"<tr><td>{project}</td><td>{count}</td></tr>" for project, count in grouped.items()
    )
    return (
        "<h4>Top overdue projects</h4>"
        "<table class='ds-table'><thead><tr><th>Project</th><th>Overdue</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _render_export_panel(actions_df: pd.DataFrame, export_available: bool) -> None:
    if not export_available:
        return

    with st.expander("⬇️ Export", expanded=st.session_state.get("analysis_export_open", False)):
        if actions_df.empty:
            st.caption("No data available to export.")
            return

        export_df = actions_df.copy()
        st.download_button(
            "Download filtered actions (CSV)",
            export_df.to_csv(index=False),
            file_name="analysis_actions_filtered.csv",
            mime="text/csv",
        )

        if not _png_export_available():
            st.caption("Chart PNG export unavailable (install kaleido to enable).")


def _png_export_available() -> bool:
    return importlib.util.find_spec("kaleido") is not None


__all__ = ["render_kpi_dashboard"]
