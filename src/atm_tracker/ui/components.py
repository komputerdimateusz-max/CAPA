from __future__ import annotations

from collections.abc import Callable, Sequence

import streamlit as st


def chip_toggle_group(
    label: str,
    options: Sequence[str],
    state_key: str,
    *,
    columns: int = 4,
    format_func: Callable[[str], str] | None = None,
) -> list[str]:
    if state_key not in st.session_state:
        st.session_state[state_key] = []

    format_func = format_func or (lambda value: value)
    selected = set(st.session_state.get(state_key, []))

    if label:
        st.markdown(f"**{label}**")

    if not options:
        return list(selected)

    chip_columns = st.columns(columns)
    for idx, option in enumerate(options):
        is_selected = option in selected
        label_text = format_func(option)
        if chip_columns[idx % columns].button(
            label_text,
            key=f"{state_key}_{idx}",
            type="primary" if is_selected else "secondary",
        ):
            if is_selected:
                selected.remove(option)
            else:
                selected.add(option)
            st.session_state[state_key] = [opt for opt in options if opt in selected]

    return list(st.session_state.get(state_key, []))


def chip_single_select(
    label: str,
    options: Sequence[str],
    state_key: str,
    *,
    columns: int = 3,
    format_func: Callable[[str], str] | None = None,
) -> str:
    if not options:
        st.session_state[state_key] = ""
        return ""

    if state_key not in st.session_state:
        st.session_state[state_key] = options[0]

    format_func = format_func or (lambda value: value)
    selected = st.session_state.get(state_key, options[0])

    if label:
        st.markdown(f"**{label}**")

    chip_columns = st.columns(columns)
    for idx, option in enumerate(options):
        is_selected = option == selected
        label_text = format_func(option)
        if chip_columns[idx % columns].button(
            label_text,
            key=f"{state_key}_{idx}",
            type="primary" if is_selected else "secondary",
        ):
            st.session_state[state_key] = option

    return st.session_state.get(state_key, options[0])

