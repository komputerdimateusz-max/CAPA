from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_session_token, verify_password
from app.db.session import get_db
from app.repositories import users as users_repo

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/login", response_class=HTMLResponse, response_model=None)
def login_form(request: Request, error: str | None = None):
    if settings.auth_enabled and getattr(request.state, "user", None):
        return RedirectResponse(url="/ui", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error or "",
        },
    )


@router.post("/login", response_model=None)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if not settings.auth_enabled:
        return RedirectResponse(url="/ui", status_code=303)
    user = users_repo.get_user_by_username(db, username)
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid username or password.",
            },
            status_code=401,
        )
    token = create_session_token(user.id, user.role)
    response = RedirectResponse(url="/ui", status_code=303)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
    )
    return response


@router.post("/logout", response_model=None)
def logout():
    response = RedirectResponse(url="/ui/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response
