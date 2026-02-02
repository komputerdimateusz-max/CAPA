from __future__ import annotations

from fastapi import FastAPI

from app.api import actions, kpi, projects
from app.db.base import Base
from app.db.session import get_engine


def create_app() -> FastAPI:
    app = FastAPI(title="CAPA Backend", version="0.1.0")

    app.include_router(actions.router)
    app.include_router(projects.router)
    app.include_router(kpi.router)

    return app


app = create_app()


@app.on_event("startup")
def on_startup() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
