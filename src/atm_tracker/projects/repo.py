from __future__ import annotations

import sqlite3

import pandas as pd

from atm_tracker.actions.db import connect


def _normalize_spaces(value: str) -> str:
    return " ".join(value.split())


def _normalize_code(value: str) -> str:
    return value.strip()


def list_projects(
    include_inactive: bool = True,
    search: str | None = None,
    limit: int = 50,
) -> pd.DataFrame:
    con = connect()
    q = "SELECT * FROM projects WHERE deleted = 0"
    params: list[object] = []

    if not include_inactive:
        q += " AND is_active = 1"

    if search:
        q += " AND (LOWER(name) LIKE ? OR LOWER(code) LIKE ?)"
        term = f"%{search.lower()}%"
        params.extend([term, term])

    q += " ORDER BY name ASC"

    if not search and limit:
        q += " LIMIT ?"
        params.append(int(limit))

    df = pd.read_sql_query(q, con, params=params)
    con.close()
    if "name" in df.columns:
        df["name"] = df["name"].fillna("").astype(str)
    if "code" in df.columns:
        df["code"] = df["code"].fillna("").astype(str)
    return df


def add_project(name: str, code: str = "") -> int:
    cleaned_name = _normalize_spaces(name)
    cleaned_code = _normalize_code(code)
    if not cleaned_name:
        raise ValueError("Project name is required.")

    con = connect()
    cur = con.cursor()
    try:
        cur.execute(
            """
            INSERT INTO projects (name, code)
            VALUES (?, ?);
            """,
            (cleaned_name, cleaned_code),
        )
    except sqlite3.IntegrityError as exc:
        con.close()
        raise ValueError("Project name already exists.") from exc

    con.commit()
    new_id = int(cur.lastrowid)
    con.close()
    return new_id


def get_project(project_id: int) -> dict[str, object] | None:
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
    row = cur.fetchone()
    if row is None:
        con.close()
        return None
    columns = [col[0] for col in cur.description]
    con.close()
    return dict(zip(columns, row))


def update_project(project_id: int, name: str, code: str, is_active: bool) -> None:
    cleaned_name = _normalize_spaces(name)
    cleaned_code = _normalize_code(code)
    if not cleaned_name:
        raise ValueError("Project name is required.")

    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        SELECT id
        FROM projects
        WHERE LOWER(name) = LOWER(?) AND id != ?;
        """,
        (cleaned_name, project_id),
    )
    if cur.fetchone():
        con.close()
        raise ValueError("Project name already exists.")

    cur.execute(
        """
        UPDATE projects
        SET name = ?, code = ?, is_active = ?, updated_at = datetime('now')
        WHERE id = ?;
        """,
        (cleaned_name, cleaned_code, 1 if is_active else 0, project_id),
    )
    con.commit()
    con.close()


def soft_delete_project(project_id: int) -> None:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        UPDATE projects
        SET deleted = 1, updated_at = datetime('now')
        WHERE id = ?;
        """,
        (project_id,),
    )
    con.commit()
    con.close()
