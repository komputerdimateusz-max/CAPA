from __future__ import annotations

from datetime import date

import streamlit as st
from pydantic import ValidationError

from atm_tracker.actions.db import init_db
from atm_tracker.actions.models import ActionCreate
from atm_tracker.actions.repo import insert_action, list_actions, soft_delete_action, update_status
from atm_tracker.champions.repo import list_champions


def render_actions_module() -> None:
    init_db()

    st.title("➕ CAPA Actions — Input Module")
    st.caption("Fast action capture with validation. No ROI yet — we build clean foundations.")

    tab_add, tab_list = st.tabs(["Add action", "Actions list / edit"])

    with tab_add:
        _render_add()

    with tab_list:
        _render_list()


def _render_add() -> None:
    st.subheader("New action")

    champions_df = list_champions(active_only=True)

    with st.form("add_action", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input("Title *", placeholder="e.g. Reduce scratch defects on L1")
            line = st.text_input("Line *", placeholder="e.g. L1")
            project = st.text_input("Project / family", placeholder="e.g. ProjectX")
            champion = _render_champion_input(champions_df)
            tags = st.text_input("Tags (comma-separated)", placeholder="scrap, coating, poka-yoke")

        with col2:
            status = st.selectbox("Status", ["OPEN", "IN_PROGRESS", "CLOSED"], index=0)
            created_at = st.date_input("Created at *", value=date.today())
            implemented_at = st.date_input("Implemented at", value=None)
            closed_at = st.date_input("Closed at", value=None)

            st.markdown("**Action cost (MVP)**")
            cost_internal_hours = st.number_input("Internal hours", min_value=0.0, value=0.0, step=0.5)
            cost_external_eur = st.number_input("External cost (€)", min_value=0.0, value=0.0, step=10.0)
            cost_material_eur = st.number_input("Material cost (€)", min_value=0.0, value=0.0, step=10.0)

        description = st.text_area("Description", height=120, placeholder="Context, root cause, what we changed, expected effect...")

        submitted = st.form_submit_button("Save action")

    if not submitted:
        return

    try:
        a = ActionCreate(
            title=title.strip(),
            description=description.strip(),
            line=line.strip(),
            project_or_family=project.strip(),
            owner="",
            champion=_normalize_name(champion),
            status=status,
            created_at=created_at,
            implemented_at=implemented_at,
            closed_at=closed_at,
            cost_internal_hours=cost_internal_hours,
            cost_external_eur=cost_external_eur,
            cost_material_eur=cost_material_eur,
            tags=tags.strip(),
        )
    except ValidationError as e:
        st.error("Validation error — fix inputs:")
        st.code(str(e))
        return

    new_id = insert_action(a)
    st.success(f"Saved ✅ (id={new_id})")


def _render_champion_input(champions_df) -> str:
    if champions_df.empty:
        return st.text_input("Champion", placeholder="e.g. Anna")

    options = ["(none)"] + champions_df["name_display"].tolist() + ["Other (type manually)"]
    selection = st.selectbox("Champion", options)

    if selection == "Other (type manually)":
        return st.text_input("Champion name")
    if selection == "(none)":
        return ""
    return selection


def _normalize_name(value: str) -> str:
    return " ".join(value.split())


def _render_list() -> None:
    st.subheader("Actions list")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        status = st.selectbox("Filter: status", ["(all)", "OPEN", "IN_PROGRESS", "CLOSED"])
    with c2:
        line = st.text_input("Filter: line", placeholder="e.g. L1")
    with c3:
        project = st.text_input("Filter: project/family", placeholder="e.g. ProjectX")
    with c4:
        search = st.text_input("Search", placeholder="title/desc/champion")

    df = list_actions(
        status=None if status == "(all)" else status,
        line=line.strip() or None,
        project_or_family=project.strip() or None,
        search=search.strip() or None,
    )

    if "owner" in df.columns:
        df = df.drop(columns=["owner"])

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Quick edit (status / close date)")

    if df.empty:
        st.info("No actions to edit.")
        return

    action_ids = df["id"].tolist()
    selected_id = st.selectbox("Select action id", action_ids)

    row = df[df["id"] == selected_id].iloc[0]
    colA, colB, colC, colD = st.columns(4)
    with colA:
        new_status = st.selectbox("New status", ["OPEN", "IN_PROGRESS", "CLOSED"], index=["OPEN","IN_PROGRESS","CLOSED"].index(row["status"]))
    with colB:
        new_closed = st.date_input("Closed at (required if CLOSED)", value=row["closed_at"])
    with colC:
        st.write("")
        st.write("")
        if st.button("Update"):
            if new_status == "CLOSED" and not new_closed:
                st.error("closed_at is required when status=CLOSED")
            else:
                update_status(int(selected_id), new_status, new_closed if new_status == "CLOSED" else None)
                st.success("Updated ✅")
                st.rerun()
    with colD:
        st.write("")
        st.write("")
        if st.button("Delete (soft)"):
            # Hide action from lists without losing history.
            soft_delete_action(int(selected_id))
            st.success("Deleted (soft) ✅")
            st.rerun()
