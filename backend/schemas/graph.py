"""Request and response shapes for the graph API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CourseOut(BaseModel):
    id: int
    name: str
    graph_status: Literal["draft", "approved"]
    graph_version: int
    lock_mode: str


class NodeOut(BaseModel):
    id: int
    title: str
    section_number: str | None
    world_group: str | None
    threshold: float | None
    k_required: int | None
    origin: str
    question_count: int


class ClassificationOut(BaseModel):
    type: Literal["required", "optional", "none"]
    justification: str
    confidence: float
    provider: str
    model: str
    prompt_version: str


class CrossRefOut(BaseModel):
    """One reference: `referring` (in `referring_section`) points to `referred`."""

    referring: str
    referring_section: str
    referred: str
    referred_section: str
    count: int


class EvidenceOut(BaseModel):
    total: int
    crossrefs: list[CrossRefOut]


class EdgeOut(BaseModel):
    id: int
    src_node: int
    dst_node: int
    type: Literal["required", "optional"]
    weight: int
    source: Literal["xref", "llm", "manual"]
    status: Literal["proposed", "accepted", "rejected"]
    justification: str | None
    classifications: dict[str, ClassificationOut]
    # Two or more pipelines classified the edge and did not all agree.
    disagreement: bool
    # Implied by a longer path, so the map hides it. It still exists and can be reviewed.
    hidden: bool
    evidence: EvidenceOut


class GraphOut(BaseModel):
    course: CourseOut
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    # Ids of edges still to review, most worth looking at first (disagreements, then least sure).
    review_queue: list[int]


class EdgeCreate(BaseModel):
    course_id: int | None = None
    src_node: int
    dst_node: int
    type: Literal["required", "optional"] = "required"


class EdgeRetype(BaseModel):
    type: Literal["required", "optional"]


class ApproveRequest(BaseModel):
    course_id: int | None = None
    # Accept every edge still `proposed` instead of refusing to approve.
    accept_remaining: bool = Field(default=False)


class EditOut(BaseModel):
    id: int
    graph_version: int
    actor: str
    ts: datetime
    op: str
    target_id: int | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
