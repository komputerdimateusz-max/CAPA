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
from atm_tracker.projects.repo import (
    add_project,
    get_project,
    list_projects,
    soft_delete_project,
    update_project,
)


DEFAULT_CHAMPION_LIMIT = 50
DEFAULT_PROJECT_LIMIT = 50


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

    if not isinstance(selected, str):
        champion_id = int(selected)
        champion = get_champion(champion_id)
        if not champion:
            st.error("Champion not found.")
        else:
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

    st.markdown("### Projects")

    with st.expander("Add project", expanded=True):
        with st.form("add_project", clear_on_submit=True):
            project_name = st.text_input("Project name")
            project_code = st.text_input("Project code (optional)")
            project_submitted = st.form_submit_button("Add project")

        if project_submitted:
            try:
                new_id = add_project(project_name, project_code)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success(f"Project added ✅ (id={new_id})")
                st.rerun()

    project_search = st.text_input("Search project", key="project_search")
    project_query = project_search.strip()
    projects = list_projects(
        include_inactive=True,
        search=project_query or None,
        limit=DEFAULT_PROJECT_LIMIT,
    )

    project_options: dict[int, str] = {}
    for _, row in projects.iterrows():
        project_id = int(row["id"])
        name = row.get("name", "") or f"ID {project_id}"
        code = row.get("code", "")
        label = f"{name} ({code})" if code else name
        if not bool(row.get("is_active", True)):
            label = f"{label} (inactive)"
        project_options[project_id] = label

    current_project = st.session_state.get("project_select")
    if isinstance(current_project, int) and current_project not in project_options:
        selected_project = get_project(current_project)
        if selected_project:
            name = selected_project.get("name") or f"ID {current_project}"
            code = selected_project.get("code", "")
            label = f"{name} ({code})" if code else name
            if not bool(selected_project.get("is_active", True)):
                label = f"{label} (inactive)"
            project_options[current_project] = str(label)

    project_select_options: list[object] = ["(select...)"] + list(project_options.keys())
    selected_project = st.selectbox(
        "Select project",
        options=project_select_options,
        format_func=lambda value: value
        if isinstance(value, str)
        else project_options.get(int(value), str(value)),
        key="project_select",
    )

    if projects.empty:
        st.info("No matching projects. Add one above.")

    if isinstance(selected_project, str):
        return

    project_id = int(selected_project)
    project = get_project(project_id)
    if not project:
        st.error("Project not found.")
        return

    st.markdown("#### Edit project")
    with st.form("edit_project"):
        project_name = st.text_input("Name", value=str(project.get("name", "")))
        project_code = st.text_input("Code", value=str(project.get("code", "")))
        project_active = st.checkbox("Is active", value=bool(project.get("is_active", True)))
        project_save = st.form_submit_button("Save changes")

    if project_save:
        try:
            update_project(project_id, project_name, project_code, project_active)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("Updated ✅")
            st.rerun()

    if st.button("Delete (soft)", key="delete_project"):
        soft_delete_project(project_id)
        st.session_state["project_select"] = "(select...)"
        st.success("Deleted (soft) ✅")
        st.rerun()
