from __future__ import annotations

import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    # Keep DB outside src, in repo root /data
    root = Path.cwd()
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "actions.db"


def connect() -> sqlite3.Connection:
    db_path = get_db_path()
    con = sqlite3.connect(db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = connect()
    cur = con.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            line TEXT NOT NULL,
            project_or_family TEXT NOT NULL,
            owner TEXT NOT NULL,
            champion TEXT NOT NULL,

            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            implemented_at TEXT,
            closed_at TEXT,

            cost_internal_hours REAL NOT NULL,
            cost_external_eur REAL NOT NULL,
            cost_material_eur REAL NOT NULL,

            tags TEXT NOT NULL,

            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_line ON actions(line);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_project ON actions(project_or_family);")
    con.commit()
    con.close()
