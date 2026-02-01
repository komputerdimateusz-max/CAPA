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


def main() -> None:
    st.set_page_config(page_title="CAPA Actions", layout="wide")

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Actions", "Analyses", "Champions", "Global Settings"])

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
