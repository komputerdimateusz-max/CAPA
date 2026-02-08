from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import actions, kpi, projects
from app.core.auth import get_current_user_optional, require_auth
from app.core.config import settings
from app.core.security import hash_password, is_password_too_long
from app.db.schema_guard import ensure_champion_schema
from app.db.base import Base
from app.db.session import SessionLocal, get_engine
from app.models.user import User
from app.repositories import users as users_repo
from app.ui import routes as ui_routes
from app.ui import routes_analyses, routes_auth, routes_champions, routes_metrics, routes_projects, routes_settings


def create_app() -> FastAPI:
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
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.middleware("http")
    async def ui_auth_middleware(request: Request, call_next):
        request.state.user = None
        if settings.auth_enabled and request.url.path.startswith("/ui"):
            with SessionLocal() as db:
                request.state.user = get_current_user_optional(request, db)
            if not request.url.path.startswith("/ui/login") and not request.state.user:
                if request.headers.get("HX-Request"):
                    response = HTMLResponse("Login required", status_code=401)
                    response.headers["HX-Redirect"] = "/ui/login"
                    return response
                return RedirectResponse("/ui/login", status_code=303)
        return await call_next(request)

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
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    if settings.dev_mode:
        ensure_champion_schema(engine)
    if settings.auth_enabled:
        db = SessionLocal()
        try:
            seed_admin_user(db)
        finally:
            db.close()
