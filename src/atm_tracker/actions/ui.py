from __future__ import annotations

from datetime import date, timedelta
import html
import json
import re
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
    update_action_text_field,
)
from atm_tracker.analyses.repo import list_linked_analysis_ids
from atm_tracker.champions.repo import list_champions
from atm_tracker.projects.repo import list_projects
from atm_tracker.ui.layout import footer, kpi_row, main_grid, page_header, section
from atm_tracker.ui.components import chip_single_select, chip_toggle_group
from atm_tracker.ui.shared_tables import render_table_card
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

ADD_ACTION_TEMPLATES = [
    {
        "label": "Containment (24h)",
        "title_prefix": "[Containment] ",
        "due_days": 1,
        "status": "OPEN",
    },
    {
        "label": "Root cause analysis task",
        "title_prefix": "[RCA] ",
        "due_days": 7,
        "status": None,
    },
    {
        "label": "Update SOP / Training",
        "title_prefix": "[SOP] ",
        "due_days": 14,
        "status": None,
    },
    {
        "label": "Maintenance intervention",
        "title_prefix": "[Maintenance] ",
        "due_days": 3,
        "status": None,
    },
]

WIZARD_STEPS = {
    1: "1. Basics",
    2: "2. Dates & Status",
    3: "3. Tags & Context",
    4: "4. Review",
}

ANALYSIS_COLUMN_PRIORITY = [
    "analysis",
    "analysis_notes",
    "rca",
    "root_cause",
    "rca_notes",
    "investigation",
    "notes",
    "description",
    "comment",
]

ANALYSIS_IMPACT_OPTIONS = ["Scrap", "Downtime", "Quality", "Safety", "Cost", "Customer"]
ANALYSIS_EVIDENCE_STATUSES = ["Hypothesis", "Confirmed", "Rejected"]
ANALYSIS_CONTAINMENT_OPTIONS = [
    "Stop shipment",
    "100% inspection",
    "Sort & rework",
    "Quarantine",
    "Temporary parameter change",
]
ANALYSIS_RCA_METHODS = ["5 Why", "Ishikawa"]
ISHIKAWA_CATEGORIES = [
    "Man",
    "Machine",
    "Method",
    "Material",
    "Measurement",
    "Environment",
]

ANALYSIS_BLOCK_PATTERN = re.compile(
    r"### Analysis \(Wizard\)(?:.|\n)*?```json\s*(?P<payload>\{.*?\})\s*```",
    re.DOTALL,
)


def _analysis_storage_column(action: pd.Series) -> Optional[str]:
    columns = set(action.index)
    for column in ANALYSIS_COLUMN_PRIORITY:
        if column in columns:
            return column
    return None


def _split_analysis_block(text: str) -> tuple[str, Optional[dict[str, object]]]:
    if not text:
        return "", None
    match = ANALYSIS_BLOCK_PATTERN.search(str(text))
    if not match:
        return str(text).strip(), None
    payload = None
    payload_text = match.group("payload")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        payload = None
    remaining = (str(text)[: match.start()] + str(text)[match.end() :]).strip()
    return remaining, payload


def _init_state_value(key: str, value: object) -> None:
    if key not in st.session_state:
        st.session_state[key] = value


def _build_analysis_draft(payload: Optional[dict[str, object]]) -> dict[str, object]:
    payload = payload or {}
    evidence = payload.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    whys_payload = payload.get("whys", [])
    whys_list: list[dict[str, str]] = []
    if isinstance(whys_payload, list):
        for item in whys_payload:
            if isinstance(item, dict):
                text = str(item.get("text", "") or item.get("why", "") or "")
                status = str(item.get("status", "Hypothesis") or "Hypothesis")
            else:
                text = str(item or "")
                status = "Hypothesis"
            whys_list.append({"text": text, "status": status})
    while len(whys_list) < 3:
        whys_list.append({"text": "", "status": "Hypothesis"})

    ishikawa_payload = payload.get("ishikawa", {})
    ishikawa: dict[str, list[dict[str, str]]] = {}
    if isinstance(ishikawa_payload, dict):
        for category in ISHIKAWA_CATEGORIES:
            category_payload = ishikawa_payload.get(category, [])
            causes: list[dict[str, str]] = []
            if isinstance(category_payload, list):
                for entry in category_payload:
                    if isinstance(entry, dict):
                        cause_text = str(entry.get("cause", "") or "")
                        confidence = str(entry.get("confidence", "Medium") or "Medium")
                    else:
                        cause_text = str(entry or "")
                        confidence = "Medium"
                    causes.append({"cause": cause_text, "confidence": confidence})
            ishikawa[category] = causes
    else:
        ishikawa = {category: [] for category in ISHIKAWA_CATEGORIES}

    return {
        "problem": str(payload.get("problem", "") or ""),
        "process": str(evidence.get("where_process", "") or payload.get("process", "") or ""),
        "impact": payload.get("impact", []) if isinstance(payload.get("impact"), list) else [],
        "evidence_note": str(evidence.get("note", "") or ""),
        "evidence_status": str(evidence.get("status", "Hypothesis") or "Hypothesis"),
        "containment": payload.get("containment", []) if isinstance(payload.get("containment"), list) else [],
        "containment_notes": str(evidence.get("containment_notes", "") or ""),
        "rca_method": str(payload.get("rca_method", "5why") or "5why"),
        "whys": whys_list,
        "root_cause_index": payload.get("root_cause_index"),
        "ishikawa": ishikawa,
        "step": int(payload.get("step", 1) or 1),
    }


def _format_analysis_block(draft: dict[str, object]) -> str:
    problem = str(draft.get("problem", "") or "(not set)")
    process = str(draft.get("process", "") or "(not set)")
    impact = draft.get("impact", []) or []
    containment = draft.get("containment", []) or []
    containment_notes = str(draft.get("containment_notes", "") or "")
    rca_method = str(draft.get("rca_method", "5why") or "5why")
    evidence_note = str(draft.get("evidence_note", "") or "")
    evidence_status = str(draft.get("evidence_status", "Hypothesis") or "Hypothesis")
    whys = draft.get("whys", []) or []
    root_index = draft.get("root_cause_index")
    ishikawa = draft.get("ishikawa", {}) if isinstance(draft.get("ishikawa"), dict) else {}

    root_label = "(not selected)"
    root_text = ""
    if isinstance(root_index, int) and 1 <= root_index <= len(whys):
        root_label = f"Why #{root_index}"
        root_text = str(whys[root_index - 1].get("text", "") or "")
    elif isinstance(root_index, str) and root_index.isdigit():
        index_int = int(root_index)
        if 1 <= index_int <= len(whys):
            root_label = f"Why #{index_int}"
            root_text = str(whys[index_int - 1].get("text", "") or "")

    impact_text = ", ".join(impact) if impact else "(none)"
    containment_text = ", ".join(containment) if containment else "(none)"
    root_text_summary = f"{root_label} – {root_text}".strip(" –") if root_text else root_label

    markdown_lines = [
        "### Analysis (Wizard)",
        f"Problem: {problem}",
        f"Where / Process: {process}",
        f"Impact: [{impact_text}]",
        f"Containment: {containment_text}",
    ]
    if containment_notes:
        markdown_lines.append(f"Containment notes: {containment_notes}")
    markdown_lines.extend(
        [
            f"RCA method: {'5 Why' if rca_method == '5why' else 'Ishikawa'}",
            f"Root cause: {root_text_summary}",
            f"Evidence: {evidence_status} — {evidence_note or '(none)'}",
            "",
        ]
    )

    payload = {
        "problem": problem,
        "impact": impact,
        "containment": containment,
        "rca_method": rca_method,
        "whys": whys,
        "root_cause_index": root_index,
        "ishikawa": ishikawa,
        "evidence": {
            "note": evidence_note,
            "status": evidence_status,
            "where_process": process,
            "containment_notes": containment_notes,
        },
    }
    json_payload = json.dumps(payload, indent=2)
    markdown_lines.append("```json")
    markdown_lines.append(json_payload)
    markdown_lines.append("```")
    return "\n".join(markdown_lines)


def _build_analysis_summary_html(draft: dict[str, object]) -> str:
    problem = html.escape(str(draft.get("problem", "") or "(not set)"))
    process = html.escape(str(draft.get("process", "") or "(not set)"))
    impact = draft.get("impact", []) or []
    containment = draft.get("containment", []) or []
    containment_notes = html.escape(str(draft.get("containment_notes", "") or ""))
    evidence_note = html.escape(str(draft.get("evidence_note", "") or "(none)"))
    evidence_status = html.escape(str(draft.get("evidence_status", "Hypothesis") or "Hypothesis"))
    rca_method = str(draft.get("rca_method", "5why") or "5why")
    whys = draft.get("whys", []) or []
    root_index = draft.get("root_cause_index")
    ishikawa = draft.get("ishikawa", {}) if isinstance(draft.get("ishikawa"), dict) else {}

    impact_text = ", ".join(html.escape(str(item)) for item in impact) if impact else "(none)"
    containment_text = ", ".join(html.escape(str(item)) for item in containment) if containment else "(none)"

    root_label = "(not selected)"
    root_text = ""
    if isinstance(root_index, int) and 1 <= root_index <= len(whys):
        root_label = f"Why #{root_index}"
        root_text = str(whys[root_index - 1].get("text", "") or "")
    elif isinstance(root_index, str) and root_index.isdigit():
        index_int = int(root_index)
        if 1 <= index_int <= len(whys):
            root_label = f"Why #{index_int}"
            root_text = str(whys[index_int - 1].get("text", "") or "")
    root_display = html.escape(root_label)
    if root_text:
        root_display = f"{root_display} – {html.escape(root_text)}"

    html_parts = [
        "<ul class='ds-list'>",
        f"<li><strong>Problem:</strong> {problem}</li>",
        f"<li><strong>Where / Process:</strong> {process}</li>",
        f"<li><strong>Impact:</strong> {impact_text}</li>",
        f"<li><strong>Containment:</strong> {containment_text}</li>",
    ]
    if containment_notes:
        html_parts.append(f"<li><strong>Containment notes:</strong> {containment_notes}</li>")
    html_parts.extend(
        [
            f"<li><strong>RCA method:</strong> {'5 Why' if rca_method == '5why' else 'Ishikawa'}</li>",
            f"<li><strong>Root cause:</strong> {root_display}</li>",
            f"<li><strong>Evidence:</strong> {evidence_status} — {evidence_note}</li>",
        ]
    )

    if rca_method == "5why":
        if whys:
            html_parts.append("<li><strong>5 Whys:</strong><ol class='ds-list'>")
            for item in whys:
                why_text = html.escape(str(item.get("text", "") or "(blank)"))
                why_status = html.escape(str(item.get("status", "Hypothesis") or "Hypothesis"))
                html_parts.append(f"<li>{why_text} <em>({why_status})</em></li>")
            html_parts.append("</ol></li>")
        else:
            html_parts.append("<li><strong>5 Whys:</strong> (none)</li>")
    else:
        html_parts.append("<li><strong>Ishikawa causes:</strong><ul class='ds-list'>")
        for category in ISHIKAWA_CATEGORIES:
            causes = ishikawa.get(category, [])
            if not causes:
                html_parts.append(f"<li>{html.escape(category)}: (none)</li>")
                continue
            html_parts.append(f"<li>{html.escape(category)}:<ul class='ds-list'>")
            for cause in causes:
                cause_text = html.escape(str(cause.get("cause", "") or "(blank)"))
                confidence = html.escape(str(cause.get("confidence", "Medium") or "Medium"))
                html_parts.append(f"<li>{cause_text} <em>({confidence})</em></li>")
            html_parts.append("</ul></li>")
        html_parts.append("</ul></li>")

    html_parts.append("</ul>")
    return "".join(html_parts)


def _set_analysis_step(action_id: int, step: int) -> None:
    clamped = max(1, min(4, step))
    st.session_state["analysis_step"] = clamped
    action_key = str(action_id)
    if "analysis_draft" in st.session_state and action_key in st.session_state["analysis_draft"]:
        st.session_state["analysis_draft"][action_key]["step"] = clamped


def _clear_analysis_state(action_id: int) -> None:
    action_key = str(action_id)
    if "analysis_draft" in st.session_state:
        st.session_state["analysis_draft"].pop(action_key, None)
    pattern = re.compile(rf"_{re.escape(str(action_id))}(?:_|$)")
    for key in list(st.session_state.keys()):
        if key.startswith("analysis_") and pattern.search(key):
            st.session_state.pop(key, None)
    st.session_state["analysis_step"] = 1


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


def _init_add_action_state(champions_df: pd.DataFrame, projects_df: pd.DataFrame) -> None:
    defaults = {
        "add_action_title": "",
        "add_action_line": "",
        "add_action_description": "",
        "add_action_status": "OPEN",
        "add_action_created_at": date.today(),
        "add_action_target_date": None,
        "add_action_closed_at": None,
        "add_action_cost_internal_hours": 0.0,
        "add_action_cost_external_eur": 0.0,
        "add_action_cost_material_eur": 0.0,
        "add_action_tags": [],
        "add_action_team_ids": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "add_action_step" not in st.session_state:
        st.session_state["add_action_step"] = 1
    if "add_action_step_selector" not in st.session_state:
        st.session_state["add_action_step_selector"] = WIZARD_STEPS[1]

    if champions_df.empty:
        if "add_action_champion_text" not in st.session_state:
            st.session_state["add_action_champion_text"] = ""
    else:
        if "add_action_champion_select" not in st.session_state:
            st.session_state["add_action_champion_select"] = "(none)"
        if "add_action_champion_other" not in st.session_state:
            st.session_state["add_action_champion_other"] = ""

    if projects_df.empty:
        if "add_action_project_text" not in st.session_state:
            st.session_state["add_action_project_text"] = ""
    else:
        if "add_action_project_select" not in st.session_state:
            st.session_state["add_action_project_select"] = "(none)"


def _set_add_action_step(step: int) -> None:
    clamped = max(1, min(4, step))
    st.session_state["add_action_step"] = clamped
    st.session_state["add_action_step_selector"] = WIZARD_STEPS[clamped]


def _apply_add_action_template(template: dict) -> None:
    prefix = template.get("title_prefix", "")
    due_days = template.get("due_days")
    status = template.get("status")

    title = st.session_state.get("add_action_title", "").strip()
    if prefix:
        if not title:
            st.session_state["add_action_title"] = prefix
        elif not title.startswith(prefix):
            st.session_state["add_action_title"] = f"{prefix}{title}"

    if due_days is not None:
        st.session_state["add_action_target_date"] = date.today() + timedelta(days=int(due_days))

    if status:
        st.session_state["add_action_status"] = status

    _set_add_action_step(2)


def _clear_add_action_state() -> None:
    keys = [
        "add_action_title",
        "add_action_line",
        "add_action_description",
        "add_action_status",
        "add_action_created_at",
        "add_action_target_date",
        "add_action_closed_at",
        "add_action_cost_internal_hours",
        "add_action_cost_external_eur",
        "add_action_cost_material_eur",
        "add_action_tags",
        "add_action_team_ids",
        "add_action_champion_text",
        "add_action_champion_select",
        "add_action_champion_other",
        "add_action_project_text",
        "add_action_project_select",
        "add_action_step",
        "add_action_step_selector",
        "add_action_created_id",
    ]
    for key in keys:
        st.session_state.pop(key, None)


def _get_add_action_champion(champions_df: pd.DataFrame) -> str:
    if champions_df.empty:
        return st.session_state.get("add_action_champion_text", "")

    selection = st.session_state.get("add_action_champion_select", "(none)")
    if selection == "Other (type manually)":
        return st.session_state.get("add_action_champion_other", "")
    if selection == "(none)":
        return ""
    return selection


def _get_add_action_project(projects_df: pd.DataFrame) -> str:
    if projects_df.empty:
        return st.session_state.get("add_action_project_text", "")

    selection = st.session_state.get("add_action_project_select", "(none)")
    if selection == "(none)":
        return ""
    return selection


def _render_add() -> None:
    page_header(
        "➕ Add Action",
        "Create a corrective action using quick templates or a guided wizard.",
        actions=_render_view_selector,
    )
    st.divider()
    kpi_row([])
    st.divider()

    champions_df = list_champions(active_only=True)
    champion_options = _build_champion_options(champions_df)
    projects_df = list_projects(include_inactive=False)
    _init_add_action_state(champions_df, projects_df)

    with main_grid("wide") as (main,):
        with main:
            section("Quick templates")
            template_cols = st.columns(len(ADD_ACTION_TEMPLATES))
            for col, template in zip(template_cols, ADD_ACTION_TEMPLATES):
                if col.button(template["label"], key=f"add_action_template_{template['label']}"):
                    _apply_add_action_template(template)
                    st.rerun()

            st.divider()
            section("Action wizard")
            step_label = st.radio(
                "Step",
                options=list(WIZARD_STEPS.values()),
                index=max(0, st.session_state.get("add_action_step", 1) - 1),
                horizontal=True,
                key="add_action_step_selector",
            )
            step_value = [step for step, label in WIZARD_STEPS.items() if label == step_label][0]
            st.session_state["add_action_step"] = step_value

            st.divider()
            current_step = st.session_state.get("add_action_step", 1)
            team_selection: list[int] = st.session_state.get("add_action_team_ids", [])

            if current_step == 1:
                title = st.text_input(
                    "Title *",
                    placeholder="e.g. Reduce scratch defects on L1",
                    key="add_action_title",
                )
                line = st.text_input("Line *", placeholder="e.g. L1", key="add_action_line")
                project = _render_project_input(projects_df, key_prefix="add_action")
                champion = _render_champion_input(champions_df, key_prefix="add_action")
                team_selection = _render_team_input(
                    champions_df,
                    champion_options,
                    selected_ids=team_selection,
                    key="add_action_team_ids",
                )
                st.text_area(
                    "Minimal description",
                    height=120,
                    placeholder="Context, root cause, what we changed, expected effect...",
                    key="add_action_description",
                )

            elif current_step == 2:
                status = chip_single_select(
                    "Status",
                    ["OPEN", "IN_PROGRESS", "CLOSED"],
                    "add_action_status",
                    columns=3,
                    format_func=lambda value: value.replace("_", " ").title(),
                )
                created_at = st.date_input("Created at *", key="add_action_created_at")
                target_date = st.date_input("Target/Due date *", value=None, key="add_action_target_date")

                if status != "CLOSED":
                    if st.session_state.get("add_action_closed_at") is not None:
                        st.session_state["add_action_closed_at"] = None
                else:
                    if st.session_state.get("add_action_closed_at") is None:
                        st.session_state["add_action_closed_at"] = date.today()
                    st.date_input("Closed at *", key="add_action_closed_at")

                st.markdown("**Action cost (MVP)**")
                st.number_input(
                    "Internal hours",
                    min_value=0.0,
                    step=0.5,
                    key="add_action_cost_internal_hours",
                )
                st.number_input(
                    "External cost (€)",
                    min_value=0.0,
                    step=10.0,
                    key="add_action_cost_external_eur",
                )
                st.number_input(
                    "Material cost (€)",
                    min_value=0.0,
                    step=10.0,
                    key="add_action_cost_material_eur",
                )

            elif current_step == 3:
                chip_toggle_group(
                    "Tags",
                    ["Scrap", "Safety", "Customer", "Audit", "Downtime", "Quality", "Cost"],
                    "add_action_tags",
                    columns=4,
                )
                st.caption("Tap chips to toggle tags. Tags are stored as comma-separated values.")

            else:
                champion = _get_add_action_champion(champions_df)
                project = _get_add_action_project(projects_df)
                status = st.session_state.get("add_action_status", "OPEN")
                created_at = st.session_state.get("add_action_created_at")
                target_date = st.session_state.get("add_action_target_date")
                closed_at = st.session_state.get("add_action_closed_at")
                title = st.session_state.get("add_action_title", "")
                line = st.session_state.get("add_action_line", "")
                description = st.session_state.get("add_action_description", "")
                tags = st.session_state.get("add_action_tags", [])

                summary_items = [
                    f"<li><strong>Title:</strong> {html.escape(title or '(missing)')}</li>",
                    f"<li><strong>Line:</strong> {html.escape(line or '(missing)')}</li>",
                    f"<li><strong>Project:</strong> {html.escape(project or '(none)')}</li>",
                    f"<li><strong>Champion:</strong> {html.escape(champion or '(none)')}</li>",
                    f"<li><strong>Status:</strong> {pill(status)}</li>",
                    f"<li><strong>Created:</strong> {html.escape(str(created_at or '(missing)'))}</li>",
                    f"<li><strong>Due:</strong> {html.escape(str(target_date or '(missing)'))}</li>",
                    f"<li><strong>Closed:</strong> {html.escape(str(closed_at or '(not closed)'))}</li>",
                    f"<li><strong>Tags:</strong> {html.escape(', '.join(tags) or '(none)')}</li>",
                    f"<li><strong>Description:</strong> {html.escape(description or '(none)')}</li>",
                ]
                st.markdown(card(f"<ul class='ds-list'>{''.join(summary_items)}</ul>"), unsafe_allow_html=True)

                if st.button("✅ Create action", type="primary", use_container_width=True):
                    validation_errors = []
                    if not title.strip():
                        validation_errors.append("Title is required.")
                    if not line.strip():
                        validation_errors.append("Line is required.")
                    if not target_date:
                        validation_errors.append("Target/Due date is required.")
                    if status == "CLOSED" and not closed_at:
                        validation_errors.append("Closed at is required when status is Closed.")
                    if len(team_selection) > MAX_TEAM_MEMBERS:
                        validation_errors.append(f"Team members cannot exceed {MAX_TEAM_MEMBERS}.")

                    if validation_errors:
                        for error in validation_errors:
                            st.error(error)
                        footer("Action-to-Money Tracker • Build the baseline before ROI.")
                        return

                    try:
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
                            cost_internal_hours=st.session_state.get("add_action_cost_internal_hours", 0.0),
                            cost_external_eur=st.session_state.get("add_action_cost_external_eur", 0.0),
                            cost_material_eur=st.session_state.get("add_action_cost_material_eur", 0.0),
                            tags=", ".join(tags),
                        )
                    except ValidationError as exc:
                        st.error("Validation error — fix inputs:")
                        st.code(str(exc))
                        footer("Action-to-Money Tracker • Build the baseline before ROI.")
                        return

                    new_id = insert_action(a)
                    set_action_team(new_id, team_selection)
                    st.session_state["add_action_created_id"] = int(new_id)
                    st.success(f"Saved ✅ (id={new_id})")

                created_id = st.session_state.get("add_action_created_id")
                if created_id:
                    if st.button("Open action details", use_container_width=True):
                        _queue_action_details(int(created_id))
                        st.rerun()
                    if st.button("Create another action", use_container_width=True):
                        _clear_add_action_state()
                        st.rerun()

            nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
            with nav_col1:
                if st.button(
                    "⬅️ Back",
                    disabled=current_step == 1,
                    use_container_width=True,
                    key="add_action_back",
                ):
                    _set_add_action_step(current_step - 1)
                    st.rerun()
            with nav_col2:
                st.markdown(muted(f"Step {current_step} of 4"), unsafe_allow_html=True)
            with nav_col3:
                if st.button(
                    "Next ➡️",
                    disabled=current_step == 4,
                    use_container_width=True,
                    key="add_action_next",
                ):
                    _set_add_action_step(current_step + 1)
                    st.rerun()

    footer("Action-to-Money Tracker • Build the baseline before ROI.")


def _render_champion_input(champions_df, *, key_prefix: str = "add_action") -> str:
    if champions_df.empty:
        return st.text_input(
            "Champion",
            placeholder="e.g. Anna",
            key=f"{key_prefix}_champion_text",
        )

    options = ["(none)"] + champions_df["name_display"].tolist() + ["Other (type manually)"]
    selection = st.selectbox("Champion", options, key=f"{key_prefix}_champion_select")

    if selection == "Other (type manually)":
        return st.text_input("Champion name", key=f"{key_prefix}_champion_other")
    if selection == "(none)":
        return ""
    return selection


def _render_project_input(projects_df, *, key_prefix: str = "add_action") -> str:
    if projects_df.empty:
        st.info("Add projects in Global Settings.")
        return st.text_input(
            "Project",
            placeholder="e.g. ProjectX",
            key=f"{key_prefix}_project_text",
        )

    options = ["(none)"] + projects_df["name"].tolist()
    labels = {}
    for _, row in projects_df.iterrows():
        name = row.get("name", "")
        code = row.get("code", "")
        label = f"{name} ({code})" if code else name
        labels[name] = label

    selection = st.selectbox(
        "Project",
        options,
        format_func=lambda value: labels.get(value, value),
        key=f"{key_prefix}_project_select",
    )
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

            rows = []
            for _, row in filtered_df.iterrows():
                row_cells = []
                action_id = row.get("id")
                for column in table_columns:
                    if column == "title":
                        label = row.get("title") or f"Action #{int(action_id)}"
                        link = f"?view=details&action_id={int(action_id)}"
                        row_cells.append(f"<a class='ds-link' href='{link}'>{html.escape(str(label))}</a>")
                    elif column == "status":
                        label = status_label(row.get("status"), int(row.get("days_late", 0)))
                        row_cells.append(pill(label))
                    else:
                        row_cells.append(format_value(row.get(column)))
                rows.append(row_cells)

            headers = [column_labels[col] for col in table_columns]
            render_table_card(headers, rows)

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
                st.markdown(muted("Select an action to add analysis."), unsafe_allow_html=True)
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
    analysis_column = _analysis_storage_column(action)
    analysis_value = action.get(analysis_column, "") if analysis_column else ""
    stripped_description = description
    if analysis_column == "description":
        stripped_description, _payload = _split_analysis_block(str(description or ""))
    linked_analysis_ids = list_linked_analysis_ids(int(action_id))
    linked_analysis_label = ", ".join(linked_analysis_ids) if linked_analysis_ids else "(none)"

    details_items = [
        f"<li><strong>Tasks:</strong> {tasks_total} total • {tasks_done} done • {tasks_open} open</li>",
        f"<li><strong>Status:</strong> {pill(status or 'Open')}</li>",
        f"<li><strong>Champion (responsible):</strong> {html.escape(champion or '(unassigned)')}</li>",
        f"<li><strong>Linked analysis:</strong> {html.escape(linked_analysis_label)}</li>",
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
            st.markdown(card(html.escape(stripped_description or "(none)")), unsafe_allow_html=True)
            _render_tasks_section(
                action_id=int(action_id),
                team_ids=team_ids,
                champion_options=champion_options,
            )
            _render_analysis_section(
                action_id=int(action_id),
                action=action,
                actions_df=actions_df,
                analysis_column=analysis_column,
                analysis_value=analysis_value,
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


def _render_analysis_section(
    action_id: int,
    action: pd.Series,
    actions_df: pd.DataFrame,
    analysis_column: Optional[str],
    analysis_value: object,
) -> None:
    section("🧠 Analysis")

    if analysis_column is None:
        st.error(
            "No suitable text column exists to store analysis. "
            "Add a text column such as notes or description to enable analysis persistence."
        )
        return

    action_key = str(action_id)
    base_text, payload = _split_analysis_block(str(analysis_value or ""))

    if "analysis_draft" not in st.session_state:
        st.session_state["analysis_draft"] = {}
    if action_key not in st.session_state["analysis_draft"]:
        draft = _build_analysis_draft(payload)
        draft["base_text"] = base_text
        st.session_state["analysis_draft"][action_key] = draft
    else:
        draft = st.session_state["analysis_draft"][action_key]
        draft.setdefault("base_text", base_text)

    if st.session_state.get("analysis_action_id") != action_id:
        st.session_state["analysis_action_id"] = action_id
        _set_analysis_step(action_id, int(draft.get("step", 1) or 1))

    current_step = int(st.session_state.get("analysis_step", 1) or 1)

    st.progress(current_step / 4)
    step_labels = [
        "Problem definition",
        "Containment",
        "Root cause",
        "Review & save",
    ]
    step_cols = st.columns(4)
    for idx, label in enumerate(step_labels, start=1):
        step_cols[idx - 1].markdown(f"**{label}**" if idx == current_step else label)

    if st.button("Reset analysis draft", key=f"analysis_reset_{action_id}"):
        _clear_analysis_state(action_id)
        st.rerun()

    st.divider()

    line_options: list[str] = []
    if not actions_df.empty and "line" in actions_df.columns:
        line_options = sorted(
            {
                str(value).strip()
                for value in actions_df["line"].dropna().tolist()
                if str(value).strip()
            }
        )

    if current_step == 1:
        problem_key = f"analysis_problem_{action_id}"
        _init_state_value(problem_key, draft.get("problem", ""))
        problem_value = st.text_input("Problem statement", key=problem_key)

        process_value = ""
        if line_options:
            process_key = f"analysis_process_{action_id}"
            process_options = ["(not set)"] + line_options + ["Other (type manually)"]
            default_process = draft.get("process", "")
            if default_process not in process_options:
                default_process = "Other (type manually)" if default_process else "(not set)"
            _init_state_value(process_key, default_process)
            selection = st.selectbox("Where / Process", options=process_options, key=process_key)
            if selection == "Other (type manually)":
                custom_key = f"analysis_process_custom_{action_id}"
                custom_default = draft.get("process", "")
                _init_state_value(custom_key, custom_default if custom_default not in process_options else "")
                process_value = st.text_input("Specify process", key=custom_key)
            elif selection != "(not set)":
                process_value = selection
        else:
            process_key = f"analysis_process_{action_id}"
            _init_state_value(process_key, draft.get("process", ""))
            process_value = st.text_input("Where / Process", key=process_key)

        impact_key = f"analysis_impact_{action_id}"
        _init_state_value(impact_key, draft.get("impact", []))
        impact_value = chip_toggle_group("Impact chips", ANALYSIS_IMPACT_OPTIONS, impact_key, columns=3)

        evidence_note_key = f"analysis_evidence_note_{action_id}"
        _init_state_value(evidence_note_key, draft.get("evidence_note", ""))
        evidence_note_value = st.text_input("Evidence note", key=evidence_note_key)

        evidence_status_key = f"analysis_evidence_status_{action_id}"
        _init_state_value(evidence_status_key, draft.get("evidence_status", "Hypothesis"))
        evidence_status_value = chip_single_select(
            "Evidence status",
            ANALYSIS_EVIDENCE_STATUSES,
            evidence_status_key,
            columns=3,
        )

        draft.update(
            {
                "problem": problem_value,
                "process": process_value,
                "impact": impact_value,
                "evidence_note": evidence_note_value,
                "evidence_status": evidence_status_value,
            }
        )

    elif current_step == 2:
        containment_key = f"analysis_containment_{action_id}"
        _init_state_value(containment_key, draft.get("containment", []))
        containment_value = chip_toggle_group(
            "Containment actions",
            ANALYSIS_CONTAINMENT_OPTIONS,
            containment_key,
            columns=2,
        )

        containment_notes_key = f"analysis_containment_notes_{action_id}"
        _init_state_value(containment_notes_key, draft.get("containment_notes", ""))
        containment_notes_value = st.text_area("Containment notes", key=containment_notes_key, height=120)

        draft.update(
            {
                "containment": containment_value,
                "containment_notes": containment_notes_value,
            }
        )

    elif current_step == 3:
        method_key = f"analysis_rca_method_{action_id}"
        default_method = "5 Why" if draft.get("rca_method") == "5why" else "Ishikawa"
        _init_state_value(method_key, default_method)
        method_label = st.radio(
            "RCA method",
            ANALYSIS_RCA_METHODS,
            key=method_key,
            horizontal=True,
        )
        rca_method = "5why" if method_label == "5 Why" else "ishikawa"
        draft["rca_method"] = rca_method

        if rca_method == "5why":
            whys = draft.get("whys", []) or []
            root_key = f"analysis_root_cause_{action_id}"
            _init_state_value(root_key, draft.get("root_cause_index"))
            for idx, item in enumerate(whys):
                st.markdown(f"**Why #{idx + 1}**")
                text_key = f"analysis_why_text_{action_id}_{idx}"
                _init_state_value(text_key, item.get("text", ""))
                why_text = st.text_input(f"Why #{idx + 1} statement", key=text_key)

                status_key = f"analysis_why_status_{action_id}_{idx}"
                _init_state_value(status_key, item.get("status", "Hypothesis"))
                why_status = chip_single_select(
                    "Evidence status",
                    ANALYSIS_EVIDENCE_STATUSES,
                    status_key,
                    columns=3,
                )
                whys[idx] = {"text": why_text, "status": why_status}

                if st.button("🎯 Mark Root Cause", key=f"analysis_root_select_{action_id}_{idx}"):
                    st.session_state[root_key] = idx + 1

                selected_root = st.session_state.get(root_key)
                if selected_root == idx + 1:
                    st.caption("Root cause selected ✅")

                st.divider()

            if st.button("➕ Add next Why", key=f"analysis_add_why_{action_id}"):
                whys.append({"text": "", "status": "Hypothesis"})
                new_idx = len(whys) - 1
                _init_state_value(f"analysis_why_text_{action_id}_{new_idx}", "")
                _init_state_value(f"analysis_why_status_{action_id}_{new_idx}", "Hypothesis")

            draft["whys"] = whys
            draft["root_cause_index"] = st.session_state.get(root_key)

        else:
            ishikawa = draft.get("ishikawa", {}) or {category: [] for category in ISHIKAWA_CATEGORIES}
            tabs = st.tabs(ISHIKAWA_CATEGORIES)
            for category, tab in zip(ISHIKAWA_CATEGORIES, tabs):
                with tab:
                    causes = ishikawa.get(category, [])
                    if causes:
                        for idx, cause in enumerate(causes):
                            cause_text = str(cause.get("cause", "") or "")
                            st.markdown(card(f"<strong>{html.escape(cause_text or '(blank)')}</strong>"), unsafe_allow_html=True)
                            conf_key = f"analysis_ishikawa_conf_{action_id}_{category}_{idx}"
                            _init_state_value(conf_key, cause.get("confidence", "Medium"))
                            confidence = chip_single_select(
                                f"Confidence ({category} #{idx + 1})",
                                ["Low", "Medium", "High"],
                                conf_key,
                                columns=3,
                            )
                            causes[idx]["confidence"] = confidence
                            st.divider()
                    else:
                        st.markdown(muted("No causes yet."), unsafe_allow_html=True)

                    new_key = f"analysis_ishikawa_new_{action_id}_{category}"
                    _init_state_value(new_key, "")
                    new_cause = st.text_input("Add cause", key=new_key)
                    if st.button("Add cause", key=f"analysis_ishikawa_add_{action_id}_{category}"):
                        if new_cause.strip():
                            causes.append({"cause": new_cause.strip(), "confidence": "Medium"})
                            st.session_state[new_key] = ""

                    ishikawa[category] = causes

            draft["ishikawa"] = ishikawa

    else:
        summary_html = _build_analysis_summary_html(draft)
        st.markdown(card(summary_html), unsafe_allow_html=True)

        save_label = "✅ Save analysis to action"
        if st.button(save_label, key=f"analysis_save_{action_id}"):
            base_text = str(draft.get("base_text", "") or "").strip()
            analysis_block = _format_analysis_block(draft)
            updated_text = f"{base_text}\n\n{analysis_block}" if base_text else analysis_block
            update_action_text_field(action_id, analysis_column, updated_text)
            draft["base_text"] = base_text
            st.success("Analysis saved to action ✅")

        if st.button("Back to Action Details", key=f"analysis_back_to_details_{action_id}"):
            _queue_action_details(action_id)

    nav_cols = st.columns(3)
    if current_step > 1:
        if nav_cols[0].button("⬅️ Back", key=f"analysis_nav_back_{action_id}"):
            _set_analysis_step(action_id, current_step - 1)
    if current_step < 4:
        if nav_cols[2].button("Next ➡️", key=f"analysis_nav_next_{action_id}"):
            _set_analysis_step(action_id, current_step + 1)


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


def _render_team_input(
    champions_df,
    champion_options,
    selected_ids: list[int],
    *,
    key: str = "add_action_team_ids",
) -> list[int]:
    if champions_df.empty:
        st.info("Add champions in Global Settings first.")
        return []

    selection = st.multiselect(
        f"Team members (max {MAX_TEAM_MEMBERS})",
        options=list(champion_options.keys()),
        default=selected_ids,
        format_func=champion_options.get,
        key=key,
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
