from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from backend.models.enums import BookRole, GraphStatus, LockMode, Visibility


def utcnow() -> datetime:
    return datetime.now(UTC)


class Course(SQLModel, table=True):
    __tablename__ = "course"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    lock_mode: str = LockMode.SOFT.value
    graph_status: str = GraphStatus.DRAFT.value
    # Bumped when an approved graph is re-opened. Edges and edits record the version they belong to.
    graph_version: int = 1
    checkpoint_every_n: int | None = None
    default_threshold: float = 0.95
    # "all" means k = n: every required prerequisite must be mastered.
    default_k_rule: str = "all"
    created_at: datetime = Field(default_factory=utcnow)


class Book(SQLModel, table=True):
    __tablename__ = "book"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    authors: str | None = None
    edition: str | None = None
    role: str = BookRole.MAIN.value
    license: str | None = None
    license_url: str | None = None
    # The single source of truth for export blocking. Questions inherit it.
    visibility: str = Visibility.INTERNAL_ONLY.value
    file_sha256: str | None = Field(default=None, index=True)
