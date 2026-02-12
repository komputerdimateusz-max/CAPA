from __future__ import annotations

import pytest

from app.core.security import verify_password
from app.models.user import User
from app.services import users as users_service


def test_create_user_hashes_password_and_defaults_role(db_session):
    user = users_service.create_user(db_session, "alice", "super-secret", dev_mode=True)

    assert user.role == "viewer"
    assert user.email == "alice@local.invalid"
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


def test_list_users_returns_all(db_session):
    users_service.create_user(db_session, "alice", "secret-1", email="alice@example.com", dev_mode=True)
    users_service.create_user(db_session, "bob", "secret-2", email="bob@example.com", dev_mode=True)

    users = users_service.list_users(db_session)

    assert [user.email for user in users] == ["alice@example.com", "bob@example.com"]


def test_upsert_user_role_persists(db_session):
    user = users_service.create_user(db_session, "alice", "secret", email="alice@example.com", dev_mode=True)

    updated = users_service.upsert_user_role(db_session, user_id=user.id, email=user.email, role="admin")

    assert updated.role == "admin"
    stored = db_session.get(User, user.id)
    assert stored is not None
    assert stored.role == "admin"


def test_upsert_user_role_rejects_invalid_role(db_session):
    user = users_service.create_user(db_session, "alice", "secret", email="alice@example.com", dev_mode=True)

    with pytest.raises(ValueError, match="Role must be one of"):
        users_service.upsert_user_role(db_session, user_id=user.id, email=user.email, role="owner")
