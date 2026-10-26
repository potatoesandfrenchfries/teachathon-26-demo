from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from backend.models.enums import QuestionType, ReviewStatus, TagSource, TagStatus


class Question(SQLModel, table=True):
    """A practice question. Fields follow PLAN.md section 4.

    `options` (MCQ only) is a list of {"label", "text", "misconception"}. `answer_key` depends
    on the type: {"correct": "B"} for mcq, {"value": 20.0, "unit": "m/s", "tolerance_rel": 0.01}
    for numeric, {"accepted": [...]} for short. The book's visibility applies to every question
    that belongs to it.
    """

    __tablename__ = "question"

    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    section_id: int | None = Field(default=None, foreign_key="section.id")
    page: int | None = None
    source_ref: str | None = None  # for example "2.A.7"
    latex: str  # the statement, as KaTeX-compatible LaTeX
    type: str = QuestionType.NUMERIC.value
    options: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    answer_key: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    difficulty_prior: float | None = None
    irt_b: float | None = None
    irt_a: float | None = None
    extraction_confidence: float | None = None
    review_status: str = ReviewStatus.NEEDS_REVIEW.value
    page_image_ref: str | None = None
    content_hash: str | None = Field(default=None, index=True)
    # Provenance. Null for sample and hand-written questions.
    pipeline: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    run_id: str | None = None


class QuestionTag(SQLModel, table=True):
    """Links a question to the concept nodes it exercises. At most 3 tags per question."""

    __tablename__ = "question_tag"

    question_id: int = Field(foreign_key="question.id", primary_key=True)
    node_id: int = Field(foreign_key="concept_node.id", primary_key=True)
    is_primary: bool = False
    source: str = TagSource.LLM.value
    confidence: float | None = None
    status: str = TagStatus.PROPOSED.value
