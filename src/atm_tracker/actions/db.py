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

            created_by TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            deleted INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    # Lightweight migrations for existing DBs: add missing columns only.
    cur.execute("PRAGMA table_info(actions);")
    existing_cols = {row["name"] for row in cur.fetchall()}
    columns_to_add = {
        "created_by": "TEXT NOT NULL DEFAULT ''",
        "updated_by": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT (datetime('now'))",
        "deleted": "INTEGER NOT NULL DEFAULT 0",
    }
    for col_name, col_def in columns_to_add.items():
        if col_name not in existing_cols:
            cur.execute(f"ALTER TABLE actions ADD COLUMN {col_name} {col_def};")

    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_actions_updated_at
        AFTER UPDATE ON actions
        FOR EACH ROW
        BEGIN
            UPDATE actions SET updated_at = datetime('now') WHERE id = NEW.id;
        END;
        """
    )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_line ON actions(line);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_project ON actions(project_or_family);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_deleted ON actions(deleted);")
    con.commit()
    con.close()
