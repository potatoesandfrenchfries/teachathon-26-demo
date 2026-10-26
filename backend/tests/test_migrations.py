"""Alembic migrations apply to an empty database, match the models, and can be reversed."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, select

import backend.models  # noqa: F401
from backend.db import make_engine
from backend.models import Book, Course
from backend.seed import DEFAULT_PRESET, PRESETS, seed

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_url(tmp_path) -> str:
    url = f"sqlite:///{tmp_path / 'test.db'}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return url


def test_upgrade_creates_every_model_table(migrated_url):
    tables = set(inspect(make_engine(migrated_url)).get_table_names())
    assert set(SQLModel.metadata.tables) <= tables


def test_migration_matches_the_models(migrated_url):
    """Fails when a model changed without a new migration."""
    engine = make_engine(migrated_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(context, SQLModel.metadata)
    assert diff == []


def test_downgrade_to_base_removes_the_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'down.db'}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    remaining = set(inspect(make_engine(url)).get_table_names()) - {"alembic_version"}
    assert remaining == set()


def test_seed_gives_one_course_and_one_book_and_is_idempotent(migrated_url, tmp_path):
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"not really a pdf")

    engine = make_engine(migrated_url)
    with Session(engine) as session:
        course, book = seed(session, DEFAULT_PRESET, pdf)
        first_hash = book.file_sha256
        seed(session, DEFAULT_PRESET, pdf)

        assert len(session.exec(select(Course)).all()) == 1
        books = session.exec(select(Book)).all()
        assert len(books) == 1
        assert books[0].role == "main"
        assert books[0].title == PRESETS[DEFAULT_PRESET].book_title
        assert first_hash is not None and len(first_hash) == 64
        assert books[0].file_sha256 == first_hash


def test_seed_without_a_pdf_leaves_the_hash_empty(migrated_url, tmp_path):
    engine = make_engine(migrated_url)
    with Session(engine) as session:
        _, book = seed(session, DEFAULT_PRESET, tmp_path / "missing.pdf")
        assert book.file_sha256 is None
