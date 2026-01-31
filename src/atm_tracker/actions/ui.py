from __future__ import annotations

from datetime import date
from typing import Optional

import streamlit as st
from pydantic import ValidationError

from atm_tracker.actions.db import init_db
from atm_tracker.actions.models import ActionCreate
from atm_tracker.actions.repo import (
    MAX_TEAM_MEMBERS,
    TASK_STATUSES,
    add_task,
    get_actions_progress_map,
    get_action,
    get_action_progress_summaries,
    get_action_team,
    get_action_team_sizes,
    insert_action,
    list_actions,
    list_tasks,
    set_action_team,
    soft_delete_action,
    soft_delete_task,
    update_status,
    update_task,
)
from atm_tracker.champions.repo import list_champions
from atm_tracker.projects.repo import list_projects


def render_actions_module() -> None:
    init_db()

    st.title("➕ CAPA Actions — Input Module")
    st.caption("Fast action capture with validation. No ROI yet — we build clean foundations.")

    if "actions_view" not in st.session_state:
        st.session_state["actions_view"] = "Add action"
    if "actions_view_override" in st.session_state:
        st.session_state["actions_view"] = st.session_state.pop("actions_view_override")

    view_options = ["Add action", "Actions list / edit", "Action details"]

    current_view = st.radio("View", view_options, horizontal=True, key="actions_view")

    if current_view == "Add action":
        _render_add()
    elif current_view == "Actions list / edit":
        _render_list()
    else:
        _render_action_details()


def _render_add() -> None:
    st.subheader("New action")

    champions_df = list_champions(active_only=True)
    champion_options = _build_champion_options(champions_df)
    projects_df = list_projects(include_inactive=False)
    team_selection: list[int] = []

    with st.form("add_action", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input("Title *", placeholder="e.g. Reduce scratch defects on L1")
            line = st.text_input("Line *", placeholder="e.g. L1")
            project = _render_project_input(projects_df)
            champion = _render_champion_input(champions_df)
            team_selection = _render_team_input(champions_df, champion_options, selected_ids=team_selection)
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

        description = st.text_area("Description", height=120, placeholder="Context, root cause, what we changed, expected effect...")

        submitted = st.form_submit_button("Save action")

    if not submitted:
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

    action_ids = df["id"].tolist()
    team_sizes = get_action_team_sizes(action_ids)
    progress_map = get_actions_progress_map([int(action_id) for action_id in action_ids])
    if "id" in df.columns:
        df["team_size"] = df["id"].map(lambda action_id: team_sizes.get(int(action_id), 0))
        progress_summaries = get_action_progress_summaries(
            [int(action_id) for action_id in action_ids]
        )
        df["tasks_total"] = df["id"].map(
            lambda action_id: progress_summaries.get(int(action_id), {}).get("total", 0)
        )
        df["tasks_done"] = df["id"].map(
            lambda action_id: progress_summaries.get(int(action_id), {}).get("done", 0)
        )
        df["progress"] = df["id"].map(lambda action_id: progress_map.get(int(action_id), 0))
        df["progress"] = df["progress"].map(lambda value: f"{int(value)}%")

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Open action details")

    if df.empty:
        st.info("No actions to open.")
        return

    action_lookup = {
        int(row["id"]): _build_action_label(
            int(row["id"]),
            row.get("project_or_family", ""),
            row.get("title", ""),
            progress_map.get(int(row["id"]), 0),
        )
        for _, row in df.iterrows()
    }
    selected_action_id = st.selectbox(
        "Select action",
        options=action_ids,
        format_func=lambda action_id: action_lookup.get(int(action_id), str(action_id)),
    )
    st.button(
        "Open action",
        on_click=_queue_action_details,
        args=(int(selected_action_id),),
    )

    st.divider()
    st.markdown("### Quick edit (status / close date)")

    if df.empty:
        st.info("No actions to edit.")
        return

    selected_id = st.selectbox(
        "Select action id",
        action_ids,
        format_func=lambda action_id: action_lookup.get(int(action_id), str(action_id)),
    )

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

    st.divider()
    st.markdown("### Team members")

    champions_all = list_champions(active_only=False)
    options = _build_champion_options(champions_all)
    current_team = get_action_team(int(selected_id))

    if champions_all.empty:
        st.info("Add champions in Global Settings first.")
        return

    selection = st.multiselect(
        f"Team members (max {MAX_TEAM_MEMBERS})",
        options=list(options.keys()),
        default=current_team,
        format_func=options.get,
    )
    names = [options.get(champion_id, f"ID {champion_id}") for champion_id in current_team]
    if names:
        st.caption(f"Current team: {', '.join(names)}")
    else:
        st.caption("Current team: (none)")

    if st.button("Save team"):
        if len(selection) > MAX_TEAM_MEMBERS:
            st.error(f"Team members cannot exceed {MAX_TEAM_MEMBERS}.")
        else:
            set_action_team(int(selected_id), selection)
            st.success("Team updated ✅")
            st.rerun()


def _render_action_details() -> None:
    actions_df = list_actions()
    if actions_df.empty:
        st.info("No actions available.")
        st.session_state.pop("selected_action_id", None)
        return

    action_ids = [int(row["id"]) for _, row in actions_df.iterrows()]
    progress_map = get_actions_progress_map(action_ids)
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
    current_action_id = st.session_state.get("selected_action_id")
    options = [None] + action_ids
    index = options.index(current_action_id) if current_action_id in action_ids else 0
    selected_action_id = st.selectbox(
        "Select action",
        options=options,
        index=index,
        format_func=lambda action_id: "(select...)"
        if action_id is None
        else action_lookup.get(int(action_id), str(action_id)),
        key="action_details_select_action",
    )

    if not selected_action_id:
        st.session_state.pop("selected_action_id", None)
        st.info("Select an action to view details.")
        return

    st.session_state["selected_action_id"] = int(selected_action_id)
    action_id = int(selected_action_id)

    action = get_action(int(action_id))
    if action is None:
        st.warning("Selected action not found.")
        st.session_state.pop("selected_action_id", None)
        st.session_state["actions_view_override"] = "Actions list / edit"
        st.rerun()
        return

    st.button("Back to list", on_click=_queue_actions_list)

    title = action.get("title", "")
    progress_summary = progress_summaries.get(
        int(action_id),
        {
            "total": 0,
            "done": 0,
            "progress_percent": 0,
            "has_overdue_subtasks": False,
            "is_action_overdue": False,
        },
    )
    progress_percent = int(progress_summary.get("progress_percent", 0))
    progress_color = _progress_color(
        progress_percent,
        bool(progress_summary.get("has_overdue_subtasks", False)),
        bool(progress_summary.get("is_action_overdue", False)),
    )
    _render_action_header(int(action_id), str(title or ""), progress_percent, progress_color)

    tasks_total = int(progress_summary.get("total", 0))
    tasks_done = int(progress_summary.get("done", 0))
    tasks_open = tasks_total - tasks_done
    st.caption(f"Tasks: {tasks_total} total • {tasks_done} done • {tasks_open} open")

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

    st.markdown(f"**Status:** {status or '(unknown)'}")
    st.markdown(f"**Champion (responsible):** {champion or '(unassigned)'}")
    st.markdown(f"**Team members:** {', '.join(team_names) if team_names else '(none)'}")
    st.markdown("**Key dates:**")
    st.markdown(
        f"- Created at: {created_at or '(not set)'}\n"
        f"- Target date: {target_date or '(not set)'}\n"
        f"- Closed at: {closed_at or '(not set)'}\n"
        f"- Status updated: {updated_at or '(not set)'}"
    )
    st.markdown("**Description:**")
    st.write(description or "(none)")

    st.divider()
    _render_tasks_section(
        action_id=int(action_id),
        team_ids=team_ids,
        champion_options=champion_options,
    )


def _render_tasks_section(
    action_id: int,
    team_ids: list[int],
    champion_options: dict[int, str],
) -> None:
    st.subheader("Tasks / Sub-actions")

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
    st.session_state["actions_view_override"] = "Actions list / edit"
