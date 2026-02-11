from __future__ import annotations

import html

import streamlit as st

BASE_CSS = """
<style>
:root {
    --ds-primary: #1F2937;
    --ds-secondary: #6B7280;
    --ds-bg: #F9FAFB;
    --ds-card-bg: #FFFFFF;
    --ds-border: #E5E7EB;
    --ds-success: #16A34A;
    --ds-warning: #D97706;
    --ds-danger: #DC2626;
    --ds-neutral: #6B7280;
}

.stApp {
    background-color: var(--ds-bg);
    color: var(--ds-primary);
}

.ds-page-layout {
    max-width: 1300px;
    margin: 0 auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.ds-page-header {
    margin-bottom: 0;
}

.ds-page-header .stCaption {
    color: var(--ds-secondary);
}

.ds-card {
    background: var(--ds-card-bg);
    border: 1px solid var(--ds-border);
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.ds-muted {
    color: var(--ds-secondary);
    font-size: 0.9rem;
}

.ds-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 4px 10px;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}

.ds-pill--success {
    background: #DCFCE7;
    color: var(--ds-success);
}

.ds-pill--warning {
    background: #FEF3C7;
    color: var(--ds-warning);
}

.ds-pill--danger {
    background: #FEE2E2;
    color: var(--ds-danger);
}

.ds-pill--neutral {
    background: #F3F4F6;
    color: var(--ds-neutral);
}

.ds-table {
    width: 100%;
    border-collapse: collapse;
}

.ds-table th {
    text-align: left;
    font-size: 0.85rem;
    color: var(--ds-secondary);
    padding-bottom: 8px;
    border-bottom: 1px solid var(--ds-border);
}

.ds-table td {
    padding: 10px 0;
    border-top: 1px solid var(--ds-border);
    vertical-align: top;
}

.ds-table tbody tr:hover {
    background: #F3F4F6;
}

.ds-link {
    color: var(--ds-primary);
    font-weight: 600;
    text-decoration: none;
}

.ds-link:hover {
    text-decoration: underline;
}

.ds-list {
    margin: 0;
    padding-left: 1.1rem;
}

.ds-list li {
    margin-bottom: 0.35rem;
}

.stApp h2,
.stApp h3 {
    margin-top: 0;
    margin-bottom: 0.5rem;
}

.stApp h2:first-child,
.stApp h3:first-child {
    margin-top: 0;
}

div[data-testid="stMetric"] {
    background: var(--ds-card-bg);
    border: 1px solid var(--ds-border);
    border-radius: 12px;
    padding: 16px;
    min-height: 110px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

div[data-testid="stMetricValue"] {
    font-size: 1.75rem;
}

div[data-testid="stMetricLabel"] {
    color: var(--ds-secondary);
}

div[data-baseweb="input"],
div[data-baseweb="select"],
div[data-baseweb="textarea"] {
    border-radius: 10px;
}

div[data-baseweb="input"] input,
div[data-baseweb="select"] div,
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div {
    min-height: 40px;
}

.stButton > button,
.stDownloadButton > button,
button[kind] {
    min-height: 40px;
    border-radius: 10px;
}

.stDataFrame [role="row"]:hover {
    background-color: #f8fafc !important;
}
</style>
"""


def inject_global_styles() -> None:
    """Inject shared design system styles."""
    st.markdown(BASE_CSS, unsafe_allow_html=True)


def card(html_or_markdown: str, *, unsafe_html: bool = True) -> str:
    """Wrap content inside a design system card."""
    content = html_or_markdown if unsafe_html else html.escape(html_or_markdown)
    return f"<div class='ds-card'>{content}</div>"


def muted(text: str) -> str:
    """Return muted caption text."""
    return f"<span class='ds-muted'>{html.escape(text)}</span>"


def _format_status_label(status: str) -> str:
    if not status:
        return "Open"
    normalized = status.replace("_", " ").strip()
    return " ".join(word.capitalize() for word in normalized.split())


def pill(status: str) -> str:
    """Return a status pill with semantic coloring."""
    normalized = str(status or "").strip().lower().replace("_", " ")
    if normalized in {"closed", "success"}:
        variant = "success"
    elif normalized in {"in progress", "ongoing"}:
        variant = "warning"
    elif normalized == "overdue":
        variant = "danger"
    else:
        variant = "neutral"

    label = _format_status_label(status or "Open")
    return f"<span class='ds-pill ds-pill--{variant}'>{html.escape(label)}</span>"
