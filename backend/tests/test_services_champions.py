from __future__ import annotations

from datetime import datetime

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
