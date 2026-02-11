from __future__ import annotations

import argparse
import csv
from datetime import datetime, date
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.action import Action
from app.models.champion import Champion
from app.models.project import Project
from app.models.subtask import Subtask


DATE_FIELDS = {"due_date", "created_at", "closed_at"}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed
        except ValueError:
            continue
    return None


def import_champions(session, path: Path) -> None:
    if not path.exists():
        return
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            first_name = (row.get("first_name") or "").strip()
            last_name = (row.get("last_name") or "").strip()
            if not first_name and not last_name:
                name = (row.get("name") or "").strip()
                if not name:
                    continue
                parts = name.split()
                if len(parts) >= 2:
                    first_name = parts[0]
                    last_name = " ".join(parts[1:])
                else:
                    first_name = "Unknown"
                    last_name = name
            session.add(
                Champion(
                    first_name=first_name,
                    last_name=last_name,
                    email=(row.get("email") or "").strip() or None,
                    position=(row.get("position") or "").strip() or None,
                    birth_date=_parse_date(row.get("birth_date")),
                )
            )
    session.commit()


def import_projects(session, path: Path) -> None:
    if not path.exists():
        return
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = (row.get("name") or row.get("project") or "").strip()
            if not name:
                continue
            session.add(
                Project(
                    name=name,
                    status=row.get("status") or None,
                    due_date=_parse_date(row.get("due_date")),
                )
            )
    session.commit()


def import_actions(session, path: Path) -> None:
    if not path.exists():
        return
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            title = (row.get("title") or row.get("action") or "").strip()
            if not title:
                continue
            session.add(
                Action(
                    title=title,
                    description=row.get("description") or "",
                    status=row.get("status") or "OPEN",
                    created_at=_parse_datetime(row.get("created_at")) or datetime.utcnow(),
                    due_date=_parse_date(row.get("due_date")),
                    closed_at=_parse_datetime(row.get("closed_at")),
                    owner=row.get("owner"),
                    tags=[t.strip() for t in (row.get("tags") or "").split(",") if t.strip()],
                )
            )
    session.commit()


def import_subtasks(session, path: Path) -> None:
    if not path.exists():
        return
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            title = (row.get("title") or "").strip()
            action_id = row.get("action_id")
            if not title or not action_id:
                continue
            session.add(
                Subtask(
                    action_id=int(action_id),
                    title=title,
                    status=row.get("status") or "OPEN",
                    due_date=_parse_date(row.get("due_date")),
                    closed_at=_parse_datetime(row.get("closed_at")),
                    created_at=_parse_datetime(row.get("created_at")) or datetime.utcnow(),
                )
            )
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("../data"))
    args = parser.parse_args()

    engine = create_engine(
        settings.sqlalchemy_database_uri,
        connect_args={"check_same_thread": False}
        if settings.sqlalchemy_database_uri.startswith("sqlite")
        else {},
    )
    inspector = inspect(engine)
    required_tables = {"actions", "projects", "champions", "subtasks"}
    missing_tables = sorted(required_tables - set(inspector.get_table_names()))
    if missing_tables:
        missing = ", ".join(missing_tables)
        raise RuntimeError(
            f"Database schema is missing tables: {missing}. Run Alembic migrations before importing CSV data."
        )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        import_champions(session, args.data_dir / "champions.csv")
        import_projects(session, args.data_dir / "projects.csv")
        import_actions(session, args.data_dir / "actions.csv")
        import_subtasks(session, args.data_dir / "subtasks.csv")
    finally:
        session.close()


if __name__ == "__main__":
    main()
