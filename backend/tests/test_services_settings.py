from __future__ import annotations

from datetime import date

import pytest

from app.services import settings as settings_service


def test_create_champion_unique(db_session):
    champion = settings_service.create_champion(
        db_session,
        first_name="Alex",
        last_name="Kim",
        email="alex.kim@example.com",
        position="Supervisor",
        birth_date=None,
    )

    assert champion.id is not None
    assert champion.full_name == "Alex Kim"

    with pytest.raises(ValueError, match="already exists"):
        settings_service.create_champion(
            db_session,
            first_name="Alex",
            last_name="Kim",
            email="another@example.com",
            position=None,
            birth_date=None,
        )


def test_update_project_fields(db_session):
    engineer = settings_service.create_champion(
        db_session,
        first_name="Casey",
        last_name="Ng",
        email="casey.ng@example.com",
        position="Process Engineer",
        birth_date=None,
    )
    project = settings_service.create_project(
        db_session,
        "Line Upgrade",
        "Serial production",
        1000,
        5,
        engineer.id,
        None,
    )

    updated = settings_service.update_project(
        db_session,
        project_id=project.id,
        name="Line Upgrade Phase 2",
        status="Spare Parts",
        max_volume=500,
        flex_percent=12.5,
        process_engineer_id=engineer.id,
        due_date=date(2024, 5, 1),
    )

    assert updated.name == "Line Upgrade Phase 2"
    assert updated.status == "Spare Parts"
    assert updated.max_volume == 500
    assert updated.flex_percent == 12.5
    assert updated.process_engineer_id == engineer.id
    assert updated.due_date == date(2024, 5, 1)


def test_create_project_validates_required_fields(db_session):
    with pytest.raises(ValueError, match="Project status is required"):
        settings_service.create_project(db_session, "Line", None, 0, 10, 1, None)

    engineer = settings_service.create_champion(
        db_session,
        first_name="Sam",
        last_name="Fox",
        email="sam.fox@example.com",
        position="Process Engineer",
        birth_date=None,
    )

    with pytest.raises(ValueError, match="must be one of"):
        settings_service.create_project(db_session, "Line", "Open", 0, 10, engineer.id, None)
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        settings_service.create_project(db_session, "Line", "Serial production", -1, 10, engineer.id, None)
    with pytest.raises(ValueError, match="between 0 and 100"):
        settings_service.create_project(db_session, "Line", "Serial production", 1, 120, engineer.id, None)
    with pytest.raises(ValueError, match="does not exist"):
        settings_service.create_project(db_session, "Line", "Serial production", 1, 10, 9999, None)
