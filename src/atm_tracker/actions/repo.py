from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any, Optional

import pandas as pd

from atm_tracker.actions.db import connect
from atm_tracker.actions.models import ActionCreate

MAX_TEAM_MEMBERS = 15
TASK_STATUSES = ["OPEN", "IN_PROGRESS", "DONE"]
_UNSET = object()


def _d(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _normalize_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
            df[col] = df[col].apply(lambda value: value if pd.notna(value) else None)
    return df


def insert_action(a: ActionCreate) -> int:
    con = connect()
    cur = con.cursor()

    owner_value = a.champion or ""
    cur.execute(
        """
        INSERT INTO actions (
            title, description, line, project_or_family, owner, champion,
            status, created_at, implemented_at, target_date, closed_at,
            cost_internal_hours, cost_external_eur, cost_material_eur,
            tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
            None,
            _d(a.target_date),
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
    df = _normalize_dates(
        df,
        ["created_at", "implemented_at", "target_date", "closed_at", "updated_at"],
    )

    return df


def get_action(action_id: int) -> Optional[pd.Series]:
    con = connect()
    df = pd.read_sql_query(
        "SELECT * FROM actions WHERE id = ? AND deleted = 0;",
        con,
        params=(action_id,),
    )
    con.close()
    if df.empty:
        return None
    df = _normalize_dates(
        df,
        ["created_at", "implemented_at", "target_date", "closed_at", "updated_at"],
    )
    row = df.iloc[0].copy()
    champion = str(row.get("champion", "") or "")
    owner = str(row.get("owner", "") or "")
    if champion or owner:
        row["champion"] = champion or owner
    return row


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


def list_tasks(action_id: int, include_deleted: bool = False) -> pd.DataFrame:
    con = connect()
    q = "SELECT * FROM action_tasks WHERE action_id = ?"
    params: list[Any] = [action_id]
    if not include_deleted:
        q += " AND deleted = 0"
    q += """
        ORDER BY
            CASE
                WHEN status IN ('OPEN', 'IN_PROGRESS') THEN 0
                ELSE 1
            END,
            sort_order ASC,
            id ASC;
        """
    df = pd.read_sql_query(q, con, params=params)
    con.close()
    df = _normalize_dates(df, ["created_at", "target_date", "done_at", "updated_at"])
    return df


def add_task(
    action_id: int,
    title: str,
    description: str,
    assignee_champion_id: Optional[int],
    status: str,
    target_date: Optional[date],
) -> int:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO action_tasks (
            action_id,
            title,
            description,
            assignee_champion_id,
            status,
            target_date
        ) VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            action_id,
            title,
            description,
            assignee_champion_id,
            status,
            _d(target_date),
        ),
    )
    con.commit()
    new_id = int(cur.lastrowid)
    con.close()
    return new_id


def update_task(
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    assignee_champion_id: Optional[int] | object = _UNSET,
    status: Optional[str] = None,
    target_date: Optional[date] | object = _UNSET,
) -> None:
    fields: list[str] = []
    params: list[Any] = []

    if title is not None:
        fields.append("title = ?")
        params.append(title)
    if description is not None:
        fields.append("description = ?")
        params.append(description)
    if assignee_champion_id is not _UNSET:
        fields.append("assignee_champion_id = ?")
        params.append(None if assignee_champion_id is None else int(assignee_champion_id))
    if status is not None:
        fields.append("status = ?")
        params.append(status)
        fields.append(
            """
            done_at = CASE
                WHEN ? = 'DONE' THEN COALESCE(done_at, date('now'))
                ELSE NULL
            END
            """.strip()
        )
        params.append(status)
    if target_date is not _UNSET:
        fields.append("target_date = ?")
        params.append(_d(target_date if target_date is not None else None))

    if not fields:
        return

    fields.append("updated_at = datetime('now')")
    params.append(task_id)

    con = connect()
    cur = con.cursor()
    cur.execute(
        f"""
        UPDATE action_tasks
        SET {", ".join(fields)}
        WHERE id = ?;
        """,
        tuple(params),
    )
    con.commit()
    con.close()


def soft_delete_task(task_id: int) -> None:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        UPDATE action_tasks
        SET deleted = 1, updated_at = datetime('now')
        WHERE id = ?;
        """,
        (task_id,),
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


def get_action_team(action_id: int) -> list[int]:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        SELECT champion_id
        FROM action_team_members
        WHERE action_id = ? AND deleted = 0
        ORDER BY champion_id;
        """,
        (action_id,),
    )
    rows = cur.fetchall()
    con.close()
    return [int(row[0]) for row in rows]


def set_action_team(action_id: int, champion_ids: list[int]) -> None:
    cleaned: list[int] = []
    seen: set[int] = set()
    for champion_id in champion_ids:
        if champion_id is None:
            continue
        cid = int(champion_id)
        if cid not in seen:
            seen.add(cid)
            cleaned.append(cid)

    if len(cleaned) > MAX_TEAM_MEMBERS:
        raise ValueError(f"Team members cannot exceed {MAX_TEAM_MEMBERS}.")

    con = connect()
    cur = con.cursor()
    try:
        cur.execute(
            """
            SELECT champion_id, deleted
            FROM action_team_members
            WHERE action_id = ?;
            """,
            (action_id,),
        )
        existing_rows = cur.fetchall()
        existing_any = {int(row[0]) for row in existing_rows}
        existing_active = {int(row[0]) for row in existing_rows if int(row[1]) == 0}

        to_remove = existing_active - set(cleaned)

        for champion_id in to_remove:
            cur.execute(
                """
                UPDATE action_team_members
                SET deleted = 1, updated_at = datetime('now')
                WHERE action_id = ? AND champion_id = ? AND deleted = 0;
                """,
                (action_id, champion_id),
            )

        for champion_id in cleaned:
            if champion_id in existing_any:
                cur.execute(
                    """
                    UPDATE action_team_members
                    SET deleted = 0, updated_at = datetime('now')
                    WHERE action_id = ? AND champion_id = ?;
                    """,
                    (action_id, champion_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO action_team_members (action_id, champion_id)
                    VALUES (?, ?);
                    """,
                    (action_id, champion_id),
                )

        con.commit()
    finally:
        con.close()


def get_action_team_sizes(action_ids: list[int]) -> dict[int, int]:
    if not action_ids:
        return {}

    placeholders = ",".join(["?"] * len(action_ids))
    con = connect()
    cur = con.cursor()
    cur.execute(
        f"""
        SELECT action_id, COUNT(*) as team_size
        FROM action_team_members
        WHERE deleted = 0 AND action_id IN ({placeholders})
        GROUP BY action_id;
        """,
        tuple(action_ids),
    )
    rows = cur.fetchall()
    con.close()
    return {int(row[0]): int(row[1]) for row in rows}


def get_task_counts(action_ids: list[int]) -> dict[int, dict[str, int]]:
    if not action_ids:
        return {}
    placeholders = ",".join(["?"] * len(action_ids))
    con = connect()
    cur = con.cursor()
    cur.execute(
        f"""
        SELECT action_id,
               COUNT(*) as total_count,
               SUM(CASE WHEN status = 'DONE' THEN 1 ELSE 0 END) as done_count
        FROM action_tasks
        WHERE deleted = 0 AND action_id IN ({placeholders})
        GROUP BY action_id;
        """,
        tuple(action_ids),
    )
    rows = cur.fetchall()
    con.close()
    return {
        int(row[0]): {"total": int(row[1] or 0), "done": int(row[2] or 0)}
        for row in rows
    }


def get_actions_progress_map(action_ids: list[int]) -> dict[int, int]:
    if not action_ids:
        return {}
    placeholders = ",".join(["?"] * len(action_ids))
    con = connect()
    cur = con.cursor()
    cur.execute(
        f"""
        SELECT a.id,
               a.status,
               COUNT(t.id) as total_count,
               SUM(CASE WHEN t.status = 'DONE' THEN 1 ELSE 0 END) as done_count
        FROM actions a
        LEFT JOIN action_tasks t
            ON a.id = t.action_id AND t.deleted = 0
        WHERE a.id IN ({placeholders})
        GROUP BY a.id, a.status;
        """,
        tuple(action_ids),
    )
    rows = cur.fetchall()
    con.close()
    progress_map: dict[int, int] = {}
    for row in rows:
        action_id = int(row[0])
        status = str(row[1] or "")
        total = int(row[2] or 0)
        done = int(row[3] or 0)
        if status == "CLOSED":
            progress = 100
        elif total == 0:
            progress = 0
        else:
            progress = int(round(done / total * 100))
        progress_map[action_id] = progress
    return progress_map
