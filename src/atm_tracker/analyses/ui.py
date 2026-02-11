from __future__ import annotations

from datetime import date
import html

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from atm_tracker.actions.db import init_db
from atm_tracker.actions.models import ActionCreate
from atm_tracker.actions.repo import (
    get_actions_days_late,
    insert_action,
    list_actions,
    set_action_analysis_id,
)
from atm_tracker.analyses.repo import (
    A3_FIELDS,
    ANALYSIS_STATUSES,
    ANALYSIS_TYPES,
    EIGHT_D_FIELDS,
    WHY_FIELDS,
    close_analysis,
    generate_analysis_id,
    get_analysis,
    link_action_to_analysis,
    list_analysis_actions,
    list_analyses,
    list_linked_action_ids,
    upsert_analysis,
)
from atm_tracker.champions.repo import list_champions
from atm_tracker.projects.repo import list_projects
from atm_tracker.ui.layout import footer, kpi_row, main_grid, page_header, section
from atm_tracker.ui.styles import card, inject_global_styles, muted, pill


VIEW_OPTIONS = {
    "list": "Analyses list",
    "add": "Add analysis",
    "details": "Analysis details",
}
VIEW_ORDER = list(VIEW_OPTIONS.keys())
VIEW_LABELS = ["Analyses list", "Add analysis"]
ADD_TEMPLATE_KEYS = {
    "5WHY": [
        "a5_problem",
        "a5_why1",
        "a5_why2",
        "a5_why3",
        "a5_why4",
        "a5_why5",
        "a5_root_cause",
        "a5_solution",
    ],
    "8D": [
        "a8_d1_team",
        "a8_d2_problem",
        "a8_d3_ica",
        "a8_d4_root_cause",
        "a8_d5_ca",
        "a8_d6_verify",
        "a8_d7_pa",
        "a8_d8_lessons",
    ],
    "A3": [
        "aa3_plan_problem",
        "aa3_plan_analysis",
        "aa3_plan_target",
        "aa3_plan_root",
        "aa3_do",
        "aa3_check",
        "aa3_act",
    ],
}


def _apply_analysis_details_query_params() -> None:
    params = st.query_params
    view_param = params.get("analysis_view") or params.get("view")
    analysis_param = params.get("analysis_id")

    if isinstance(view_param, list):
        view_value = view_param[0] if view_param else None
    else:
        view_value = view_param

    if isinstance(analysis_param, list):
        analysis_value = analysis_param[0] if analysis_param else None
    else:
        analysis_value = analysis_param

    if analysis_value:
        st.session_state["selected_analysis_id"] = analysis_value
        if view_value in (None, "", "details"):
            st.session_state["analyses_route"] = "details"
        elif view_value in {"list", "add"}:
            st.session_state["analyses_route"] = view_value


def _clear_add_template_keys(template_type: str) -> None:
    for key in ADD_TEMPLATE_KEYS.get(template_type, []):
        st.session_state.pop(key, None)


def _on_add_analysis_type_change() -> None:
    new_type = st.session_state.get("analysis_type_select", ANALYSIS_TYPES[0])
    previous_type = st.session_state.get("analysis_type_selected")
    if previous_type and previous_type != new_type:
        _clear_add_template_keys(previous_type)
    st.session_state["analysis_type_selected"] = new_type
    st.session_state["analysis_type_changed"] = new_type
    st.rerun()


def _render_add_analysis_fields(analysis_type: str) -> dict[str, str]:
    values: dict[str, str] = {}
    if analysis_type == "5WHY":
        values["problem_statement"] = st.text_area(
            "Problem statement",
            value=str(st.session_state.get("a5_problem", "")),
            height=100,
            key="a5_problem",
        )
        for idx, field in enumerate(WHY_FIELDS[1:6], start=1):
            key = f"a5_why{idx}"
            values[field] = st.text_area(
                f"Why {idx}",
                value=str(st.session_state.get(key, "")),
                height=80,
                key=key,
            )
        values["root_cause"] = st.text_area(
            "Root cause",
            value=str(st.session_state.get("a5_root_cause", "")),
            height=100,
            key="a5_root_cause",
        )
        values["solution"] = st.text_area(
            "Solution",
            value=str(st.session_state.get("a5_solution", "")),
            height=100,
            key="a5_solution",
        )
        return values

    if analysis_type == "8D":
        section("8D sections")
        labels = [
            ("a8_d1_team", "d1_team", "D1 Team"),
            ("a8_d2_problem", "d2_problem_description", "D2 Problem description"),
            ("a8_d3_ica", "d3_interim_containment_actions", "D3 Interim containment actions"),
            ("a8_d4_root_cause", "d4_root_cause", "D4 Root cause (Ishikawa + 5Why)"),
            ("a8_d5_ca", "d5_corrective_actions", "D5 Corrective actions"),
            ("a8_d6_verify", "d6_verification_effectiveness", "D6 Verification / Effectiveness"),
            ("a8_d7_pa", "d7_preventive_actions", "D7 Preventive actions"),
            ("a8_d8_lessons", "d8_closure_lessons_learned", "D8 Closure & Lessons learned"),
        ]
        for widget_key, field, label in labels:
            values[field] = st.text_area(
                label,
                value=str(st.session_state.get(widget_key, "")),
                height=120,
                key=widget_key,
            )
        return values

    if analysis_type == "A3":
        section("Plan")
        plan_labels = [
            ("aa3_plan_problem", "a3_plan_problem", "Problem"),
            ("aa3_plan_analysis", "a3_plan_analysis", "Analysis"),
            ("aa3_plan_target", "a3_plan_target", "Target"),
            ("aa3_plan_root", "a3_plan_root_cause", "Root cause"),
        ]
        for widget_key, field, label in plan_labels:
            values[field] = st.text_area(
                label,
                value=str(st.session_state.get(widget_key, "")),
                height=100,
                key=widget_key,
            )
        section("Do")
        values["a3_do_actions_description"] = st.text_area(
            "Actions description",
            value=str(st.session_state.get("aa3_do", "")),
            height=120,
            key="aa3_do",
        )
        section("Check")
        values["a3_check_results_verification"] = st.text_area(
            "Results / Verification",
            value=str(st.session_state.get("aa3_check", "")),
            height=120,
            key="aa3_check",
        )
        section("Act")
        values["a3_act_standardization_lessons"] = st.text_area(
            "Standardization / Lessons learned",
            value=str(st.session_state.get("aa3_act", "")),
            height=120,
            key="aa3_act",
        )
        return values

    return {field: "" for field in WHY_FIELDS + EIGHT_D_FIELDS + A3_FIELDS}


def render_analyses_module() -> None:
    init_db()
    inject_global_styles()

    if "analyses_route" not in st.session_state:
        st.session_state["analyses_route"] = "list"
    if "selected_analysis_id" not in st.session_state:
        st.session_state["selected_analysis_id"] = None

    _apply_analysis_details_query_params()

    selected_view = st.session_state.get("analyses_view_select")
    if selected_view == "Add analysis":
        st.session_state["analyses_route"] = "add"
    elif selected_view == "Analyses list" and st.session_state["analyses_route"] != "details":
        st.session_state["analyses_route"] = "list"

    current_view = st.session_state.get("analyses_route", "list")

    if current_view == "add":
        _render_add()
    elif current_view == "details":
        _render_details()
    else:
        _render_list()


def _render_view_selector() -> None:
    route = st.session_state.get("analyses_route", "list")
    default_idx = 1 if route == "add" else 0
    st.selectbox(
        "View",
        options=VIEW_LABELS,
        index=default_idx,
        key="analyses_view_select",
    )


def _analysis_summary_label(row: pd.Series) -> str:
    title = str(row.get("title") or "").strip() or "Untitled analysis"
    analysis_id = row.get("analysis_id", "")
    analysis_type = row.get("type", "")
    return f"{analysis_id} • {analysis_type} • {title}"


def _render_list() -> None:
    analyses_df = list_analyses()
    links_df = list_analysis_actions()

    page_header(
        "🧩 Analyses",
        "Structured problem-solving analyses linked to actions.",
        actions=_render_view_selector,
    )
    st.divider()

    linked_counts = (
        links_df.groupby("analysis_id")["action_id"].count().to_dict() if not links_df.empty else {}
    )

    kpi_row(
        [
            ("Total analyses", int(len(analyses_df))),
            (
                "Open",
                int((analyses_df["status"].fillna("").str.lower() != "closed").sum()) if not analyses_df.empty else 0,
            ),
            (
                "Closed",
                int((analyses_df["status"].fillna("").str.lower() == "closed").sum()) if not analyses_df.empty else 0,
            ),
        ]
    )
    st.divider()

    with main_grid("wide") as (main,):
        with main:
            type_options = ["All"] + (sorted(analyses_df["type"].dropna().unique().tolist()) or ANALYSIS_TYPES)
            status_options = ["All"] + ANALYSIS_STATUSES
            champion_options = ["All"]
            champions_df = list_champions(active_only=False)
            if not champions_df.empty and "name_display" in champions_df.columns:
                champion_options += champions_df["name_display"].dropna().tolist()
            if not analyses_df.empty and "champion" in analyses_df.columns:
                champion_options += analyses_df["champion"].dropna().tolist()
            champion_options = ["All"] + sorted({value for value in champion_options if value})

            with st.expander("🔍 Filters", expanded=True):
                row1 = st.columns(5)
                with row1[0]:
                    st.text_input(
                        "Search",
                        placeholder="e.g. A3-001 or coating defect",
                        key="analysis_filter_search",
                    )
                with row1[1]:
                    st.selectbox("Status", status_options, key="analysis_filter_status")
                with row1[2]:
                    st.selectbox("Project", ["All"], key="analysis_filter_project")
                with row1[3]:
                    st.selectbox("Champion", champion_options, key="analysis_filter_champion")
                with row1[4]:
                    st.selectbox("Tags", ["All"], key="analysis_filter_tags")

                with st.expander("Advanced filters", expanded=False):
                    row2 = st.columns(4)
                    with row2[0]:
                        st.date_input("Date from", value=None, key="analysis_filter_date_from")
                    with row2[1]:
                        st.date_input("Date to", value=None, key="analysis_filter_date_to")
                    with row2[2]:
                        st.selectbox("Sort", ["Newest", "Oldest"], key="analysis_filter_sort")
                    with row2[3]:
                        st.selectbox("Page size", [25, 50, 100], key="analysis_filter_page_size")
                    _, add_col, apply_col = st.columns([3, 1, 1])
                    with add_col:
                        st.button("Add analysis", on_click=_queue_add_analysis, use_container_width=True)
                    with apply_col:
                        st.button("Apply filters", key="analysis_apply_filters", use_container_width=True)

            filtered = analyses_df.copy()
            selected_type = st.session_state.get("analysis_filter_type", "All")
            selected_champion = st.session_state.get("analysis_filter_champion", "All")
            selected_status = st.session_state.get("analysis_filter_status", "All")
            search_text = st.session_state.get("analysis_filter_search", "")

            if selected_type and selected_type != "All" and "type" in filtered.columns:
                filtered = filtered[filtered["type"] == selected_type]
            if selected_champion and selected_champion != "All" and "champion" in filtered.columns:
                filtered = filtered[filtered["champion"] == selected_champion]
            if selected_status and selected_status != "All" and "status" in filtered.columns:
                filtered = filtered[
                    filtered["status"].fillna("").str.lower() == selected_status.lower()
                ]
            if search_text:
                search_lower = search_text.strip().lower()
                id_matches = (
                    filtered["analysis_id"].astype(str).str.contains(search_lower, case=False, na=False)
                    if "analysis_id" in filtered.columns
                    else pd.Series([], dtype=bool)
                )
                title_matches = (
                    filtered.get("title", pd.Series([]))
                    .astype(str)
                    .str.contains(search_lower, case=False, na=False)
                )
                filtered = filtered[id_matches | title_matches]

            date_from = st.session_state.get("analysis_filter_date_from")
            date_to = st.session_state.get("analysis_filter_date_to")
            if (date_from or date_to) and "created_at" in filtered.columns:
                created_series = pd.to_datetime(filtered["created_at"], errors="coerce").dt.date
                if date_from:
                    filtered = filtered[created_series >= date_from]
                if date_to:
                    filtered = filtered[created_series <= date_to]

            if analyses_df.empty:
                st.markdown(muted("📭 No analyses available yet."), unsafe_allow_html=True)
                st.caption("Showing 0 of 0 analyses")
                footer("Action-to-Money Tracker • Structured analysis before ROI.")
                return

            if filtered.empty:
                st.markdown(muted("📭 No analyses match the current filters."), unsafe_allow_html=True)
                st.caption(f"Showing 0 of {len(analyses_df)} analyses")
                footer("Action-to-Money Tracker • Structured analysis before ROI.")
                return

            section("Analyses")

            page_size = int(st.session_state.get("analysis_filter_page_size", 50))
            display_df = filtered[
                ["analysis_id", "type", "title", "champion", "status"]
            ].head(page_size).copy()
            display_df["linked_actions"] = display_df["analysis_id"].map(linked_counts).fillna(0).astype(int)

            column_labels = {
                "analysis_id": "Analysis ID",
                "title": "Title",
                "type": "Type",
                "champion": "Champion",
                "status": "Status",
                "linked_actions": "Linked actions",
            }
            table_columns = [key for key in column_labels if key in display_df.columns]

            def format_value(value: object) -> str:
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    return "—"
                if isinstance(value, date):
                    return value.strftime("%Y-%m-%d")
                return str(value)

            def open_analysis_details(analysis_id: str) -> None:
                st.session_state["selected_analysis_id"] = analysis_id
                st.session_state["analyses_route"] = "details"
                st.rerun()

            header_cols = st.columns(len(table_columns))
            for col, header in zip(header_cols, [column_labels[col] for col in table_columns]):
                col.markdown(f"**{header}**")

            for row_idx, row in display_df.iterrows():
                row_cols = st.columns(len(table_columns))
                analysis_id = str(row.get("analysis_id") or "")
                for column, col in zip(table_columns, row_cols):
                    if column in {"analysis_id", "title"} and analysis_id:
                        title_value = row.get("title") or f"Analysis {analysis_id}"
                        label = title_value if column == "title" else analysis_id
                        if col.button(
                            str(label),
                            key=f"analysis_{column}_{analysis_id}_{row_idx}",
                            type="tertiary",
                        ):
                            open_analysis_details(analysis_id)
                    elif column == "status":
                        col.markdown(pill(str(row.get("status") or "Open")), unsafe_allow_html=True)
                    else:
                        col.write(format_value(row.get(column)))

            st.caption(f"Showing {len(filtered)} of {len(analyses_df)} analyses")

    footer("Action-to-Money Tracker • Structured analysis before ROI.")


def _render_add() -> None:
    page_header(
        "➕ Add analysis",
        "Capture structured problem analyses (5WHY, 8D, A3).",
        actions=_render_view_selector,
    )
    st.divider()
    kpi_row([])
    st.divider()

    champions_df = list_champions(active_only=True)
    champion_options = (
        [""] + champions_df["name_display"].dropna().tolist()
        if not champions_df.empty and "name_display" in champions_df.columns
        else [""]
    )

    with main_grid("wide") as (main,):
        with main:
            section("New analysis")
            type_choice = st.selectbox(
                "Type *",
                ANALYSIS_TYPES,
                key="analysis_type_select",
                on_change=_on_add_analysis_type_change,
            )
            if "analysis_type_selected" not in st.session_state:
                st.session_state["analysis_type_selected"] = type_choice
            analysis_type = st.session_state.get("analysis_type_selected", type_choice)
            changed_to = st.session_state.pop("analysis_type_changed", None)
            if changed_to:
                st.toast(f"Template changed to: {changed_to}")

            with st.form("add_analysis", clear_on_submit=True):
                title = st.text_input("Title *", placeholder="e.g. Coating defect root cause")
                description = st.text_area(
                    "Description",
                    height=120,
                    placeholder="Context, scope, and expected impact...",
                )
                champion = st.selectbox("Champion", champion_options, index=0)
                status = st.selectbox("Status", ANALYSIS_STATUSES, index=0)

                detail_values = _render_add_analysis_fields(analysis_type)
                submitted = st.form_submit_button("Save analysis")

    if not submitted:
        footer("Action-to-Money Tracker • Structured analysis before ROI.")
        return

    analysis_id = generate_analysis_id(analysis_type)
    created_at = date.today()
    closed_at = created_at if status == "Closed" else None
    payload = {
        "analysis_id": analysis_id,
        "type": analysis_type,
        "title": title.strip(),
        "description": description.strip(),
        "champion": champion.strip() if champion else "",
        "status": status,
        "created_at": created_at.isoformat(),
        "closed_at": closed_at.isoformat() if closed_at else "",
    }
    payload.update(detail_values)
    if not payload["title"]:
        st.error("Title is required.")
        return

    upsert_analysis(payload)
    st.success(f"Saved ✅ (id={analysis_id})")
    footer("Action-to-Money Tracker • Structured analysis before ROI.")


def _render_details() -> None:
    analyses_df = list_analyses()
    if analyses_df.empty:
        page_header("🧩 Analysis Details", "No analyses yet.", actions=_render_view_selector)
        st.info("Add an analysis to view details.")
        footer("Action-to-Money Tracker • Structured analysis before ROI.")
        return

    analysis_lookup = {row["analysis_id"]: _analysis_summary_label(row) for _, row in analyses_df.iterrows()}
    selection = st.selectbox(
        "Analysis",
        options=[None] + list(analysis_lookup.keys()),
        index=_safe_index([None] + list(analysis_lookup.keys()), st.session_state.get("selected_analysis_id")),
        format_func=lambda value: "(select...)" if value is None else analysis_lookup.get(value, value),
        key="analysis_details_select",
    )

    if selection is None:
        st.session_state.pop("selected_analysis_id", None)
        page_header("🧩 Analysis Details", "Select an analysis to view details.", actions=_render_view_selector)
        footer("Action-to-Money Tracker • Structured analysis before ROI.")
        return

    st.session_state["selected_analysis_id"] = selection
    analysis = get_analysis(str(selection))
    if analysis is None:
        st.warning("Selected analysis not found.")
        st.session_state.pop("selected_analysis_id", None)
        st.session_state["analyses_route"] = "list"
        st.rerun()
        return

    analysis_type = str(analysis.get("type") or "")
    title = str(analysis.get("title") or "")
    champion = str(analysis.get("champion") or "")
    status = str(analysis.get("status") or "Open")
    created_at = analysis.get("created_at")
    closed_at = analysis.get("closed_at")
    description = str(analysis.get("description") or "")

    linked_action_ids = list_linked_action_ids(str(selection))
    actions_df = list_actions()
    linked_actions = actions_df[actions_df["id"].isin(linked_action_ids)] if not actions_df.empty else pd.DataFrame()
    linked_actions = linked_actions.copy()
    days_late = get_actions_days_late(linked_action_ids)
    if not linked_actions.empty:
        linked_actions["delay_days"] = linked_actions["id"].map(days_late).fillna(0).astype(int)

    page_header(
        f"🧩 Analysis {selection}",
        "Review analysis details and linked actions.",
        actions=_render_view_selector,
    )
    st.divider()
    kpi_row(
        [
            ("Linked actions", int(len(linked_action_ids))),
            ("Status", status),
        ]
    )
    st.divider()

    with main_grid("focus") as (main, side):
        with main:
            section("Analysis form")
            with st.form("analysis_edit"):
                updated_title = st.text_input("Title *", value=title)
                updated_description = st.text_area("Description", value=description, height=120)
                updated_champion = _render_champion_select(champion)
                updated_status = st.selectbox(
                    "Status",
                    ANALYSIS_STATUSES,
                    index=_safe_index(ANALYSIS_STATUSES, status),
                )

                detail_values = _render_analysis_fields(analysis_type, analysis, "edit")
                saved = st.form_submit_button("Save changes")

            if saved:
                resolved_closed_at = closed_at
                if updated_status == "Closed" and not closed_at:
                    resolved_closed_at = date.today()
                if updated_status != "Closed":
                    resolved_closed_at = ""
                payload = {
                    "analysis_id": selection,
                    "type": analysis_type,
                    "title": updated_title.strip(),
                    "description": updated_description.strip(),
                    "champion": updated_champion,
                    "status": updated_status,
                    "created_at": _format_date(created_at),
                    "closed_at": _format_date(resolved_closed_at),
                }
                payload.update(detail_values)
                if not payload["title"]:
                    st.error("Title is required.")
                else:
                    upsert_analysis(payload)
                    st.success("Analysis updated ✅")
                    st.rerun()

            section("Linked actions")
            if linked_actions.empty:
                st.markdown(muted("No actions linked yet."), unsafe_allow_html=True)
            else:
                display = linked_actions[
                    ["id", "title", "status", "champion", "target_date", "delay_days"]
                ].rename(columns={"id": "action_id"})
                st.dataframe(display, use_container_width=True)

            section("Action integration")
            _render_add_action(selection)
            _render_link_action(selection, linked_action_ids)

        with side:
            section("Analysis summary")
            summary_items = [
                f"<li><strong>Type:</strong> {html.escape(analysis_type or '(not set)')}</li>",
                f"<li><strong>Champion:</strong> {html.escape(champion or '(unassigned)')}</li>",
                f"<li><strong>Status:</strong> {pill(status)}</li>",
                f"<li><strong>Created:</strong> {html.escape(str(created_at or '(not set)'))}</li>",
                f"<li><strong>Closed:</strong> {html.escape(str(closed_at or '(not set)'))}</li>",
            ]
            st.markdown(card(f"<ul class='ds-list'>{''.join(summary_items)}</ul>"), unsafe_allow_html=True)

            section("Actions")
            st.button("← Back to list", on_click=_queue_analyses_list, use_container_width=True)
            if status != "Closed":
                if st.button("Close analysis", use_container_width=True):
                    close_analysis(str(selection), date.today())
                    st.success("Analysis closed ✅")
                    st.rerun()
    footer("Action-to-Money Tracker • Structured analysis before ROI.")


def _render_analysis_fields(analysis_type: str, analysis: dict[str, object], key_prefix: str) -> dict[str, str]:
    values: dict[str, str] = {}
    if analysis_type == "5WHY":
        values["problem_statement"] = st.text_area(
            "Problem statement",
            value=str(analysis.get("problem_statement") or ""),
            height=100,
            key=f"{key_prefix}_problem_statement",
        )
        for idx, field in enumerate(WHY_FIELDS[1:6], start=1):
            values[field] = st.text_area(
                f"Why {idx}",
                value=str(analysis.get(field) or ""),
                height=80,
                key=f"{key_prefix}_{field}",
            )
        values["root_cause"] = st.text_area(
            "Root cause",
            value=str(analysis.get("root_cause") or ""),
            height=100,
            key=f"{key_prefix}_root_cause",
        )
        values["solution"] = st.text_area(
            "Solution",
            value=str(analysis.get("solution") or ""),
            height=100,
            key=f"{key_prefix}_solution",
        )
        return values

    if analysis_type == "8D":
        section("8D sections")
        labels = [
            ("d1_team", "D1 Team"),
            ("d2_problem_description", "D2 Problem description"),
            ("d3_interim_containment_actions", "D3 Interim containment actions"),
            ("d4_root_cause", "D4 Root cause (Ishikawa + 5Why)"),
            ("d5_corrective_actions", "D5 Corrective actions"),
            ("d6_verification_effectiveness", "D6 Verification / Effectiveness"),
            ("d7_preventive_actions", "D7 Preventive actions"),
            ("d8_closure_lessons_learned", "D8 Closure & Lessons learned"),
        ]
        for field, label in labels:
            values[field] = st.text_area(
                label,
                value=str(analysis.get(field) or ""),
                height=120,
                key=f"{key_prefix}_{field}",
            )
        return values

    if analysis_type == "A3":
        section("Plan")
        plan_labels = [
            ("a3_plan_problem", "Problem"),
            ("a3_plan_analysis", "Analysis"),
            ("a3_plan_target", "Target"),
            ("a3_plan_root_cause", "Root cause"),
        ]
        for field, label in plan_labels:
            values[field] = st.text_area(
                label,
                value=str(analysis.get(field) or ""),
                height=100,
                key=f"{key_prefix}_{field}",
            )
        section("Do")
        values["a3_do_actions_description"] = st.text_area(
            "Actions description",
            value=str(analysis.get("a3_do_actions_description") or ""),
            height=120,
            key=f"{key_prefix}_a3_do_actions_description",
        )
        section("Check")
        values["a3_check_results_verification"] = st.text_area(
            "Results / Verification",
            value=str(analysis.get("a3_check_results_verification") or ""),
            height=120,
            key=f"{key_prefix}_a3_check_results_verification",
        )
        section("Act")
        values["a3_act_standardization_lessons"] = st.text_area(
            "Standardization / Lessons learned",
            value=str(analysis.get("a3_act_standardization_lessons") or ""),
            height=120,
            key=f"{key_prefix}_a3_act_standardization_lessons",
        )
        return values

    return {field: str(analysis.get(field) or "") for field in WHY_FIELDS + EIGHT_D_FIELDS + A3_FIELDS}


def _render_add_action(analysis_id: str) -> None:
    with st.expander("Add new action", expanded=False):
        projects_df = list_projects(include_inactive=False)
        champion_df = list_champions(active_only=True)
        champion_options = (
            [""] + champion_df["name_display"].dropna().tolist()
            if not champion_df.empty and "name_display" in champion_df.columns
            else [""]
        )

        with st.form(f"analysis_add_action_{analysis_id}"):
            title = st.text_input("Title *", placeholder="e.g. Replace coating nozzle")
            project = _render_project_input(projects_df)
            champion = st.selectbox("Champion", champion_options, index=0)
            status = st.selectbox("Status", ["OPEN", "IN_PROGRESS", "CLOSED"], index=0)
            created_at = st.date_input("Created at", value=date.today())
            target_date = st.date_input("Target Date", value=None)
            closed_at = st.date_input("Closed at", value=None)
            tags = st.text_input("Tags (comma-separated)", placeholder="scrap, downtime")

            st.markdown("**Action cost (MVP)**")
            cost_internal_hours = st.number_input("Internal hours", min_value=0.0, value=0.0, step=0.5)
            cost_external_eur = st.number_input("External cost (€)", min_value=0.0, value=0.0, step=10.0)
            cost_material_eur = st.number_input("Material cost (€)", min_value=0.0, value=0.0, step=10.0)
            description = st.text_area("Description", height=120)

            submitted = st.form_submit_button("Create action")

        if not submitted:
            return

        try:
            action = ActionCreate(
                title=title.strip(),
                description=description.strip(),
                project_or_family=project.strip(),
                owner="",
                champion=champion.strip(),
                status=status,
                created_at=created_at,
                target_date=target_date,
                closed_at=closed_at,
                cost_internal_hours=cost_internal_hours,
                cost_external_eur=cost_external_eur,
                cost_material_eur=cost_material_eur,
                tags=tags.strip(),
                analysis_id=analysis_id,
            )
        except ValidationError as exc:
            st.error("Validation error — fix inputs:")
            st.code(str(exc))
            return

        new_id = insert_action(action)
        link_action_to_analysis(analysis_id, new_id)
        set_action_analysis_id(new_id, analysis_id)
        st.success(f"Action created ✅ (id={new_id})")
        st.rerun()


def _render_link_action(analysis_id: str, linked_action_ids: list[int]) -> None:
    with st.expander("Link existing action", expanded=False):
        actions_df = list_actions()
        if actions_df.empty:
            st.info("No actions available to link.")
            return
        actions_df = actions_df.copy()
        actions_df["label"] = actions_df.apply(
            lambda row: f"{row['id']} • {row.get('project_or_family', '')} • {row.get('title', '')}",
            axis=1,
        )
        available = actions_df[~actions_df["id"].isin(linked_action_ids)] if linked_action_ids else actions_df
        if available.empty:
            st.info("All actions are already linked.")
            return
        options = available["id"].tolist()
        labels = dict(zip(available["id"], available["label"]))
        selected_action = st.selectbox(
            "Select action to link",
            options=options,
            format_func=lambda value: labels.get(value, value),
        )
        if st.button("Link action", use_container_width=True):
            link_action_to_analysis(analysis_id, int(selected_action))
            set_action_analysis_id(int(selected_action), analysis_id)
            st.success("Action linked ✅")
            st.rerun()


def _render_champion_select(current: str) -> str:
    champions_df = list_champions(active_only=False)
    options = [""]
    if not champions_df.empty and "name_display" in champions_df.columns:
        options += champions_df["name_display"].dropna().tolist()
    options = [""] + sorted({opt for opt in options if opt})
    if current and current not in options:
        options.append(current)
    selection = st.selectbox(
        "Champion",
        options,
        index=_safe_index(options, current),
    )
    return selection


def _render_project_input(projects_df: pd.DataFrame) -> str:
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
    return "" if selection == "(none)" else selection


def _queue_add_analysis() -> None:
    st.session_state["analyses_route"] = "add"


def _queue_analyses_list() -> None:
    st.session_state["analyses_route"] = "list"
    st.session_state["selected_analysis_id"] = None


def _safe_index(options: list[object], value: object) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0


def _format_date(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if value:
        return str(value)
    return ""


__all__ = ["render_analyses_module"]
