"""Budget cap and resumable runs."""

import pytest
from sqlmodel import Session, select

from backend.llm.base import EdgeClassification, LLMRequest
from backend.llm.cache import CachedLLM, spent_usd
from backend.llm.fake import FakeProvider
from backend.llm.run import BudgetExceeded, RunManifest
from backend.models import LLMCall


def _request(item: int) -> LLMRequest:
    return LLMRequest(stage="edge", prompt_version="edge-v1", user=f"edge {item}")


def test_exceeding_the_cap_raises_before_the_next_provider_call(session):
    provider = FakeProvider(cost_per_call=0.01)
    llm = CachedLLM(provider, session, run_id="r", budget_usd=0.025)

    for item in range(3):  # spends 0.03, so the cap is passed during the third call
        llm.complete(_request(item), EdgeClassification)
    assert provider.calls == 3
    assert spent_usd(session, "r") == pytest.approx(0.03)

    with pytest.raises(BudgetExceeded):
        llm.complete(_request(3), EdgeClassification)
    assert provider.calls == 3  # the fourth call was never made


def test_cache_hits_are_free_even_after_the_cap_is_reached(session):
    provider = FakeProvider(cost_per_call=0.01)
    llm = CachedLLM(provider, session, run_id="r", budget_usd=0.01)
    llm.complete(_request(0), EdgeClassification)

    assert llm.complete(_request(0), EdgeClassification).cached is True
    with pytest.raises(BudgetExceeded):
        llm.complete(_request(1), EdgeClassification)


def test_spend_is_counted_per_run(session):
    CachedLLM(FakeProvider(cost_per_call=0.01), session, run_id="a").complete(
        _request(0), EdgeClassification
    )
    CachedLLM(FakeProvider(cost_per_call=0.01), session, run_id="b").complete(
        _request(1), EdgeClassification
    )
    assert spent_usd(session, "a") == pytest.approx(0.01)
    assert spent_usd(session, "b") == pytest.approx(0.01)
    assert spent_usd(session, "nobody") == 0.0


def _classify_all(manifest: RunManifest, llm: CachedLLM, items: range) -> None:
    for item in items:
        manifest.process(
            f"edge-{item}", lambda item=item: llm.complete(_request(item), EdgeClassification)
        )


def test_a_killed_run_resumes_without_repeating_provider_calls(engine, tmp_path):
    items = range(5)

    # First attempt: the provider "crashes" on the third call, so two items finish.
    crashing = FakeProvider(fail_after=2)
    with Session(engine) as session:
        manifest = RunManifest.open(tmp_path, "run-1")
        with pytest.raises(RuntimeError):
            _classify_all(manifest, CachedLLM(crashing, session, run_id="run-1"), items)
    assert crashing.calls == 2

    # Resume with the same run id: reopen the manifest and carry on.
    healthy = FakeProvider()
    with Session(engine) as session:
        manifest = RunManifest.open(tmp_path, "run-1")
        assert manifest.done == {"edge-0", "edge-1"}
        _classify_all(manifest, CachedLLM(healthy, session, run_id="run-1"), items)

    assert healthy.calls == 3  # only the three unfinished items
    with Session(engine) as session:
        assert len(session.exec(select(LLMCall)).all()) == 5  # each item paid for exactly once


def test_rerunning_a_finished_run_makes_no_calls(engine, tmp_path):
    provider = FakeProvider()
    with Session(engine) as session:
        llm = CachedLLM(provider, session, run_id="run-2")
        _classify_all(RunManifest.open(tmp_path, "run-2"), llm, range(4))
        assert provider.calls == 4
        _classify_all(RunManifest.open(tmp_path, "run-2"), llm, range(4))
    assert provider.calls == 4


def test_manifest_is_saved_after_every_item_and_ignores_a_stray_tmp_file(tmp_path):
    manifest = RunManifest.open(tmp_path, "run-3")
    manifest.mark_done("a")
    (tmp_path / "run-3.tmp").write_text("{ half written")  # a kill during a save

    reopened = RunManifest.open(tmp_path, "run-3")
    assert reopened.done == {"a"}
    assert reopened.process("a", lambda: pytest.fail("should be skipped")) is False
