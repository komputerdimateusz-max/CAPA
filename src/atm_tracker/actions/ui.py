from __future__ import annotations

from datetime import date
import html
from typing import Optional

import streamlit as st
import pandas as pd
from pydantic import ValidationError

from atm_tracker.actions.db import init_db
from atm_tracker.actions.models import ActionCreate
from atm_tracker.actions.repo import (
    MAX_TEAM_MEMBERS,
    TASK_STATUSES,
    add_task,
    get_actions_days_late,
    get_actions_progress_map,
    get_action,
    get_action_progress_summaries,
    get_action_team,
    insert_action,
    list_actions,
    list_tasks,
    set_action_team,
    soft_delete_action,
    soft_delete_task,
    update_task,
)
from atm_tracker.champions.repo import list_champions
from atm_tracker.projects.repo import list_projects
from atm_tracker.ui.layout import footer, kpi_row, main_grid, page_header, section
from atm_tracker.ui.styles import card, inject_global_styles, muted, pill

DEFAULT_ACTION_PROGRESS_SUMMARY = {
    "progress_percent": 0,
    "has_overdue_subtasks": False,
    "is_action_overdue": False,
    "total": 0,
    "done": 0,
    "open": 0,
}

VIEW_OPTIONS = ["Add action", "Actions list", "Action details"]


def _apply_action_details_query_params() -> None:
    params = st.query_params
    view_param = params.get("view")
    action_param = params.get("action_id")

    if isinstance(view_param, list):
        view_value = view_param[0] if view_param else None
    else:
        view_value = view_param

    if isinstance(action_param, list):
        action_value = action_param[0] if action_param else None
    else:
        action_value = action_param

    if action_value:
        try:
            action_id = int(action_value)
        except (TypeError, ValueError):
            return
        if view_value in (None, "", "details"):
            st.session_state["selected_action_id"] = action_id
            st.session_state["actions_view_override"] = "Action details"


def render_actions_module() -> None:
    init_db()
    inject_global_styles()

    _apply_action_details_query_params()

    if "actions_view" not in st.session_state:
        st.session_state["actions_view"] = VIEW_OPTIONS[0]
    if "actions_view_override" in st.session_state:
        st.session_state["actions_view"] = st.session_state.pop("actions_view_override")

    current_view = st.session_state.get("actions_view", VIEW_OPTIONS[0])

    if current_view == "Add action":
        _render_add()
    elif current_view == "Actions list":
        _render_list()
    else:
        try:
            _render_action_details()
        except Exception as exc:
            st.error(f"Action details error (hotfix): {exc}")
            st.info("Please select another action or go back to list.")


def _render_view_selector() -> None:
    st.selectbox("View", options=VIEW_OPTIONS, key="actions_view")


def _render_add() -> None:
    page_header(
        "➕ Add action",
        "Fast action capture with validation. No ROI yet — we build clean foundations.",
        actions=_render_view_selector,
    )
    st.divider()
    kpi_row([])
    st.divider()

    champions_df = list_champions(active_only=True)
    champion_options = _build_champion_options(champions_df)
    projects_df = list_projects(include_inactive=False)
    team_selection: list[int] = []

    with main_grid("wide") as (main,):
        with main:
            section("New action")
            with st.form("add_action", clear_on_submit=True):
                col1, col2 = st.columns(2)

                with col1:
                    title = st.text_input("Title *", placeholder="e.g. Reduce scratch defects on L1")
                    line = st.text_input("Line *", placeholder="e.g. L1")
                    project = _render_project_input(projects_df)
                    champion = _render_champion_input(champions_df)
                    team_selection = _render_team_input(
                        champions_df, champion_options, selected_ids=team_selection
                    )
                    tags = st.text_input("Tags (comma-separated)", placeholder="scrap, coating, poka-yoke")

                with col2:
                    status = st.selectbox("Status", ["OPEN", "IN_PROGRESS", "CLOSED"], index=0)
                    created_at = st.date_input("Created at *", value=date.today())
                    target_date = st.date_input("Target Date", value=None)
                    closed_at = st.date_input("Closed at", value=None)

                    st.markdown("**Action cost (MVP)**")
                    cost_internal_hours = st.number_input("Internal hours", min_value=0.0, value=0.0, step=0.5)
                    cost_external_eur = st.number_input("External cost (€)", min_value=0.0, value=0.0, step=10.0)
                    cost_material_eur = st.number_input("Material cost (€)", min_value=0.0, value=0.0, step=10.0)

                description = st.text_area(
                    "Description",
                    height=120,
                    placeholder="Context, root cause, what we changed, expected effect...",
                )

                submitted = st.form_submit_button("Save action")

    if not submitted:
        footer("Action-to-Money Tracker • Build the baseline before ROI.")
        return

    try:
        if len(team_selection) > MAX_TEAM_MEMBERS:
            st.error(f"Team members cannot exceed {MAX_TEAM_MEMBERS}.")
            return
        a = ActionCreate(
            title=title.strip(),
            description=description.strip(),
            line=line.strip(),
            project_or_family=_normalize_name(project),
            owner="",
            champion=_normalize_name(champion),
            status=status,
            created_at=created_at,
            target_date=target_date,
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
    set_action_team(new_id, team_selection)
    st.success(f"Saved ✅ (id={new_id})")
    footer("Action-to-Money Tracker • Build the baseline before ROI.")


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


def _render_project_input(projects_df) -> str:
    if projects_df.empty:
        st.info("Add projects in Global Settings.")
        return st.text_input("Project", placeholder="e.g. ProjectX")

    options = ["(none)"] + projects_df["name"].tolist()
    labels = {}
    for _, row in projects_df.iterrows():
        name = row.get("name", "")
        code = row.get("code", "")
        label = f"{name} ({code})" if code else name
        labels[name] = label

    selection = st.selectbox("Project", options, format_func=lambda value: labels.get(value, value))
    if selection == "(none)":
        return ""
    return selection


def _normalize_name(value: str) -> str:
    return " ".join(value.split())


def _build_action_label(
    action_id: int,
    project_or_family: str,
    title: str,
    progress: int,
) -> str:
    project_value = _normalize_name(str(project_or_family or ""))
    title_value = _normalize_name(str(title or ""))
    parts = [str(action_id)]
    if project_value:
        parts.append(project_value)
    if title_value:
        parts.append(title_value)
    label = " ".join(parts)
    return f"{label} — {int(progress)}%"


def _render_list() -> None:
    export_container: Optional[st.delta_generator.DeltaGenerator] = None

    def _actions() -> None:
        nonlocal export_container
        _render_view_selector()
        if st.button("Refresh", use_container_width=True):
            st.rerun()
        export_container = st.container()

    page_header(
        "📋 Action List",
        "Overview of active and closed actions with key KPIs. Click an action title to open Action Details.",
        actions=_actions,
    )
    st.divider()

    df = list_actions()
    total_actions = len(df)

    if "owner" in df.columns:
        df = df.drop(columns=["owner"])

    status_options = sorted([value for value in df.get("status", pd.Series([])).dropna().unique()])
    champion_options = sorted(
        [value for value in df.get("champion", pd.Series([])).dropna().unique() if str(value).strip()]
    )
    project_options = sorted(
        [
            value
            for value in df.get("project_or_family", pd.Series([])).dropna().unique()
            if str(value).strip()
        ]
    )

    if "actions_filter_statuses" not in st.session_state:
        st.session_state["actions_filter_statuses"] = status_options
    if "actions_filter_champion" not in st.session_state:
        st.session_state["actions_filter_champion"] = "All"
    if "actions_filter_project" not in st.session_state:
        st.session_state["actions_filter_project"] = "All"
    if "actions_filter_search" not in st.session_state:
        st.session_state["actions_filter_search"] = ""
    if "actions_filter_due_from" not in st.session_state:
        st.session_state["actions_filter_due_from"] = None
    if "actions_filter_due_to" not in st.session_state:
        st.session_state["actions_filter_due_to"] = None

    selected_statuses = [
        status
        for status in st.session_state.get("actions_filter_statuses", status_options)
        if status in status_options
    ]
    if not selected_statuses:
        selected_statuses = status_options

    selected_champion = st.session_state.get("actions_filter_champion", "All")
    if selected_champion not in ["All"] + champion_options:
        selected_champion = "All"

    selected_project = st.session_state.get("actions_filter_project", "All")
    if selected_project not in ["All"] + project_options:
        selected_project = "All"

    search_text = st.session_state.get("actions_filter_search", "")
    due_date_from = st.session_state.get("actions_filter_due_from")
    due_date_to = st.session_state.get("actions_filter_due_to")

    filtered_df = df.copy()

    if selected_statuses and "status" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["status"].isin(selected_statuses)]

    if selected_champion != "All" and "champion" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["champion"] == selected_champion]

    if selected_project != "All" and "project_or_family" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["project_or_family"] == selected_project]

    if search_text:
        search_lower = search_text.strip().lower()
        id_matches = filtered_df["id"].astype(str).str.contains(search_lower, case=False, na=False)
        title_matches = filtered_df.get("title", pd.Series([])).astype(str).str.contains(
            search_lower, case=False, na=False
        )
        filtered_df = filtered_df[id_matches | title_matches]

    if "target_date" in filtered_df.columns and (due_date_from or due_date_to):
        due_series = pd.to_datetime(filtered_df["target_date"], errors="coerce").dt.date
        if due_date_from:
            filtered_df = filtered_df[due_series >= due_date_from]
        if due_date_to:
            filtered_df = filtered_df[due_series <= due_date_to]
    action_ids = [int(action_id) for action_id in filtered_df.get("id", pd.Series([])).tolist()]
    days_late_map = get_actions_days_late(action_ids)
    if "id" in filtered_df.columns:
        filtered_df = filtered_df.copy()
        filtered_df["days_late"] = filtered_df["id"].map(
            lambda action_id: days_late_map.get(int(action_id), 0)
        )

    status_lower = filtered_df.get("status", pd.Series([])).astype(str).str.lower()
    open_actions = int((status_lower != "closed").sum()) if not filtered_df.empty else 0
    overdue_actions = int((filtered_df.get("days_late", pd.Series([])) > 0).sum())
    late_days = filtered_df.get("days_late", pd.Series([]))
    avg_days_late = float(late_days[late_days > 0].mean()) if (late_days > 0).any() else 0.0
    closed_mask = status_lower == "closed"
    closed_count = int(closed_mask.sum())
    on_time_closed = int(((filtered_df.get("days_late", pd.Series([])) <= 0) & closed_mask).sum())
    on_time_close_rate = (on_time_closed / closed_count * 100) if closed_count else 0.0
    kpi_row(
        [
            ("Open actions", f"{open_actions}"),
            ("Overdue actions", f"{overdue_actions}"),
            ("Avg days late", f"{avg_days_late:.1f}"),
            ("On-time close rate", f"{on_time_close_rate:.0f}%"),
        ]
    )
    st.divider()

    with main_grid("wide") as (main,):
        with main:
            with st.expander("🔍 Filters", expanded=True):
                filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
                with filter_col1:
                    st.multiselect(
                        "Status",
                        options=status_options,
                        key="actions_filter_statuses",
                    )
                with filter_col2:
                    st.selectbox(
                        "Champion",
                        options=["All"] + champion_options,
                        key="actions_filter_champion",
                    )
                with filter_col3:
                    st.selectbox(
                        "Project",
                        options=["All"] + project_options,
                        key="actions_filter_project",
                    )
                with filter_col4:
                    st.text_input(
                        "Search (ID or title)",
                        placeholder="e.g. 42 or reduce defects",
                        key="actions_filter_search",
                    )

                date_col1, date_col2 = st.columns(2)
                with date_col1:
                    st.date_input("Due date from", value=None, key="actions_filter_due_from")
                with date_col2:
                    st.date_input("Due date to", value=None, key="actions_filter_due_to")

            if df.empty:
                st.markdown(muted("📭 No actions available."), unsafe_allow_html=True)
                st.caption("Showing 0 of 0 actions")
                footer("Action-to-Money Tracker • Keep actions traceable and on time.")
                return

            if filtered_df.empty:
                st.markdown(
                    muted("📭 No actions match current filters. Try adjusting filters or date range."),
                    unsafe_allow_html=True,
                )
                st.caption(f"Showing 0 of {total_actions} actions")
                footer("Action-to-Money Tracker • Keep actions traceable and on time.")
                return

            if "days_late" in filtered_df.columns or "target_date" in filtered_df.columns:
                sort_columns: list[str] = []
                sort_ascending: list[bool] = []
                if "days_late" in filtered_df.columns:
                    sort_columns.append("days_late")
                    sort_ascending.append(False)
                if "target_date" in filtered_df.columns:
                    sort_columns.append("target_date")
                    sort_ascending.append(True)
                if sort_columns:
                    filtered_df = filtered_df.sort_values(by=sort_columns, ascending=sort_ascending)

            section("Actions")

            table_columns = []
            column_labels = {
                "title": "Title",
                "status": "Status",
                "champion": "Champion",
                "project_or_family": "Project",
                "target_date": "Due date",
                "closed_at": "Closed at",
                "days_late": "Days late",
            }
            for key in column_labels:
                if key in filtered_df.columns:
                    table_columns.append(key)

            def format_value(value: object) -> str:
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    return "—"
                if isinstance(value, date):
                    return value.strftime("%Y-%m-%d")
                return html.escape(str(value))

            def status_label(status_value: str, days_late_value: int) -> str:
                status_normalized = str(status_value or "").strip().lower()
                if days_late_value > 0 and status_normalized != "closed":
                    return "Overdue"
                if status_normalized in {"in_progress", "ongoing"}:
                    return "In progress"
                if status_normalized == "closed":
                    return "Closed"
                if status_normalized == "open":
                    return "Open"
                return status_value or "Open"

            rows_html = []
            for _, row in filtered_df.iterrows():
                row_cells = []
                action_id = row.get("id")
                for column in table_columns:
                    if column == "title":
                        label = row.get("title") or f"Action #{int(action_id)}"
                        link = f"?view=details&action_id={int(action_id)}"
                        row_cells.append(
                            f"<td><a class='ds-link' href='{link}'>{html.escape(str(label))}</a></td>"
                        )
                    elif column == "status":
                        label = status_label(row.get("status"), int(row.get("days_late", 0)))
                        row_cells.append(f"<td>{pill(label)}</td>")
                    else:
                        row_cells.append(f"<td>{format_value(row.get(column))}</td>")
                rows_html.append(f"<tr>{''.join(row_cells)}</tr>")

            header_html = "".join([f"<th>{column_labels[col]}</th>" for col in table_columns])
            table_html = f"""
            <table class="ds-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
            """
            st.markdown(card(table_html), unsafe_allow_html=True)

            export_df = filtered_df.copy()
            if "title" in filtered_df.columns:
                export_df = export_df.rename(columns={"title": "Title"})
            csv_data = export_df.to_csv(index=False)
            if export_container is not None:
                with export_container:
                    st.download_button(
                        "Export CSV",
                        data=csv_data,
                        file_name="actions_export.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
            st.caption(f"Showing {len(filtered_df)} of {total_actions} actions")
    footer("Action-to-Money Tracker • Keep actions traceable and on time.")


def _render_action_details() -> None:
    actions_df = list_actions()
    if st.session_state.pop("flash_action_deleted", False):
        st.info("Action deleted")

    action_ids = [int(row["id"]) for _, row in actions_df.iterrows()] if not actions_df.empty else []
    progress_map = get_actions_progress_map(action_ids) if action_ids else {}
    progress_summaries: dict[int, dict] = {}
    try:
        progress_summaries = get_action_progress_summaries(action_ids) if action_ids else {}
        if not isinstance(progress_summaries, dict):
            progress_summaries = {}
    except Exception:
        progress_summaries = {}

    action_lookup = {
        int(row["id"]): _build_action_label(
            int(row["id"]),
            row.get("project_or_family", ""),
            row.get("title", ""),
            progress_map.get(int(row["id"]), 0),
        )
        for _, row in actions_df.iterrows()
    }
    action_ids = list(action_lookup.keys())

    selection_value: Optional[int] = None

    def _actions() -> None:
        nonlocal selection_value
        _render_view_selector()
        selection_value = st.selectbox(
            "Action",
            options=[None] + action_ids,
            index=_safe_index([None] + action_ids, st.session_state.get("selected_action_id")),
            format_func=lambda action_id: "(select...)"
            if action_id is None
            else action_lookup.get(int(action_id), str(action_id)),
            key="action_details_select_action",
        )

    page_header(
        "🧾 Action Details",
        "Review status, dates, tasks, and team ownership for a selected action.",
        actions=_actions,
    )
    st.divider()

    if actions_df.empty:
        kpi_row([])
        st.divider()
        with main_grid("focus") as (main, _side):
            with main:
                st.markdown(muted("📭 No actions available."), unsafe_allow_html=True)
        footer("Action-to-Money Tracker • Transparency before impact.")
        st.session_state.pop("selected_action_id", None)
        return

    selected_action_id = selection_value
    if selected_action_id is None:
        st.session_state.pop("selected_action_id", None)
        kpi_row([])
        st.divider()
        with main_grid("focus") as (main, _side):
            with main:
                st.markdown(muted("Select an action to view details."), unsafe_allow_html=True)
        footer("Action-to-Money Tracker • Transparency before impact.")
        return

    st.session_state["selected_action_id"] = int(selected_action_id)
    action_id = int(selected_action_id)

    action = get_action(int(action_id))
    if action is None:
        st.warning("Selected action not found.")
        st.session_state.pop("selected_action_id", None)
        st.session_state["actions_view_override"] = "Actions list"
        st.rerun()
        return

    title = action.get("title", "")
    progress_summary = progress_summaries.get(
        int(action_id),
        DEFAULT_ACTION_PROGRESS_SUMMARY,
    )
    progress_percent = int(progress_summary.get("progress_percent", 0))

    tasks_total = int(progress_summary.get("total", 0))
    tasks_done = int(progress_summary.get("done", 0))
    tasks_open = tasks_total - tasks_done
    champions_all = list_champions(active_only=False)
    champion_options = _build_champion_options(champions_all)
    team_ids = get_action_team(int(action_id))
    team_names = [champion_options.get(member_id, f"ID {member_id}") for member_id in team_ids]

    status = action.get("status", "")
    champion = action.get("champion", "")
    created_at = action.get("created_at")
    target_date = action.get("target_date")
    closed_at = action.get("closed_at")
    updated_at = action.get("updated_at")
    description = action.get("description", "")

    details_items = [
        f"<li><strong>Tasks:</strong> {tasks_total} total • {tasks_done} done • {tasks_open} open</li>",
        f"<li><strong>Status:</strong> {pill(status or 'Open')}</li>",
        f"<li><strong>Champion (responsible):</strong> {html.escape(champion or '(unassigned)')}</li>",
        f"<li><strong>Team members:</strong> {html.escape(', '.join(team_names)) if team_names else '(none)'}</li>",
        "<li><strong>Key dates:</strong>",
        "<ul class='ds-list'>"
        f"<li>Created at: {html.escape(str(created_at or '(not set)'))}</li>"
        f"<li>Target date: {html.escape(str(target_date or '(not set)'))}</li>"
        f"<li>Closed at: {html.escape(str(closed_at or '(not set)'))}</li>"
        f"<li>Status updated: {html.escape(str(updated_at or '(not set)'))}</li>"
        "</ul></li>",
    ]

    kpi_row(
        [
            ("Progress", f"{progress_percent}%"),
            ("Tasks total", f"{tasks_total}"),
            ("Tasks open", f"{tasks_open}"),
            ("Tasks done", f"{tasks_done}"),
        ]
    )
    st.divider()

    with main_grid("focus") as (main, side):
        with main:
            section("Action overview")
            title_text = str(title or f"Action #{int(action_id)}")
            st.markdown(f"**{html.escape(title_text)}**")
            section("Description")
            st.markdown(card(html.escape(description or "(none)")), unsafe_allow_html=True)
            _render_tasks_section(
                action_id=int(action_id),
                team_ids=team_ids,
                champion_options=champion_options,
            )
        with side:
            section("Action summary")
            details_html = f"<ul class='ds-list'>{''.join(details_items)}</ul>"
            st.markdown(card(details_html), unsafe_allow_html=True)
            section("Actions")
            st.button("Back to list", on_click=_queue_actions_list, use_container_width=True)
            if st.button("Delete action (soft)", use_container_width=True):
                soft_delete_action(int(action_id))
                st.session_state.pop("selected_action_id", None)
                st.session_state["flash_action_deleted"] = True
                st.rerun()
    footer("Action-to-Money Tracker • Transparency before impact.")


def _render_tasks_section(
    action_id: int,
    team_ids: list[int],
    champion_options: dict[int, str],
) -> None:
    section("Tasks / Sub-actions")

    champions_active = list_champions(active_only=True)
    active_ids = [int(row["id"]) for _, row in champions_active.iterrows()] if not champions_active.empty else []

    show_all = st.checkbox("Show all champions", value=False, key="tasks_show_all_champions")
    assignee_options = _build_assignee_options(
        team_ids=team_ids,
        active_ids=active_ids,
        show_all=show_all,
    )

    assignee_labels = {None: "(unassigned)", **champion_options}

    tasks_df = list_tasks(action_id)
    if tasks_df.empty:
        st.info("No tasks yet.")
    else:
        for _, task in tasks_df.iterrows():
            task_id = int(task["id"])
            task_title = task.get("title", "")
            task_status = task.get("status", "OPEN")
            task_assignee = task.get("assignee_champion_id")
            task_target = task.get("target_date")
            task_description = task.get("description", "")

            with st.expander(f"{task_title} (#{task_id})", expanded=False):
                title_value = st.text_input("Title", value=task_title, key=f"task_title_{task_id}")
                description_value = st.text_area(
                    "Description", value=task_description, height=100, key=f"task_desc_{task_id}"
                )
                status_value = st.selectbox(
                    "Status",
                    TASK_STATUSES,
                    index=TASK_STATUSES.index(task_status) if task_status in TASK_STATUSES else 0,
                    key=f"task_status_{task_id}",
                )
                assignee_value = st.selectbox(
                    "Assignee",
                    options=assignee_options,
                    index=_safe_index(assignee_options, task_assignee),
                    format_func=lambda cid: assignee_labels.get(cid, f"ID {cid}"),
                    key=f"task_assignee_{task_id}",
                )
                target_value = st.date_input(
                    "Target date", value=task_target, key=f"task_target_{task_id}"
                )

                col_save, col_delete = st.columns(2)
                with col_save:
                    if st.button("Save", key=f"task_save_{task_id}"):
                        update_task(
                            task_id=task_id,
                            title=title_value.strip(),
                            description=description_value.strip(),
                            assignee_champion_id=None if assignee_value is None else int(assignee_value),
                            status=status_value,
                            target_date=target_value,
                        )
                        st.success("Task updated ✅")
                        st.rerun()
                with col_delete:
                    if st.button("Delete", key=f"task_delete_{task_id}"):
                        soft_delete_task(task_id)
                        st.success("Task deleted ✅")
                        st.rerun()

    with st.form(f"add_task_{action_id}", clear_on_submit=True):
        title = st.text_input("Title *")
        assignee = st.selectbox(
            "Assignee",
            options=assignee_options,
            format_func=lambda cid: assignee_labels.get(cid, f"ID {cid}"),
        )
        status = st.selectbox("Status", TASK_STATUSES, index=0)
        target_date = st.date_input("Target date", value=None)
        description = st.text_area("Description", height=100)
        submitted = st.form_submit_button("Add task")

    if submitted:
        if not title.strip():
            st.error("Title is required.")
        else:
            add_task(
                action_id=action_id,
                title=title.strip(),
                description=description.strip(),
                assignee_champion_id=None if assignee is None else int(assignee),
                status=status,
                target_date=target_date,
            )
            st.success("Task added ✅")
            st.rerun()


def _render_team_input(champions_df, champion_options, selected_ids: list[int]) -> list[int]:
    if champions_df.empty:
        st.info("Add champions in Global Settings first.")
        return []

    selection = st.multiselect(
        f"Team members (max {MAX_TEAM_MEMBERS})",
        options=list(champion_options.keys()),
        default=selected_ids,
        format_func=champion_options.get,
    )
    if len(selection) > MAX_TEAM_MEMBERS:
        st.error(f"Team members cannot exceed {MAX_TEAM_MEMBERS}.")
    return selection


def _build_champion_options(champions_df):
    options = {}
    if champions_df.empty:
        return options

    active_column = "is_active" in champions_df.columns
    for _, row in champions_df.iterrows():
        champion_id = int(row["id"])
        name = row.get("name_display", "") or row.get("name", "") or f"ID {champion_id}"
        if active_column and int(row.get("is_active", 1)) == 0:
            name = f"{name} (inactive)"
        options[champion_id] = name
    return options


def _build_assignee_options(
    team_ids: list[int],
    active_ids: list[int],
    show_all: bool,
) -> list[Optional[int]]:
    unique_ids: list[int] = []
    seen: set[int] = set()

    base_ids = active_ids if show_all or not team_ids else team_ids
    for cid in base_ids + team_ids:
        if cid is None:
            continue
        cid_int = int(cid)
        if cid_int not in seen:
            seen.add(cid_int)
            unique_ids.append(cid_int)

    return [None] + unique_ids


def _safe_index(options: list[Optional[int]], value: Optional[int]) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0


def _queue_action_details(action_id: int) -> None:
    st.session_state["selected_action_id"] = int(action_id)
    st.session_state["actions_view_override"] = "Action details"


def _queue_actions_list() -> None:
    if "action_id" in st.query_params:
        del st.query_params["action_id"]
    if "view" in st.query_params:
        del st.query_params["view"]
    st.session_state["actions_view_override"] = "Actions list"
