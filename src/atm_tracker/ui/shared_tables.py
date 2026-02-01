from __future__ import annotations

import html
from typing import Sequence

import streamlit as st

from atm_tracker.ui.styles import card


def render_table_card(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        row_html.append(f"<tr>{cells}</tr>")

    table_html = f"""
    <table class="ds-table">
        <thead><tr>{header_html}</tr></thead>
        <tbody>
            {''.join(row_html)}
        </tbody>
    </table>
    """
    st.markdown(card(table_html), unsafe_allow_html=True)
