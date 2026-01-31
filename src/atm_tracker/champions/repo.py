from __future__ import annotations

import sqlite3

import pandas as pd

from atm_tracker.actions.db import connect


def _normalize_spaces(value: str) -> str:
    return " ".join(value.split())


def _normalize_display(first_name: str, last_name: str) -> str:
    first_clean = _normalize_spaces(first_name)
    last_clean = _normalize_spaces(last_name)
    name_display = " ".join(part for part in [first_clean, last_clean] if part).strip()
    return first_clean, last_clean, name_display


def list_champions(
    active_only: bool = True,
    include_inactive: bool | None = None,
    search: str | None = None,
    limit: int = 50,
) -> pd.DataFrame:
    con = connect()
    q = "SELECT * FROM champions WHERE deleted = 0"
    params: list[object] = []

    if include_inactive is None:
        include_inactive = not active_only

    if not include_inactive:
        q += " AND is_active = 1"

    if search:
        q += " AND LOWER(name_display) LIKE ?"
        params.append(f"%{search.lower()}%")

    q += " ORDER BY name_display ASC"

    if include_inactive is not None and not search and limit:
        q += " LIMIT ?"
        params.append(int(limit))

    df = pd.read_sql_query(q, con, params=params)
    con.close()
    if "name_display" in df.columns:
        df["name_display"] = df["name_display"].fillna("").astype(str)
    if "name" in df.columns:
        df["name"] = df["name"].fillna("").astype(str)
    if "name_display" in df.columns and "name" in df.columns:
        df["name_display"] = df.apply(
            lambda row: row["name_display"] or row["name"],
            axis=1,
        )
    return df


def get_champion(champion_id: int) -> dict[str, object] | None:
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM champions WHERE id = ?;", (champion_id,))
    row = cur.fetchone()
    if row is None:
        con.close()
        return None
    columns = [col[0] for col in cur.description]
    con.close()
    return dict(zip(columns, row))


def update_champion(champion_id: int, first_name: str, last_name: str, is_active: bool) -> None:
    cleaned_first, cleaned_last, name_display = _normalize_display(first_name, last_name)
    if not cleaned_first or not cleaned_last:
        raise ValueError("First name and last name are required.")

    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        SELECT id
        FROM champions
        WHERE LOWER(name_display) = LOWER(?) AND id != ?;
        """,
        (name_display, champion_id),
    )
    if cur.fetchone():
        con.close()
        raise ValueError("Champion name already exists.")

    cur.execute(
        """
        UPDATE champions
        SET name = ?, first_name = ?, last_name = ?, name_display = ?, is_active = ?, updated_at = datetime('now')
        WHERE id = ?;
        """,
        (name_display, cleaned_first, cleaned_last, name_display, 1 if is_active else 0, champion_id),
    )
    con.commit()
    con.close()


def add_champion(first_name: str, last_name: str) -> int:
    cleaned_first, cleaned_last, name_display = _normalize_display(first_name, last_name)
    if not cleaned_first or not cleaned_last:
        raise ValueError("First name and last name are required.")
    if not name_display:
        raise ValueError("Champion name cannot be empty.")

    con = connect()
    cur = con.cursor()
    try:
        cur.execute(
            """
            INSERT INTO champions (name, first_name, last_name, name_display)
            VALUES (?, ?, ?, ?);
            """,
            (name_display, cleaned_first, cleaned_last, name_display),
        )
    except sqlite3.IntegrityError as exc:
        con.close()
        raise ValueError("Champion already exists.") from exc

    con.commit()
    new_id = int(cur.lastrowid)
    con.close()
    return new_id


def set_champion_active(champion_id: int, is_active: bool) -> None:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        UPDATE champions
        SET is_active = ?, updated_at = datetime('now')
        WHERE id = ?;
        """,
        (1 if is_active else 0, champion_id),
    )
    con.commit()
    con.close()


def soft_delete_champion(champion_id: int) -> None:
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        UPDATE champions
        SET deleted = 1, updated_at = datetime('now')
        WHERE id = ?;
        """,
        (champion_id,),
    )
    con.commit()
    con.close()
