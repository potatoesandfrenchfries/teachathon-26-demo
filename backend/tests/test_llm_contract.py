"""Every provider must pass these.

The HTTP providers run here against a mocked server, so the suite needs no key and no network.
The same checks against the real services are in test_providers_live.py.

To add a provider: put a factory for it in PROVIDERS below.
"""

import pytest
from sqlmodel import select

from backend.llm.base import Completion, EdgeClassification, LLMRequest
from backend.llm.cache import CachedLLM
from backend.llm.fake import FakeProvider
from backend.llm.local import LocalProvider
from backend.llm.openrouter import OpenRouterProvider
from backend.models import LLMCall
from backend.tests.http_mock import ok


def _openrouter() -> OpenRouterProvider:
    return OpenRouterProvider(api_key="test-key", client=ok().client)


def _local() -> LocalProvider:
    return LocalProvider(client=ok().client)


PROVIDERS = [
    pytest.param(FakeProvider, id="fake"),
    pytest.param(_openrouter, id="openrouter"),
    pytest.param(_local, id="local"),
]

REQUEST = LLMRequest(
    stage="edge",
    prompt_version="edge-v1",
    system="Classify the prerequisite relationship between two textbook sections.",
    user="Section 3.A (Invariant subspaces) -> Section 5.B (Eigenvectors). 4 cross-references.",
)


@pytest.fixture(params=PROVIDERS)
def provider(request):
    return request.param()


def test_returns_a_valid_edge_classification(provider):
    completion = provider.complete(REQUEST, EdgeClassification)

    assert isinstance(completion, Completion)
    assert completion.result.type in {"required", "optional", "none"}
    assert completion.result.justification
    assert 0.0 <= completion.result.confidence <= 1.0
    assert completion.provider == provider.provider
    assert completion.model == provider.model


def test_reports_a_non_negative_cost(provider):
    cost = provider.complete(REQUEST, EdgeClassification).cost
    assert cost.tokens_in >= 0 and cost.tokens_out >= 0 and cost.usd >= 0.0


def test_a_repeat_call_through_the_cache_is_a_hit(provider, session):
    llm = CachedLLM(provider, session)
    first = llm.complete(REQUEST, EdgeClassification)
    second = llm.complete(REQUEST, EdgeClassification)

    assert first.cached is False
    assert second.cached is True
    assert second.result == first.result
    assert (llm.misses, llm.hits) == (1, 1)


def test_a_ledger_row_is_written_for_the_provider_call(provider, session):
    CachedLLM(provider, session, run_id="contract").complete(REQUEST, EdgeClassification)

    row = session.exec(select(LLMCall)).one()
    assert (row.provider, row.model) == (provider.provider, provider.model)
    assert row.stage == "edge" and row.prompt_version == "edge-v1"
    assert row.run_id == "contract"
