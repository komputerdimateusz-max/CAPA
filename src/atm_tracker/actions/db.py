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
            target_date TEXT,
            closed_at TEXT,

            cost_internal_hours REAL NOT NULL,
            cost_external_eur REAL NOT NULL,
            cost_material_eur REAL NOT NULL,

            tags TEXT NOT NULL,

            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )

    _migrate_actions_schema(cur)
    _init_champions_schema(cur)
    _init_projects_schema(cur)
    _init_action_team_schema(cur)
    _init_action_tasks_schema(cur)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_line ON actions(line);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_project ON actions(project_or_family);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_deleted ON actions(deleted);")
    con.commit()
    con.close()


def _migrate_actions_schema(cur: sqlite3.Cursor) -> None:
    cur.execute("PRAGMA table_info(actions);")
    existing_cols = {row[1] for row in cur.fetchall()}
    required_cols = {
        "created_by": "TEXT NOT NULL DEFAULT ''",
        "updated_by": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT (datetime('now'))",
        "deleted": "INTEGER NOT NULL DEFAULT 0",
        "target_date": "TEXT",
    }

    for col, definition in required_cols.items():
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE actions ADD COLUMN {col} {definition};")

    if "updated_at" in (existing_cols | required_cols.keys()):
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_actions_updated_at
            AFTER UPDATE ON actions
            FOR EACH ROW
            WHEN NEW.updated_at = OLD.updated_at
            BEGIN
                UPDATE actions SET updated_at = datetime('now') WHERE id = OLD.id;
            END;
            """
        )


def _init_champions_schema(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS champions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            first_name TEXT NOT NULL DEFAULT '',
            last_name TEXT NOT NULL DEFAULT '',
            name_display TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            deleted INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    _migrate_champions_schema(cur)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_champions_name ON champions(name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_champions_is_active ON champions(is_active);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_champions_deleted ON champions(deleted);")


def _migrate_champions_schema(cur: sqlite3.Cursor) -> None:
    cur.execute("PRAGMA table_info(champions);")
    existing_cols = {row[1] for row in cur.fetchall()}
    required_cols = {
        "first_name": "TEXT NOT NULL DEFAULT ''",
        "last_name": "TEXT NOT NULL DEFAULT ''",
        "name_display": "TEXT NOT NULL DEFAULT ''",
    }
    for col, definition in required_cols.items():
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE champions ADD COLUMN {col} {definition};")

    cur.execute(
        """
        UPDATE champions
        SET name_display = TRIM(name)
        WHERE name_display = '' AND name IS NOT NULL;
        """
    )

    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_champions_name_display_lower
        ON champions(LOWER(name_display));
        """
    )


def _init_projects_schema(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            deleted INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(is_active);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_deleted ON projects(deleted);")
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_name_lower
        ON projects(LOWER(name));
        """
    )


def _init_action_team_schema(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS action_team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id INTEGER NOT NULL,
            champion_id INTEGER NOT NULL,
            created_by TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            deleted INTEGER NOT NULL DEFAULT 0,
            UNIQUE(action_id, champion_id)
        );
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_action_team_action_id
        ON action_team_members(action_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_action_team_champion_id
        ON action_team_members(champion_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_action_team_deleted
        ON action_team_members(deleted);
        """
    )


def _init_action_tasks_schema(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS action_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            assignee_champion_id INTEGER,
            status TEXT NOT NULL DEFAULT 'OPEN',
            created_at TEXT NOT NULL DEFAULT (date('now')),
            target_date TEXT,
            done_at TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_by TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            deleted INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tasks_action_id
        ON action_tasks(action_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tasks_deleted
        ON action_tasks(deleted);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tasks_status
        ON action_tasks(status);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tasks_assignee
        ON action_tasks(assignee_champion_id);
        """
    )
