from __future__ import annotations

import pytest

from app.core.security import verify_password
from app.services import users as users_service


def test_create_user_hashes_password_and_defaults_role(db_session):
    user = users_service.create_user(db_session, "alice", "super-secret", dev_mode=True)

    assert user.role == "viewer"
    assert user.password_hash != "super-secret"
    assert verify_password("super-secret", user.password_hash)


def test_create_user_rejects_duplicate_username(db_session):
    users_service.create_user(db_session, "alice", "super-secret", dev_mode=True)

    with pytest.raises(ValueError, match="already exists"):
        users_service.create_user(db_session, "alice", "another-secret", dev_mode=True)


def test_create_user_rejects_password_too_long(db_session):
    too_long_password = "a" * 73

    with pytest.raises(ValueError, match="72 bytes"):
        users_service.create_user(db_session, "alice", too_long_password, dev_mode=True)
