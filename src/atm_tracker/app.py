from __future__ import annotations

import sys
from pathlib import Path

# Ensure "src" is on PYTHONPATH when running via:
# streamlit run src/atm_tracker/app.py
SRC_DIR = Path(__file__).resolve().parents[1]  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st  # noqa: E402

from atm_tracker.actions.ui import render_actions_module  # noqa: E402
from atm_tracker.analyses.ui import render_analyses_module  # noqa: E402
from atm_tracker.champions.ui import render_champions_dashboard  # noqa: E402
from atm_tracker.settings.ui import render_global_settings  # noqa: E402


NAV_OPTIONS = ["Actions", "Analyses", "Champions", "Global Settings"]
NAV_LOOKUP = {
    "actions": "Actions",
    "analyses": "Analyses",
    "champions": "Champions",
    "settings": "Global Settings",
    "global settings": "Global Settings",
}


def _apply_nav_query_params() -> None:
    params = st.query_params
    nav_value = params.get("nav")
    champion_value = params.get("champion")

    if isinstance(nav_value, list):
        nav_value = nav_value[0] if nav_value else None
    if isinstance(champion_value, list):
        champion_value = champion_value[0] if champion_value else None

    if nav_value:
        st.session_state["nav_page"] = str(nav_value).lower()
        if st.session_state["nav_page"] == "actions":
            st.session_state["actions_view_override"] = "Actions list"
    if champion_value:
        st.session_state["actions_filter_champion"] = str(champion_value)
    if nav_value or champion_value:
        st.query_params.clear()
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="CAPA Actions", layout="wide")

    _apply_nav_query_params()

    st.sidebar.title("Navigation")
    if "nav_page" in st.session_state:
        selected = NAV_LOOKUP.get(str(st.session_state["nav_page"]).lower())
        if selected:
            st.session_state["nav_page_selector"] = selected
        st.session_state.pop("nav_page", None)

    page = st.sidebar.radio("Go to", NAV_OPTIONS, key="nav_page_selector")

    if page == "Global Settings":
        render_global_settings()
    elif page == "Champions":
        render_champions_dashboard()
    elif page == "Analyses":
        render_analyses_module()
    else:
        render_actions_module()


if __name__ == "__main__":
    main()
