from __future__ import annotations

from atm_tracker.actions.db import init_db
from atm_tracker.settings.ui import render_projects_admin_section
from atm_tracker.ui.layout import footer, page_header
from atm_tracker.ui.styles import inject_global_styles


def render_projects_module() -> None:
    init_db()
    inject_global_styles()

    page_header("📁 Projects", "Create and maintain the project catalog used across Actions and Analyses.")
    render_projects_admin_section()
    footer("Action-to-Money Tracker • Clear project structure keeps attribution reliable.")
