from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_session_token
from app.db.session import get_db
from app.models.action import Action
from app.models.user import User
from app.repositories import actions as actions_repo
from app.repositories import users as users_repo


def get_current_user_optional(request: Request, db: Session) -> User | None:
    if not settings.auth_enabled:
        return None
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    payload = decode_session_token(token, settings.session_ttl_days * 24 * 60 * 60)
    if not payload:
        return None
    user = users_repo.get_user_by_id(db, int(payload.get("uid", 0)))
    if not user or not user.is_active:
        return None
    return user


def require_auth(request: Request, db: Session = Depends(get_db)) -> User | None:
    if not settings.auth_enabled:
        return None
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_role_admin(user: User | None = Depends(require_auth)) -> User | None:
    if not settings.auth_enabled:
        return user
    if not user or user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_role_viewer_or_higher(user: User | None = Depends(require_auth)) -> User | None:
    if not settings.auth_enabled:
        return user
    return user


def require_can_edit_action(
    action_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(require_auth),
) -> Action:
    action = actions_repo.get_action(db, action_id)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    if not settings.auth_enabled:
        return action
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if user.role == "admin":
        return action
    if user.role == "champion" and user.champion_id and action.champion_id == user.champion_id:
        return action
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def enforce_write_access(user: User | None) -> None:
    if not settings.auth_enabled:
        return
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if user.role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only access")


def enforce_action_ownership(user: User | None, action: Action) -> None:
    if not settings.auth_enabled:
        return
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if user.role == "admin":
        return
    if user.role == "champion" and user.champion_id and action.champion_id == user.champion_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def enforce_action_create_permission(user: User | None, champion_id: int | None) -> None:
    if not settings.auth_enabled:
        return
    enforce_write_access(user)
    if user and user.role == "champion":
        if not user.champion_id or champion_id != user.champion_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Champion access required")


def enforce_admin(user: User | None) -> None:
    if not settings.auth_enabled:
        return
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
