from __future__ import annotations

import os
from datetime import date
from typing import Any

import pandas as pd
import requests

DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def api_enabled() -> bool:
    return os.getenv("USE_API", "false").lower() == "true"


def _request(method: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{DEFAULT_API_BASE_URL}{path}"
    response = requests.request(method, url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def _normalize_action_payload(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": action.get("id"),
        "title": action.get("title"),
        "description": action.get("description"),
        "project_or_family": action.get("project_name") or "",
        "champion": action.get("champion_name") or action.get("owner") or "",
        "owner": action.get("owner"),
        "status": action.get("status"),
        "created_at": action.get("created_at"),
        "target_date": action.get("due_date"),
        "closed_at": action.get("closed_at"),
        "days_late": action.get("days_late", 0),
        "tags": action.get("tags", []),
    }


def list_actions(
    status: list[str] | None = None,
    champion: str | None = None,
    owner: str | None = None,
    project: str | None = None,
    q: str | None = None,
    tags: list[str] | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    sort: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[pd.DataFrame, int]:
    params: dict[str, Any] = {
        "champion": champion,
        "owner": owner,
        "project": project,
        "q": q,
        "sort": sort,
        "limit": limit,
        "offset": offset,
    }
    if status:
        params["status"] = status
    if tags:
        params["tags"] = tags
    if due_from:
        params["from"] = due_from.isoformat()
    if due_to:
        params["to"] = due_to.isoformat()

    payload = _request("GET", "/api/actions", params=params)
    items = [_normalize_action_payload(item) for item in payload.get("items", [])]
    df = pd.DataFrame(items)

    for col in ["created_at", "target_date", "closed_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
            df[col] = df[col].apply(lambda value: value if pd.notna(value) else None)

    return df, int(payload.get("total", len(df)))


def get_action(action_id: int) -> dict[str, Any]:
    payload = _request("GET", f"/api/actions/{action_id}")
    return _normalize_action_payload(payload)


def delete_action(action_id: int) -> None:
    url = f"{DEFAULT_API_BASE_URL}/api/actions/{action_id}"
    response = requests.delete(url, timeout=10)
    response.raise_for_status()


def get_actions_kpi(
    status: list[str] | None = None,
    champion: str | None = None,
    owner: str | None = None,
    project: str | None = None,
    q: str | None = None,
    tags: list[str] | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "champion": champion,
        "owner": owner,
        "project": project,
        "q": q,
    }
    if status:
        params["status"] = status
    if tags:
        params["tags"] = tags
    if due_from:
        params["from"] = due_from.isoformat()
    if due_to:
        params["to"] = due_to.isoformat()

    return _request("GET", "/api/kpi/actions", params=params)
