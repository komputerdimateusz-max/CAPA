from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_session_token, verify_password
from app.db.session import get_db
from app.repositories import users as users_repo
from app.services import users as users_service

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/login", response_class=HTMLResponse, response_model=None)
def login_form(request: Request, error: str | None = None, signup_error: str | None = None):
    if settings.auth_enabled and getattr(request.state, "user", None):
        return RedirectResponse(url="/ui", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error or "",
            "signup_error": signup_error or "",
            "allow_signup": settings.allow_signup_enabled,
        },
    )


def _session_response(user_id: int, role: str) -> RedirectResponse:
    token = create_session_token(user_id, role)
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


@router.post("/login", response_model=None)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if not settings.auth_enabled:
        return RedirectResponse(url="/ui", status_code=303)
    try:
        user = users_repo.get_user_by_username(db, username)
    except OperationalError as exc:
        return HTMLResponse(
            content=(
                "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                "<title>CAPA Login Error</title></head><body>"
                "<h1>Database schema is out of date</h1>"
                "<p>The login query failed because the database is missing expected columns "
                "(for example <code>users.email</code>).</p>"
                "<p>Run: <code>alembic upgrade head</code></p>"
                f"<p><strong>Details:</strong> {exc}</p>"
                "<p><a href='/docs'>Open API docs</a></p>"
                "<p><a href='/ui/login'>Back to login</a></p>"
                "</body></html>"
            ),
            status_code=500,
        )
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid username or password.",
                "signup_error": "",
                "allow_signup": settings.allow_signup_enabled,
            },
            status_code=401,
        )
    return _session_response(user.id, user.role)


@router.get("/signup", response_class=HTMLResponse, response_model=None)
def signup_form(request: Request):
    if settings.auth_enabled and getattr(request.state, "user", None):
        return RedirectResponse(url="/ui", status_code=303)
    if not settings.allow_signup_enabled:
        return login_form(request, signup_error="Contact admin to create an account.")
    return login_form(request)


@router.post("/signup", response_model=None)
def signup(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if not settings.allow_signup_enabled:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "",
                "signup_error": "Contact admin to create an account.",
                "allow_signup": settings.allow_signup_enabled,
            },
            status_code=403,
        )
    if not settings.auth_enabled:
        return RedirectResponse(url="/ui", status_code=303)
    try:
        user = users_service.create_user(
            db,
            username=username,
            password=password,
            email=email,
            role="viewer",
            dev_mode=settings.dev_mode,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "",
                "signup_error": str(exc),
                "allow_signup": settings.allow_signup_enabled,
            },
            status_code=400,
        )
    return _session_response(user.id, user.role)


@router.post("/logout", response_model=None)
def logout():
    response = RedirectResponse(url="/ui/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response
