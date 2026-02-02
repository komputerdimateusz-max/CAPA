from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

from action_tracking.config import get_bool_env, get_env

DEFAULT_API_BASE_URL = get_env("API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT_S = 5


class ApiClientError(RuntimeError):
    pass


def api_enabled() -> bool:
    return get_bool_env("USE_API", False)


def _request(method: str, path: str, params: dict[str, Any] | None = None) -> requests.Response:
    url = f"{DEFAULT_API_BASE_URL}{path}"
    try:
        response = requests.request(method, url, params=params, timeout=DEFAULT_TIMEOUT_S)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        message = "API unavailable. Check API_BASE_URL and ensure the backend is running."
        raise ApiClientError(message) from exc


def _request_json(method: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = _request(method, path, params=params)
    try:
        return response.json()
    except ValueError as exc:
        raise ApiClientError("API returned an invalid response.") from exc


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed.date()
    return None


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
) -> tuple[list[dict[str, Any]], int]:
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

    payload = _request_json("GET", "/api/actions", params=params)
    items = [_normalize_action_payload(item) for item in payload.get("items", [])]
    for item in items:
        item["created_at"] = _parse_date(item.get("created_at"))
        item["target_date"] = _parse_date(item.get("target_date"))
        item["closed_at"] = _parse_date(item.get("closed_at"))
    return items, int(payload.get("total", len(items)))


def get_action(action_id: int) -> dict[str, Any]:
    payload = _request_json("GET", f"/api/actions/{action_id}")
    action = _normalize_action_payload(payload)
    action["created_at"] = _parse_date(action.get("created_at"))
    action["target_date"] = _parse_date(action.get("target_date"))
    action["closed_at"] = _parse_date(action.get("closed_at"))
    return action


def delete_action(action_id: int) -> None:
    _request("DELETE", f"/api/actions/{action_id}")


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

    return _request_json("GET", "/api/kpi/actions", params=params)
