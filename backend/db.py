"""Engine and session helpers. SQLite for the prototype; keep the SQL portable for Postgres."""

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from backend.settings import get_settings


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    if not parsed.get_backend_name() == "sqlite":
        return create_engine(url)

    in_memory = parsed.database in (None, "", ":memory:")
    if not in_memory:
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        # An in-memory database exists per connection, so share one connection.
        poolclass=StaticPool if in_memory else None,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def default_engine() -> Engine:
    return make_engine(get_settings().database_url)
