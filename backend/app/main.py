from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import actions, kpi, projects
from app.db.base import Base
from app.db.session import get_engine
from app.ui import routes as ui_routes


def create_app() -> FastAPI:
    app = FastAPI(
        title="CAPA Backend",
        version="0.1.0",
        # Ensure Swagger UI stays interactive in local development for all endpoints.
        swagger_ui_parameters={
            "tryItOutEnabled": True,
            "supportedSubmitMethods": ["get", "post", "put", "patch", "delete"],
            "persistAuthorization": True,
            "displayRequestDuration": True,
        },
    )

    app.include_router(actions.router)
    app.include_router(projects.router)
    app.include_router(kpi.router)
    app.include_router(ui_routes.router)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


app = create_app()


@app.on_event("startup")
def on_startup() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
