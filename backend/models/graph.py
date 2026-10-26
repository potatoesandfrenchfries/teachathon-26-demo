from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from backend.models.course import utcnow
from backend.models.enums import EdgeSource, EdgeStatus, EdgeType, NodeOrigin


class ConceptNode(SQLModel, table=True):
    __tablename__ = "concept_node"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    # Null for nodes added by hand or created by a merge.
    section_id: int | None = Field(default=None, foreign_key="section.id")
    title: str
    world_group: str | None = None
    # Null falls back to the course default.
    threshold: float | None = None
    k_required: int | None = None
    origin: str = NodeOrigin.SECTION.value


class Edge(SQLModel, table=True):
    """A prerequisite edge: `src_node` must be learned before `dst_node`.

    `type` and `status` are the current verdict (what the professor sees and approves).
    `classifications` keeps what each pipeline said, keyed by pipeline name, so that
    disagreement between pipelines can rank the review queue:
    {"A": {"type": ..., "justification": ..., "confidence": ..., "model": ..., "prompt": ...}}
    """

    __tablename__ = "edge"
    __table_args__ = (UniqueConstraint("course_id", "src_node", "dst_node", name="uq_edge_pair"),)

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    src_node: int = Field(foreign_key="concept_node.id")
    dst_node: int = Field(foreign_key="concept_node.id")
    type: str = EdgeType.REQUIRED.value
    # Number of cross-references backing the edge.
    weight: int = 0
    source: str = EdgeSource.XREF.value
    justification: str | None = None
    status: str = EdgeStatus.PROPOSED.value
    classifications: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    graph_version: int = 1


class GraphEdit(SQLModel, table=True):
    """Audit log of every change to the graph: who, when, and the before and after values."""

    __tablename__ = "graph_edit"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    graph_version: int
    actor: str
    ts: datetime = Field(default_factory=utcnow)
    op: str
    target_id: int | None = None
    before: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    after: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
