from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from backend.models.course import utcnow


class LLMCall(SQLModel, table=True):
    """One provider call. This table is both the response cache and the cost ledger.

    The unique key is (stage, provider, model, prompt_version, input_hash), so an identical
    request is answered from this table with no provider call. `run_id` records the run that
    paid for the call.
    """

    __tablename__ = "llm_call"
    __table_args__ = (
        UniqueConstraint(
            "stage", "provider", "model", "prompt_version", "input_hash", name="uq_llm_call_key"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    stage: str = Field(index=True)
    provider: str
    model: str
    prompt_version: str
    input_hash: str
    output: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    run_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow)
