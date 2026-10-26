from sqlmodel import select

from backend.llm.base import EdgeClassification, LLMRequest
from backend.llm.cache import CachedLLM, input_hash
from backend.llm.fake import FakeProvider
from backend.models import LLMCall


def _request(user: str = "edge between 3.A and 5.B", version: str = "edge-v1") -> LLMRequest:
    return LLMRequest(stage="edge", prompt_version=version, system="classify", user=user)


def test_second_identical_call_is_served_from_cache_with_no_provider_call(session):
    provider = FakeProvider()
    llm = CachedLLM(provider, session)

    first = llm.complete(_request(), EdgeClassification)
    second = llm.complete(_request(), EdgeClassification)

    assert provider.calls == 1
    assert (llm.misses, llm.hits) == (1, 1)
    assert first.cached is False
    assert second.cached is True
    assert second.result == first.result
    assert second.cost.usd == 0.0


def test_changed_prompt_version_input_or_model_is_a_new_call(session):
    provider = FakeProvider()
    llm = CachedLLM(provider, session)
    llm.complete(_request(), EdgeClassification)

    llm.complete(_request(version="edge-v2"), EdgeClassification)
    llm.complete(_request(user="a different edge"), EdgeClassification)
    CachedLLM(FakeProvider(model="fake-2"), session).complete(_request(), EdgeClassification)

    assert provider.calls == 3
    assert len(session.exec(select(LLMCall)).all()) == 4


def test_each_provider_call_writes_one_ledger_row(session):
    llm = CachedLLM(FakeProvider(cost_per_call=0.002), session, run_id="run-1")
    llm.complete(_request(), EdgeClassification)
    llm.complete(_request(), EdgeClassification)  # cache hit: no new row

    row = session.exec(select(LLMCall)).one()
    assert row.stage == "edge"
    assert row.provider == "fake"
    assert row.model == "fake-1"
    assert row.prompt_version == "edge-v1"
    assert row.run_id == "run-1"
    assert row.tokens_in > 0 and row.tokens_out > 0
    assert row.cost_usd == 0.002
    assert EdgeClassification.model_validate(row.output).type in {"required", "optional", "none"}


def test_cache_survives_a_new_wrapper_and_session(engine):
    """The cache is the database, so a fresh process or wrapper still hits it."""
    from sqlmodel import Session

    provider = FakeProvider()
    with Session(engine) as one:
        CachedLLM(provider, one).complete(_request(), EdgeClassification)
    with Session(engine) as two:
        result = CachedLLM(provider, two).complete(_request(), EdgeClassification)

    assert provider.calls == 1
    assert result.cached is True


def test_input_hash_depends_on_input_and_schema_but_not_on_prompt_version():
    base = input_hash(_request(), EdgeClassification)
    assert input_hash(_request(), EdgeClassification) == base
    assert input_hash(_request(user="other"), EdgeClassification) != base
    assert input_hash(_request(version="edge-v9"), EdgeClassification) == base
