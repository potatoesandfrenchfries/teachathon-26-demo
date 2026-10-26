from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.deps import require_admin_key


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_the_vite_dev_server(client):
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def _app_with_admin_route(settings, engine) -> FastAPI:
    app = create_app(settings=settings, engine=engine)

    @app.get("/admin/ping", dependencies=[Depends(require_admin_key)])
    def ping() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_admin_route_needs_the_key(settings, engine):
    client = TestClient(_app_with_admin_route(settings, engine))
    assert client.get("/admin/ping").status_code == 401
    assert client.get("/admin/ping", headers={"X-Admin-Key": "wrong"}).status_code == 401
    assert client.get("/admin/ping", headers={"X-Admin-Key": "test-key"}).status_code == 200


def test_admin_route_refused_when_no_key_is_configured(settings, engine):
    settings.admin_key = None
    client = TestClient(_app_with_admin_route(settings, engine))
    assert client.get("/admin/ping", headers={"X-Admin-Key": ""}).status_code == 401
    assert client.get("/admin/ping", headers={"X-Admin-Key": "anything"}).status_code == 401
