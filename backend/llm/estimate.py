"""Rough cost estimates for dry runs. These are estimates, not measurements."""

import json
from collections.abc import Iterable

from pydantic import BaseModel

from backend.llm.base import Cost, LLMRequest
from backend.llm.openai_compat import strict_json_schema


def estimate_tokens(text: str) -> int:
    """About four characters per token for English text and LaTeX. Replace with a real count
    before trusting a large run."""
    return max(1, len(text) // 4)


def estimate_cost(
    requests: Iterable[LLMRequest],
    schema: type[BaseModel],
    usd_per_token_in: float,
    usd_per_token_out: float,
    expected_output_tokens: int = 120,
) -> Cost:
    """Estimated total cost of `requests`, each expecting `expected_output_tokens` back."""
    schema_tokens = estimate_tokens(json.dumps(strict_json_schema(schema)))
    tokens_in = tokens_out = 0
    for request in requests:
        tokens_in += estimate_tokens(request.system + request.user) + schema_tokens
        tokens_out += expected_output_tokens
    usd = tokens_in * usd_per_token_in + tokens_out * usd_per_token_out
    return Cost(tokens_in=tokens_in, tokens_out=tokens_out, usd=usd)
