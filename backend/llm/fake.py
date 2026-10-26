"""A deterministic provider for tests and for exercising the pipeline without spending money."""

import hashlib
from typing import Literal, cast

from backend.llm.base import Completion, Cost, EdgeClassification, LLMRequest, T

_TYPES: tuple[Literal["required", "optional", "none"], ...] = ("required", "optional", "none")


class FakeProvider:
    provider = "fake"

    def __init__(
        self, model: str = "fake-1", cost_per_call: float = 0.001, fail_after: int | None = None
    ) -> None:
        self.model = model
        self.cost_per_call = cost_per_call
        # Raise on the call after this many successful ones, to simulate a crash.
        self.fail_after = fail_after
        self.calls = 0

    def complete(self, request: LLMRequest, schema: type[T]) -> Completion[T]:
        if schema is not EdgeClassification:
            raise TypeError("FakeProvider only knows how to produce EdgeClassification")
        if self.fail_after is not None and self.calls >= self.fail_after:
            raise RuntimeError("FakeProvider: simulated failure")
        self.calls += 1

        text = f"{request.stage}|{request.prompt_version}|{request.system}|{request.user}"
        digest = int(hashlib.sha256(text.encode()).hexdigest(), 16)
        verdict = _TYPES[digest % len(_TYPES)]
        result = EdgeClassification(
            type=verdict,
            justification=f"fake verdict: {verdict}",
            confidence=0.5 + ((digest >> 8) % 50) / 100,
        )
        cost = Cost(
            tokens_in=len(request.system + request.user) // 4,
            tokens_out=40,
            usd=self.cost_per_call,
        )
        completion = Completion(result=result, cost=cost, provider=self.provider, model=self.model)
        # The schema check above guarantees T is EdgeClassification; the checker cannot see that.
        return cast(Completion[T], completion)
