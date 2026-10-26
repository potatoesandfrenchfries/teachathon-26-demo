"""Cache and cost ledger in front of any provider.

The LLMCall table is both. An identical request, keyed by
(stage, provider, model, prompt_version, sha256(input)), is answered from it with no provider call.
"""

import hashlib
import json

from sqlalchemy import func
from sqlmodel import Session, select

from backend.llm.base import Completion, Cost, LLMRequest, T, TextLLM
from backend.llm.run import BudgetExceeded
from backend.models import LLMCall


def input_hash(request: LLMRequest, schema: type) -> str:
    payload = json.dumps(
        {"system": request.system, "user": request.user, "schema": schema.__name__},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def spent_usd(session: Session, run_id: str) -> float:
    total = session.exec(
        select(func.coalesce(func.sum(LLMCall.cost_usd), 0.0)).where(LLMCall.run_id == run_id)
    ).one()
    return float(total)


class CachedLLM:
    """Wraps a provider. Implements the same interface, so stages cannot tell the difference.

    With `run_id` and `budget_usd`, a provider call is refused once that run's recorded spend has
    reached the cap. The check happens before the call, so the final call can overshoot the cap by
    at most its own cost.
    """

    def __init__(
        self,
        inner: TextLLM,
        session: Session,
        run_id: str | None = None,
        budget_usd: float | None = None,
    ) -> None:
        self.inner = inner
        self.session = session
        self.run_id = run_id
        self.budget_usd = budget_usd
        self.provider = inner.provider
        self.model = inner.model
        self.hits = 0
        self.misses = 0

    def complete(self, request: LLMRequest, schema: type[T]) -> Completion[T]:
        key = input_hash(request, schema)
        row = self.session.exec(
            select(LLMCall).where(
                LLMCall.stage == request.stage,
                LLMCall.provider == self.provider,
                LLMCall.model == self.model,
                LLMCall.prompt_version == request.prompt_version,
                LLMCall.input_hash == key,
            )
        ).first()
        if row is not None:
            self.hits += 1
            return Completion(
                result=schema.model_validate(row.output),
                cost=Cost(),  # a cache hit costs nothing
                provider=row.provider,
                model=row.model,
                cached=True,
            )

        self._check_budget()
        completion = self.inner.complete(request, schema)
        self.session.add(
            LLMCall(
                stage=request.stage,
                provider=completion.provider,
                model=completion.model,
                prompt_version=request.prompt_version,
                input_hash=key,
                output=completion.result.model_dump(mode="json"),
                tokens_in=completion.cost.tokens_in,
                tokens_out=completion.cost.tokens_out,
                cost_usd=completion.cost.usd,
                run_id=self.run_id,
            )
        )
        self.session.commit()
        self.misses += 1
        return completion

    def _check_budget(self) -> None:
        if self.budget_usd is None or self.run_id is None:
            return
        spent = spent_usd(self.session, self.run_id)
        if spent >= self.budget_usd:
            raise BudgetExceeded(
                f"Run {self.run_id} has spent ${spent:.4f}, "
                f"at or over its ${self.budget_usd:.2f} cap"
            )
