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
from atm_tracker.ui.layout import footer, page_header, section
from atm_tracker.ui.styles import inject_global_styles

DEFAULT_CHAMPION_LIMIT = 50
DEFAULT_PROJECT_LIMIT = 50


@st.dialog("Add champion", width="large")
def _open_add_champion_dialog() -> None:
    st.caption("Create a new champion for ownership and action tracking.")
    with st.form("add_champion_dialog", clear_on_submit=True):
        first_name = st.text_input("First name *", placeholder="e.g. Anna")
        last_name = st.text_input("Last name *", placeholder="e.g. Martins")

        save_col, cancel_col = st.columns(2)
        save_clicked = save_col.form_submit_button("Save", type="primary", use_container_width=True)
        cancel_clicked = cancel_col.form_submit_button("Cancel", use_container_width=True)

    if cancel_clicked:
        st.rerun()

    if save_clicked:
        try:
            new_id = add_champion(first_name, last_name)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.toast("Champion added successfully.")
            st.session_state["champion_select"] = int(new_id)
            st.rerun()


@st.dialog("Add project", width="large")
def _open_add_project_dialog() -> None:
    st.caption("Create a new project used by actions and reporting.")
    with st.form("add_project_dialog", clear_on_submit=True):
        project_name = st.text_input("Project name *", placeholder="e.g. Assembly optimization")
        project_code = st.text_input("Project code", placeholder="optional")

        save_col, cancel_col = st.columns(2)
        save_clicked = save_col.form_submit_button("Save", type="primary", use_container_width=True)
        cancel_clicked = cancel_col.form_submit_button("Cancel", use_container_width=True)

    if cancel_clicked:
        st.rerun()

    if save_clicked:
        try:
            new_id = add_project(project_name, project_code)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.toast("Project added successfully.")
            st.session_state["project_select"] = int(new_id)
            st.rerun()


def _section_header_with_add(title: str, add_label: str, key: str) -> bool:
    title_col, action_col = st.columns([4, 1], vertical_alignment="center")
    title_col.markdown(f"### {title}")
    return action_col.button(add_label, key=key, type="primary", use_container_width=True)


def _render_champions_section() -> None:
    with st.container(border=True):
        add_champion_clicked = _section_header_with_add("Manage Champions", "+ Add champion", "open_add_champion")
        if add_champion_clicked:
            _open_add_champion_dialog()

        champions = list_champions(include_inactive=True, search=None, limit=DEFAULT_CHAMPION_LIMIT)
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

        selected = st.selectbox(
            "Select champion",
            options=["(select...)"] + list(options.keys()),
            format_func=lambda value: value if isinstance(value, str) else options.get(int(value), str(value)),
            key="champion_select",
        )

        if champions.empty:
            st.info("No matching champions. Add one with the button above.")

        if isinstance(selected, str):
            return

        champion_id = int(selected)
        champion = get_champion(champion_id)
        if not champion:
            st.error("Champion not found.")
            return

        section("Edit champion")
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


def render_projects_admin_section() -> None:
    with st.container(border=True):
        add_project_clicked = _section_header_with_add("Manage Projects", "+ Add project", "open_add_project")
        if add_project_clicked:
            _open_add_project_dialog()

        projects = list_projects(include_inactive=True, search=None, limit=DEFAULT_PROJECT_LIMIT)
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

        selected_project = st.selectbox(
            "Select project",
            options=["(select...)"] + list(project_options.keys()),
            format_func=lambda value: value if isinstance(value, str) else project_options.get(int(value), str(value)),
            key="project_select",
        )

        if projects.empty:
            st.info("No matching projects. Add one with the button above.")

        if isinstance(selected_project, str):
            return

        project_id = int(selected_project)
        project = get_project(project_id)
        if not project:
            st.error("Project not found.")
            return

        section("Edit project")
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


def render_global_settings() -> None:
    init_db()
    inject_global_styles()

    page_header("⚙️ Settings", "Manage shared reference data used across actions.")
    _render_champions_section()
    render_projects_admin_section()
    footer("Action-to-Money Tracker • Keep reference data clean for ROI work.")
