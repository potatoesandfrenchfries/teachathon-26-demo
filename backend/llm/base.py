"""Provider-independent types. Every pipeline stage talks to a `TextLLM`, never to a vendor SDK."""

from typing import Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class Cost(BaseModel):
    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0


class EdgeClassification(BaseModel):
    """A pipeline's verdict on one proposed prerequisite edge.

    `none` means the pipeline thinks there is no prerequisite relationship, which the gold set
    also covers (required, optional and absent).
    """

    type: Literal["required", "optional", "none"]
    justification: str
    confidence: float = Field(ge=0.0, le=1.0)


class LLMRequest(BaseModel):
    stage: str  # for example "edge"
    prompt_version: str  # for example "edge-v1"; changing a prompt means bumping this
    system: str = ""
    user: str


class Completion(BaseModel, Generic[T]):
    result: T
    cost: Cost
    provider: str
    model: str
    cached: bool = False


class TextLLM(Protocol):
    """Returns a validated `schema` instance, plus what the call cost.

    Implementations: FakeProvider (tests), ClaudeProvider (Pipeline A) and LocalProvider
    (Pipeline B). All of them must pass the contract tests in tests/test_llm_contract.py.
    """

    provider: str
    model: str

    def complete(self, request: LLMRequest, schema: type[T]) -> Completion[T]: ...
