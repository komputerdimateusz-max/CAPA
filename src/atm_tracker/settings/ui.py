from __future__ import annotations

import streamlit as st

from atm_tracker.actions.db import init_db
from atm_tracker.champions.repo import (
    add_champion,
    get_champion,
    list_champions,
    soft_delete_champion,
    update_champion,
)


DEFAULT_CHAMPION_LIMIT = 50


def render_global_settings() -> None:
    init_db()

    st.title("⚙️ Global Settings")
    st.caption("Manage shared reference data used across actions.")

    with st.expander("Add champion", expanded=True):
        with st.form("add_champion", clear_on_submit=True):
            first_name = st.text_input("First name")
            last_name = st.text_input("Last name")
            submitted = st.form_submit_button("Add")

        if submitted:
            try:
                new_id = add_champion(first_name, last_name)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success(f"Champion added ✅ (id={new_id})")
                st.rerun()

    st.markdown("### Champions")
    search_text = st.text_input("Search champion", key="champion_search")
    search_query = search_text.strip()
    champions = list_champions(
        include_inactive=True,
        search=search_query or None,
        limit=DEFAULT_CHAMPION_LIMIT,
    )

    options: dict[int, str] = {}
    for _, row in champions.iterrows():
        champion_id = int(row["id"])
        label = row.get("name_display", "") or row.get("name", "") or f"ID {champion_id}"
        if not bool(row.get("is_active", True)):
            label = f"{label} (inactive)"
        options[champion_id] = label

    current_selection = st.session_state.get("champion_select")
    if isinstance(current_selection, int) and current_selection not in options:
        selected_champion = get_champion(current_selection)
        if selected_champion:
            label = selected_champion.get("name_display") or selected_champion.get("name") or f"ID {current_selection}"
            if not bool(selected_champion.get("is_active", True)):
                label = f"{label} (inactive)"
            options[current_selection] = str(label)

    select_options: list[object] = ["(select...)"] + list(options.keys())
    selected = st.selectbox(
        "Select champion",
        options=select_options,
        format_func=lambda value: value if isinstance(value, str) else options.get(int(value), str(value)),
        key="champion_select",
    )

    if champions.empty:
        st.info("No matching champions. Add one above.")

    if isinstance(selected, str):
        return

    champion_id = int(selected)
    champion = get_champion(champion_id)
    if not champion:
        st.error("Champion not found.")
        return

    st.markdown("#### Edit champion")
    with st.form("edit_champion"):
        first_name = st.text_input("First name", value=str(champion.get("first_name", "")))
        last_name = st.text_input("Last name", value=str(champion.get("last_name", "")))
        is_active = st.checkbox("Is active", value=bool(champion.get("is_active", True)))
        save = st.form_submit_button("Save changes")

    if save:
        try:
            update_champion(champion_id, first_name, last_name, is_active)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("Updated ✅")
            st.rerun()

    if st.button("Delete (soft)"):
        soft_delete_champion(champion_id)
        st.session_state["champion_select"] = "(select...)"
        st.success("Deleted (soft) ✅")
        st.rerun()
