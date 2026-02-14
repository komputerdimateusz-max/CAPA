from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from app.models.action import Action
from app.models.project import Project
from app.services import champions as champions_service


def test_sync_actions_champions_with_settings_nullifies_orphans(db_session):
    action = Action(title="Orphan", status="OPEN", champion_id=1111, created_at=datetime.utcnow())
    project = Project(name="Project orphan", status="Serial production", process_engineer_id=1111)
    db_session.add_all([action, project])
    db_session.commit()

    stats = champions_service.sync_actions_champions_with_settings(db_session)

    db_session.refresh(action)
    db_session.refresh(project)
    assert stats.actions_updated == 1
    assert stats.projects_updated == 1
    assert stats.analyses_updated == 0
    assert action.champion_id is None
    assert project.process_engineer_id is None


def test_sync_actions_champions_with_settings_clears_legacy_name_snapshots(db_session):
    db_session.execute(text("ALTER TABLE actions ADD COLUMN champion_name VARCHAR(255)"))
    db_session.execute(text("ALTER TABLE actions ADD COLUMN champion_first_name VARCHAR(255)"))
    db_session.execute(text("ALTER TABLE actions ADD COLUMN champion_last_name VARCHAR(255)"))

    action_orphan = Action(title="Orphan", status="OPEN", champion_id=2222, created_at=datetime.utcnow())
    action_unassigned = Action(title="Unassigned", status="OPEN", champion_id=None, created_at=datetime.utcnow())
    db_session.add_all([action_orphan, action_unassigned])
    db_session.commit()

    db_session.execute(
        text(
            """
            UPDATE actions
            SET champion_name = :name,
                champion_first_name = :first_name,
                champion_last_name = :last_name
            WHERE id IN (:id_orphan, :id_unassigned)
            """
        ),
        {
            "name": "Ktokolwiek Ktos",
            "first_name": "Ktokolwiek",
            "last_name": "Ktos",
            "id_orphan": action_orphan.id,
            "id_unassigned": action_unassigned.id,
        },
    )
    db_session.commit()

    stats = champions_service.sync_actions_champions_with_settings(db_session)

    assert stats.actions_updated >= 2

    refreshed_rows = db_session.execute(
        text(
            """
            SELECT id, champion_id, champion_name, champion_first_name, champion_last_name
            FROM actions
            WHERE id IN (:id_orphan, :id_unassigned)
            ORDER BY id
            """
        ),
        {"id_orphan": action_orphan.id, "id_unassigned": action_unassigned.id},
    ).mappings().all()

    for row in refreshed_rows:
        assert row["champion_id"] is None
        assert row["champion_name"] is None
        assert row["champion_first_name"] is None
        assert row["champion_last_name"] is None
