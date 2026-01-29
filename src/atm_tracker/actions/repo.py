from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any, Optional

import pandas as pd

from atm_tracker.actions.db import connect
from atm_tracker.actions.models import ActionCreate


def _d(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def insert_action(a: ActionCreate) -> int:
    con = connect()
    cur = con.cursor()

    owner_value = a.champion or ""
    cur.execute(
        """
        INSERT INTO actions (
            title, description, line, project_or_family, owner, champion,
            status, created_at, implemented_at, closed_at,
            cost_internal_hours, cost_external_eur, cost_material_eur,
            tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            a.title,
            a.description,
            a.line,
            a.project_or_family,
            owner_value,
            a.champion,
            a.status,
            a.created_at.isoformat(),
            _d(a.implemented_at),
            _d(a.closed_at),
            float(a.cost_internal_hours),
            float(a.cost_external_eur),
            float(a.cost_material_eur),
            a.tags,
        ),
    )
    con.commit()
    new_id = int(cur.lastrowid)
    con.close()
    return new_id


def list_actions(
    status: Optional[str] = None,
    line: Optional[str] = None,
    project_or_family: Optional[str] = None,
    search: Optional[str] = None,
    include_deleted: bool = False,
) -> pd.DataFrame:
    con = connect()
    q = "SELECT * FROM actions"
    where: list[str] = []
    params: list[Any] = []

    if not include_deleted:
        where.append("deleted = 0")
    if status:
        where.append("status = ?")
        params.append(status)
    if line:
        where.append("line = ?")
        params.append(line)
    if project_or_family:
        where.append("project_or_family = ?")
        params.append(project_or_family)
    if search:
        where.append("(title LIKE ? OR description LIKE ? OR owner LIKE ? OR champion LIKE ?)")
        s = f"%{search}%"
        params.extend([s, s, s, s])

    if where:
        q += " WHERE " + " AND ".join(where)

    q += " ORDER BY id DESC"

    df = pd.read_sql_query(q, con, params=params)
    con.close()

    if "champion" in df.columns and "owner" in df.columns:
        df["champion"] = df["champion"].fillna("").astype(str)
        df["owner"] = df["owner"].fillna("").astype(str)
        df["champion"] = df.apply(
            lambda row: row["champion"] or row["owner"],
            axis=1,
        )

    # normalize dates for UI
    for col in ["created_at", "implemented_at", "closed_at", "updated_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    return df


def update_status(action_id: int, status: str, closed_at: Optional[date]) -> None:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        UPDATE actions
        SET status = ?, closed_at = ?, updated_at = datetime('now')
        WHERE id = ?;
        """,
        (status, closed_at.isoformat() if closed_at else None, action_id),
    )
    con.commit()
    con.close()


def soft_delete_action(action_id: int) -> None:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        UPDATE actions
        SET deleted = 1, updated_at = datetime('now')
        WHERE id = ?;
        """,
        (action_id,),
    )
    con.commit()
    con.close()
