"""One real call per hosted provider. Skipped unless you opt in, because it spends real money.

    OPENROUTER_API_KEY=... TA_LIVE=1 uv run pytest tests/test_providers_live.py -q

The local provider is not exercised here: it has only been tested against a mocked server.
"""

import os

import pytest

from backend.llm.base import EdgeClassification, LLMRequest
from backend.llm.openrouter import OpenRouterProvider
from backend.settings import Settings

pytestmark = pytest.mark.skipif(
    not (os.environ.get("TA_LIVE") == "1" and os.environ.get("OPENROUTER_API_KEY")),
    reason="set TA_LIVE=1 and OPENROUTER_API_KEY to run the live provider test",
)


def test_openrouter_returns_a_valid_edge_classification_and_a_real_cost():
    settings = Settings(_env_file=None)
    provider = OpenRouterProvider(
        api_key=settings.openrouter_api_key, model=settings.openrouter_model
    )
    request = LLMRequest(
        stage="edge",
        prompt_version="live-check",
        system="Classify whether section TO depends on section FROM. Answer with JSON only.",
        user=(
            "FROM: 2.2 Acceleration and constant-acceleration motion\n"
            "TO: 3.1 Newton's first and second laws\n"
            "Cross-references: 4. How much does TO depend on FROM?"
        ),
    )

    completion = provider.complete(request, EdgeClassification)

    assert completion.result.type in {"required", "optional", "none"}
    assert completion.result.justification
    assert completion.cost.tokens_in > 0 and completion.cost.tokens_out > 0
    assert completion.cost.usd > 0
