from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from backend.api import graph, health
from backend.db import make_engine
from backend.graph.service import GraphError
from backend.settings import Settings, get_settings


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="TeachAThon 2026 API")
    app.state.settings = settings
    app.state.engine = engine or make_engine(settings.database_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(graph.router)
    app.include_router(graph.admin)

    @app.exception_handler(GraphError)
    def graph_error(_request: Request, error: GraphError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    return app
