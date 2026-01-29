from __future__ import annotations

import streamlit as st

from atm_tracker.actions.db import init_db
from atm_tracker.champions.repo import add_champion, list_champions, set_champion_active, soft_delete_champion


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
    champions = list_champions(active_only=False)

    if champions.empty:
        st.info("No champions yet. Add one above.")
        return

    for _, row in champions.iterrows():
        champion_id = int(row["id"])
        st.markdown(f"**{row['name_display']}**")
        active_value = bool(row["is_active"])
        is_active = st.checkbox("Active", value=active_value, key=f"champion_active_{champion_id}")

        if st.button("Save changes", key=f"save_champion_{champion_id}"):
            set_champion_active(champion_id, is_active)
            st.success("Updated ✅")
            st.rerun()

        if st.button("Delete (soft)", key=f"delete_champion_{champion_id}"):
            soft_delete_champion(champion_id)
            st.success("Deleted (soft) ✅")
            st.rerun()

        st.divider()
