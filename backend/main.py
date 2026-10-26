"""ASGI entry point: `uvicorn backend.main:app --reload` from the repo root."""

from backend.api.app import create_app

app = create_app()
