from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api import actions, analyses, kpi, projects, tags
from app.core.auth import get_current_user_optional, require_auth
from app.core.config import settings
from app.core.security import hash_password, is_password_too_long
from app.db.session import SessionLocal, engine
from app.models.user import User
from app.repositories import users as users_repo
from app.ui import routes as ui_routes
from app.ui import routes_analyses, routes_auth, routes_champions, routes_metrics, routes_projects, routes_settings


REQUIRED_CHAMPION_COLUMNS = {"first_name", "last_name", "email", "position", "birth_date"}
REQUIRED_USERS_COLUMNS = {"username", "password_hash", "role", "is_active", "email"}
REQUIRED_ACTION_COLUMNS = {"updated_at"}


logger = logging.getLogger("app.request")
_schema_error_already_logged = False


@dataclass(frozen=True)
class SchemaValidationResult:
    is_valid: bool
    database_url: str
    missing_revisions: list[str]
    missing_by_table: dict[str, list[str]]

    @property
    def has_errors(self) -> bool:
        return bool(self.missing_revisions or self.missing_by_table)


@dataclass(frozen=True)
class BlockedModeState:
    is_blocked: bool
    database_url: str
    missing_revisions: list[str]
    missing_by_table: dict[str, list[str]]


ALLOWED_WHEN_BLOCKED = {"/blocked", "/health", "/docs", "/openapi.json"}


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


def _get_alembic_revisions(engine) -> list[str]:
    inspector = inspect(engine)
    if not inspector.has_table("alembic_version"):
        return []
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    return [str(row[0]) for row in rows]


def _get_expected_alembic_revisions() -> list[str]:
    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    revisions: list[str] = []
    for migration_file in versions_dir.glob("*.py"):
        revision = migration_file.stem.split("_", maxsplit=1)[0]
        if revision:
            revisions.append(revision)
    return sorted(set(revisions))


def _build_schema_error_message(result: SchemaValidationResult) -> str:
    missing_revisions_text = ", ".join(result.missing_revisions) if result.missing_revisions else "<none>"
    if result.missing_by_table:
        missing_columns_lines = [
            f"- {table_name}: {', '.join(columns)}"
            for table_name, columns in sorted(result.missing_by_table.items())
        ]
        missing_columns_text = "\n".join(missing_columns_lines)
    else:
        missing_columns_text = "<none>"

    return (
        "================= DATABASE SCHEMA ERROR =================\n"
        f"Database URL: {result.database_url}\n"
        f"Missing Alembic revision(s): {missing_revisions_text}\n"
        "Missing columns by table:\n"
        f"{missing_columns_text}\n"
        "Fix in Windows Command Prompt:\n"
        "cd C:\\CAPA\\backend\n"
        "call .venv\\Scripts\\activate\n"
        "alembic upgrade head\n"
        "Application is running in BLOCKED MODE until migrations are applied.\n"
        "========================================================="
    )


def _build_blocked_mode_html(state: BlockedModeState) -> str:
    missing_revisions = ", ".join(state.missing_revisions) if state.missing_revisions else "<none>"
    missing_columns = "".join(
        f"<li><strong>{table}</strong>: {', '.join(columns)}</li>"
        for table, columns in sorted(state.missing_by_table.items())
    )
    if not missing_columns:
        missing_columns = "<li>&lt;none&gt;</li>"

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>CAPA Blocked Mode</title>
</head>
<body>
  <h1>Application is running in BLOCKED MODE</h1>
  <p>Database schema is out of date.</p>
  <h2>Details</h2>
  <ul>
    <li><strong>Database URL:</strong> {state.database_url}</li>
    <li><strong>Missing Alembic revision(s):</strong> {missing_revisions}</li>
  </ul>
  <h3>Missing columns per table</h3>
  <ul>
    {missing_columns}
  </ul>
  <h2>Fix in Windows Command Prompt</h2>
  <pre>cd C:\\CAPA\\backend
call .venv\\Scripts\\activate
alembic upgrade head</pre>
  <p><strong>Restart the backend after applying migrations.</strong></p>
</body>
</html>"""


def _log_schema_error_once(message: str) -> None:
    global _schema_error_already_logged
    if _schema_error_already_logged:
        return
    logger.error(message)
    _schema_error_already_logged = True


def validate_dev_schema(engine) -> SchemaValidationResult:
    inspector = inspect(engine)
    db_uri = settings.sqlalchemy_database_uri
    missing_by_table: dict[str, list[str]] = {}
    expected_revisions = _get_expected_alembic_revisions()
    detected_revisions = _get_alembic_revisions(engine)
    missing_revisions = sorted(set(expected_revisions) - set(detected_revisions))

    if inspector.has_table("champions"):
        champion_columns = {column["name"] for column in inspector.get_columns("champions")}
        missing_champions = sorted(REQUIRED_CHAMPION_COLUMNS - champion_columns)
        if missing_champions:
            missing_by_table["champions"] = missing_champions

    if inspector.has_table("users"):
        users_columns = {column["name"] for column in inspector.get_columns("users")}
        missing_users = sorted(REQUIRED_USERS_COLUMNS - users_columns)
        if missing_users:
            missing_by_table["users"] = missing_users

    if inspector.has_table("actions"):
        action_columns = {column["name"] for column in inspector.get_columns("actions")}
        missing_actions = sorted(REQUIRED_ACTION_COLUMNS - action_columns)
        if missing_actions:
            missing_by_table["actions"] = missing_actions

    result = SchemaValidationResult(
        is_valid=not (missing_revisions or missing_by_table),
        database_url=db_uri,
        missing_revisions=missing_revisions,
        missing_by_table=missing_by_table,
    )
    if result.is_valid:
        return result

    error_message = _build_schema_error_message(result)
    if settings.dev_mode:
        _log_schema_error_once(error_message)
        return result

    raise RuntimeError(error_message)


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
        swagger_ui_parameters={
            "tryItOutEnabled": True,
            "supportedSubmitMethods": ["get", "post", "put", "patch", "delete"],
            "persistAuthorization": True,
            "displayRequestDuration": True,
        },
    )

    app.state.blocked_mode = BlockedModeState(
        is_blocked=False,
        database_url=settings.sqlalchemy_database_uri,
        missing_revisions=[],
        missing_by_table={},
    )

    @app.middleware("http")
    async def schema_block_middleware(request: Request, call_next):
        blocked_state: BlockedModeState = app.state.blocked_mode
        if not blocked_state.is_blocked:
            return await call_next(request)
        if request.url.path in ALLOWED_WHEN_BLOCKED:
            return await call_next(request)
        return RedirectResponse(url="/blocked", status_code=307)

    app.include_router(actions.router, dependencies=[Depends(require_auth)])
    app.include_router(projects.router, dependencies=[Depends(require_auth)])
    app.include_router(kpi.router, dependencies=[Depends(require_auth)])
    app.include_router(tags.router, dependencies=[Depends(require_auth)])
    app.include_router(analyses.router, dependencies=[Depends(require_auth)])
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
    def healthcheck() -> dict[str, str]:
        blocked_state: BlockedModeState = app.state.blocked_mode
        if blocked_state.is_blocked:
            return {
                "status": "blocked",
                "reason": "pending migrations",
                "action_required": "alembic upgrade head",
            }
        return {"status": "ok"}

    @app.get("/blocked", response_class=HTMLResponse, include_in_schema=False)
    def blocked_page() -> HTMLResponse:
        blocked_state: BlockedModeState = app.state.blocked_mode
        return HTMLResponse(content=_build_blocked_mode_html(blocked_state), status_code=200)

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
    schema_status = validate_dev_schema(engine)
    app.state.blocked_mode = BlockedModeState(
        is_blocked=settings.dev_mode and not schema_status.is_valid,
        database_url=schema_status.database_url,
        missing_revisions=schema_status.missing_revisions,
        missing_by_table=schema_status.missing_by_table,
    )
    if settings.auth_enabled:
        db = SessionLocal()
        try:
            seed_admin_user(db)
        finally:
            db.close()
