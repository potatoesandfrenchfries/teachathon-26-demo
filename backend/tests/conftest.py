from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

import backend.models  # noqa: F401  (registers the tables)
from backend.api.app import create_app
from backend.db import make_engine
from backend.settings import Settings


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = make_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite://",
        admin_key="test-key",
        runs_dir=tmp_path / "runs",
    )


@pytest.fixture
def client(settings: Settings, engine: Engine) -> Iterator[TestClient]:
    with TestClient(create_app(settings=settings, engine=engine)) as client:
        yield client
