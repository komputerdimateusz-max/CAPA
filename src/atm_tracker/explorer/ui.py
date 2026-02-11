from __future__ import annotations

import pandas as pd
import streamlit as st

from atm_tracker.actions.db import init_db
from atm_tracker.actions.repo import list_actions
from atm_tracker.analyses.repo import list_analyses
from atm_tracker.ui.layout import footer, page_header, section
from atm_tracker.ui.shared_tables import render_table_card
from atm_tracker.ui.styles import inject_global_styles, muted, pill


def render_explorer_module() -> None:
    init_db()
    inject_global_styles()

    page_header("🧭 Explorer", "Unified data explorer for actions and analyses.")

    dataset = st.selectbox("Dataset", ["Actions", "Analyses"], key="explorer_dataset")
    search = st.text_input("Search", placeholder="Search id, title, champion, project...", key="explorer_search")

    if dataset == "Actions":
        df = list_actions()
        _render_dataset(df, ["id", "title", "status", "champion", "project_or_family", "target_date"])
    else:
        df = list_analyses()
        _render_dataset(df, ["analysis_id", "title", "type", "status", "champion", "created_at"])

    if search:
        _ = search
    footer("Action-to-Money Tracker • Explore context before making decisions.")


def _render_dataset(df: pd.DataFrame, preferred_columns: list[str]) -> None:
    if df.empty:
        st.markdown(muted("📭 No data available."), unsafe_allow_html=True)
        return

    query = st.session_state.get("explorer_search", "").strip().lower()
    filtered_df = df.copy()
    if query:
        matches = pd.Series([False] * len(filtered_df), index=filtered_df.index)
        for col in filtered_df.columns:
            matches = matches | filtered_df[col].astype(str).str.lower().str.contains(query, na=False)
        filtered_df = filtered_df[matches]

    if filtered_df.empty:
        st.markdown(muted("📭 No rows match your search."), unsafe_allow_html=True)
        return

    section("Results")
    columns = [col for col in preferred_columns if col in filtered_df.columns]
    if not columns:
        columns = filtered_df.columns.tolist()[:6]

    headers = [col.replace("_", " ").title() for col in columns]
    rows: list[list[str]] = []
    for _, row in filtered_df[columns].head(100).iterrows():
        current_row: list[str] = []
        for col in columns:
            value = row.get(col)
            if col == "status":
                current_row.append(pill(str(value or "Open")))
            else:
                current_row.append("—" if pd.isna(value) else str(value))
        rows.append(current_row)

    render_table_card(headers, rows)
    st.caption(f"Showing {len(filtered_df)} rows")
