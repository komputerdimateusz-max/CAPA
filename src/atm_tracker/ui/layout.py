from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import streamlit as st


def page_header(
    title: str,
    subtitle: str = "",
    actions: Callable[[], None] | None = None,
) -> None:
    """Render a standard page header with optional actions."""
    col_title, col_actions = st.columns([3, 1], vertical_alignment="bottom")
    with col_title:
        st.markdown(f"## {title}")
        if subtitle:
            st.caption(subtitle)
    with col_actions:
        if actions:
            actions()


def kpi_row(items: list[tuple[str, str | int | float]]) -> None:
    """Render a row of KPI metrics."""
    if not items:
        return
    columns = st.columns(len(items))
    for col, (label, value) in zip(columns, items):
        col.metric(label, value)


@contextmanager
def main_grid(mode: str = "wide") -> Iterator[tuple[st.delta_generator.DeltaGenerator, ...]]:
    """Yield main/side containers based on the requested layout mode."""
    if mode == "wide":
        yield (st.container(),)
        return
    if mode == "split":
        main, side = st.columns([3, 1], gap="large")
        yield (main, side)
        return
    if mode == "focus":
        main, side = st.columns([2, 1], gap="large")
        yield (main, side)
        return
    raise ValueError(f"Unknown layout mode: {mode}")


def section(title: str) -> None:
    """Render a section header."""
    st.markdown(f"### {title}")


def footer(text: str) -> None:
    """Render a small footer caption."""
    st.caption(text)


__all__ = ["page_header", "kpi_row", "main_grid", "section", "footer"]
