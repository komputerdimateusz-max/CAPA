from __future__ import annotations

import sqlite3

import pandas as pd

from atm_tracker.actions.db import connect


def list_champions(active_only: bool = True) -> pd.DataFrame:
    con = connect()
    q = "SELECT * FROM champions WHERE deleted = 0"

    if active_only:
        q += " AND is_active = 1"

    q += " ORDER BY name ASC"

    df = pd.read_sql_query(q, con)
    con.close()
    return df


def add_champion(name: str) -> int:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Champion name cannot be empty.")

    con = connect()
    cur = con.cursor()
    try:
        cur.execute(
            """
            INSERT INTO champions (name)
            VALUES (?);
            """,
            (cleaned,),
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
