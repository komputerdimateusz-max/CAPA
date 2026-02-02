from __future__ import annotations

from datetime import date

import pytest

from app.services import settings as settings_service


def test_create_champion_unique(db_session):
    champion = settings_service.create_champion(db_session, "Alex Kim")

    assert champion.id is not None
    assert champion.name == "Alex Kim"

    with pytest.raises(ValueError, match="already exists"):
        settings_service.create_champion(db_session, "Alex Kim")


def test_update_project_fields(db_session):
    project = settings_service.create_project(db_session, "Line Upgrade", "Open", None)

    updated = settings_service.update_project(
        db_session,
        project_id=project.id,
        name="Line Upgrade Phase 2",
        status="In Progress",
        due_date=date(2024, 5, 1),
    )

    assert updated.name == "Line Upgrade Phase 2"
    assert updated.status == "In Progress"
    assert updated.due_date == date(2024, 5, 1)
