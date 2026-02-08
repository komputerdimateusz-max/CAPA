from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect

from app.api import actions, kpi, projects
from app.core.auth import get_current_user_optional, require_auth
from app.core.config import settings
from app.core.security import hash_password, is_password_too_long
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.user import User
from app.repositories import users as users_repo
from app.ui import routes as ui_routes
from app.ui import routes_analyses, routes_auth, routes_champions, routes_metrics, routes_projects, routes_settings


REQUIRED_CHAMPION_COLUMNS = {"first_name", "last_name", "email", "position", "birth_date"}


logger = logging.getLogger("app.request")


def configure_app_logging() -> None:
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logger.setLevel(log_level)

    if not any(isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout for handler in logger.handlers):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        logger.addHandler(stream_handler)

    logger.propagate = True


def validate_dev_schema(engine) -> None:
    if not settings.dev_mode:
        return

    inspector = inspect(engine)
    if not inspector.has_table("champions"):
        return

    champion_columns = {column["name"] for column in inspector.get_columns("champions")}
    missing_columns = sorted(REQUIRED_CHAMPION_COLUMNS - champion_columns)
    if not missing_columns:
        return

    missing_fields = ", ".join(missing_columns)
    raise RuntimeError(
        "Database schema is behind the current app models. "
        f"Missing columns on 'champions': {missing_fields}. "
        "Run Alembic migrations before starting the app: `alembic upgrade head` "
        "(PowerShell: `cd backend; .\\.venv\\Scripts\\Activate.ps1; alembic upgrade head`)."
    )


def create_app() -> FastAPI:
    configure_app_logging()
    if settings.auth_enabled:
        settings.required_secret_key
    docs_url = "/docs" if settings.dev_mode else None
    openapi_url = "/openapi.json" if settings.dev_mode else None
    redoc_url = "/redoc" if settings.dev_mode else None
    app = FastAPI(
        title="CAPA Backend",
        version="0.1.0",
        docs_url=docs_url,
        openapi_url=openapi_url,
        redoc_url=redoc_url,
        # Ensure Swagger UI stays interactive in local development for all endpoints.
        swagger_ui_parameters={
            "tryItOutEnabled": True,
            "supportedSubmitMethods": ["get", "post", "put", "patch", "delete"],
            "persistAuthorization": True,
            "displayRequestDuration": True,
        },
    )

    app.include_router(actions.router, dependencies=[Depends(require_auth)])
    app.include_router(projects.router, dependencies=[Depends(require_auth)])
    app.include_router(kpi.router, dependencies=[Depends(require_auth)])
    app.include_router(routes_auth.router)
    app.include_router(ui_routes.router)
    app.include_router(routes_projects.router)
    app.include_router(routes_champions.router)
    app.include_router(routes_metrics.router)
    app.include_router(routes_settings.router)
    app.include_router(routes_analyses.router)

    static_dir = Path(__file__).resolve().parent / "static"
    templates_dir = Path(__file__).resolve().parent / "templates"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.mount("/templates", StaticFiles(directory=str(templates_dir)), name="templates")

    @app.get("/login", include_in_schema=False)
    def login_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/login", status_code=302)

    @app.get("/health")
    def healthcheck() -> dict[str, bool]:
        return {"ok": True}

    @app.middleware("http")
    async def ui_auth_middleware(request: Request, call_next):
        request.state.user = None
        if settings.auth_enabled and request.url.path.startswith("/ui"):
            try:
                with SessionLocal() as db:
                    request.state.user = get_current_user_optional(request, db)
            except Exception:
                logger.exception("Failed to resolve UI session for %s", request.url.path)
                request.state.user = None
            if (
                not request.url.path.startswith("/ui/login")
                and not request.url.path.startswith("/ui/signup")
                and not request.state.user
            ):
                if request.headers.get("HX-Request"):
                    response = HTMLResponse("Login required", status_code=401)
                    response.headers["HX-Redirect"] = "/login"
                    return response
                return RedirectResponse("/login", status_code=302)
        return await call_next(request)

    @app.middleware("http")
    async def ui_exception_middleware(request: Request, call_next):
        if not request.url.path.startswith("/ui"):
            return await call_next(request)
        try:
            return await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled UI exception for %s", request.url.path)
            return HTMLResponse(
                content=(
                    "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                    "<title>CAPA UI Error</title></head><body>"
                    "<h1>CAPA UI Error</h1>"
                    "<p>The page could not be rendered due to an internal error.</p>"
                    f"<p><strong>{type(exc).__name__}:</strong> {exc}</p>"
                    "<p><a href='/login'>Go to Login</a></p>"
                    "</body></html>"
                ),
                status_code=500,
            )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "%s %s -> %s (%.2f ms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
            return response
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.exception(
                "%s %s -> 500 (%.2f ms)",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

    return app


def seed_admin_user(db: SessionLocal) -> None:
    if users_repo.count_users(db) != 0:
        return

    admin_username = settings.admin_username
    admin_password = settings.admin_password

    if settings.dev_mode:
        username = admin_username or "admin"
        password = admin_password or "admin123"
    else:
        if not admin_username and not admin_password:
            return
        if not admin_username:
            raise RuntimeError("ADMIN_USERNAME must be set to seed admin when DEV_MODE=false.")
        if not admin_password:
            raise RuntimeError("ADMIN_PASSWORD must be set to seed admin when DEV_MODE=false.")
        username = admin_username
        password = admin_password

    if is_password_too_long(password):
        raise RuntimeError(
            "ADMIN_PASSWORD too long for bcrypt (max 72 bytes). Use a shorter password."
        )

    try:
        user = User(
            username=username,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
        users_repo.create_user(db, user)
        print(f"Created admin user: {username}")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to seed admin user: {exc}") from exc


app = create_app()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    validate_dev_schema(engine)
    if settings.auth_enabled:
        db = SessionLocal()
        try:
            seed_admin_user(db)
        finally:
            db.close()
