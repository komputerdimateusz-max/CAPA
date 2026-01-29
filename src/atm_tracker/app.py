from __future__ import annotations

import streamlit as st

from atm_tracker.actions.ui import render_actions_module


def main() -> None:
    st.set_page_config(page_title="CAPA Actions", layout="wide")
    render_actions_module()


if __name__ == "__main__":
    main()
