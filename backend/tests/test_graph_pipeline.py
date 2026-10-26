"""Candidate graph, edge prompt, classification runner and the mock sample data."""

import pytest
from sqlmodel import select

from backend.graph.build import GraphFrozenError, build_candidate_graph, section_pair_weights
from backend.graph.classify import classify_edges
from backend.graph.prompts import PROMPT_VERSION, SYSTEM, edge_request
from backend.graph.review import pipelines_disagree, review_rank
from backend.llm.cache import CachedLLM
from backend.llm.fake import FakeProvider
from backend.llm.run import RunManifest
from backend.mockdata import physics
from backend.mockdata.load import load_mock_course, load_mock_questions, seed_mock
from backend.mockdata.oracle import MockEdgeOracle
from backend.models import ConceptNode, Course, Edge, LLMCall, Question, QuestionTag, Section
from backend.models.enums import EdgeSource, EdgeStatus, GraphStatus


@pytest.fixture
def mock(session):
    course, book = load_mock_course(session)
    return course, book


def _number_of(session, node_id: int) -> str:
    return session.get(ConceptNode, node_id).title.split(" ")[0]


# --- Candidate graph (W1-18) ------------------------------------------------------------------


def test_one_node_per_section_and_edges_only_above_the_threshold(session, mock):
    course, book = mock
    report = build_candidate_graph(session, course.id, book.id, min_weight=2)

    nodes = session.exec(select(ConceptNode)).all()
    edges = session.exec(select(Edge)).all()
    assert report.nodes_created == len(physics.SECTIONS) == len(nodes)
    assert report.pairs_below_threshold == 2  # the two count-1 pairs
    expected = [p for p in physics.PAIRS if p[2] >= 2]
    assert len(edges) == len(expected) == report.edges_created
    assert all(e.status == EdgeStatus.PROPOSED and e.source == EdgeSource.XREF for e in edges)
    assert all(e.classifications == {} for e in edges)  # nothing classified yet


def test_edges_point_from_the_earlier_section_to_the_later_one(session, mock):
    course, book = mock
    build_candidate_graph(session, course.id, book.id, min_weight=2)

    for edge in session.exec(select(Edge)):
        assert edge.src_node < edge.dst_node  # nodes were created in section order


def test_the_threshold_is_a_parameter_and_a_forward_reference_still_counts(session, mock):
    course, book = mock
    weights = section_pair_weights(session, book.id)
    by_number = {s.number: s.id for s in session.exec(select(Section))}
    # 2.2 -> 3.1 has 4 references from 3.1 plus 1 forward reference from 2.2.
    assert weights[(by_number["2.2"], by_number["3.1"])] == 5

    build_candidate_graph(session, course.id, book.id, min_weight=1)
    assert len(session.exec(select(Edge)).all()) == len(physics.PAIRS)


def test_world_groups_default_to_the_chapter(session, mock):
    course, book = mock
    build_candidate_graph(session, course.id, book.id, min_weight=2)
    groups = {n.world_group for n in session.exec(select(ConceptNode))}
    assert groups == {"Chapter 1", "Chapter 2", "Chapter 3", "Chapter 4", "Chapter 5"}


def test_rebuilding_changes_nothing_and_never_touches_a_manual_edge(session, mock):
    course, book = mock
    build_candidate_graph(session, course.id, book.id, min_weight=2)
    manual = session.exec(select(Edge)).first()
    manual.source = EdgeSource.MANUAL.value
    manual.weight = 99
    manual.type = "optional"
    session.add(manual)
    session.commit()
    before = {e.id: (e.weight, e.type, e.source) for e in session.exec(select(Edge))}

    report = build_candidate_graph(session, course.id, book.id, min_weight=2)

    assert (report.nodes_created, report.edges_created, report.edges_updated) == (0, 0, 0)
    assert report.edges_skipped_manual == 1
    assert {e.id: (e.weight, e.type, e.source) for e in session.exec(select(Edge))} == before


def test_an_approved_graph_cannot_be_rebuilt(session, mock):
    course, book = mock
    course.graph_status = GraphStatus.APPROVED.value
    session.add(course)
    session.commit()
    with pytest.raises(GraphFrozenError):
        build_candidate_graph(session, course.id, book.id, min_weight=2)


# --- Prompt (W1-20) -------------------------------------------------------------------------------


def test_the_prompt_carries_both_sections_their_results_and_the_references(session, mock):
    course, book = mock
    build_candidate_graph(session, course.id, book.id, min_weight=2)
    edge = next(
        e
        for e in session.exec(select(Edge))
        if (_number_of(session, e.src_node), _number_of(session, e.dst_node)) == ("2.2", "3.1")
    )

    request = edge_request(session, edge)

    assert (request.stage, request.prompt_version) == ("edge", PROMPT_VERSION)
    assert PROMPT_VERSION == "edge-v1"
    assert request.system == SYSTEM
    assert "FROM: 2.2 Acceleration and constant-acceleration motion" in request.user
    assert "TO: 3.1 Newton's first and second laws" in request.user
    assert "Eq. 2.2.1 (equation)" in request.user
    assert "(total 5)" in request.user  # four references back, one forward
    assert "Example 3.1.1 in TO refers to Example 2.2.1 in FROM" in request.user
    assert "Eq. 2.2.1 in FROM refers to Eq. 3.1.1 in TO (once)" in request.user  # forward


def test_the_same_edge_always_gives_the_same_prompt(session, mock):
    course, book = mock
    build_candidate_graph(session, course.id, book.id, min_weight=2)
    edge = session.exec(select(Edge)).first()
    assert edge_request(session, edge) == edge_request(session, edge)


# --- Classification runner (W1-21) ----------------------------------------------------------------


def _built(session, mock):
    course, book = mock
    build_candidate_graph(session, course.id, book.id, min_weight=2)
    return course


def test_a_fake_provider_run_classifies_every_edge(session, mock):
    course = _built(session, mock)
    llm = CachedLLM(FakeProvider(), session, run_id="r")

    report = classify_edges(session, course.id, llm, "A")

    edges = session.exec(select(Edge)).all()
    assert report.classified == len(edges)
    for edge in edges:
        entry = edge.classifications["A"]
        assert entry["type"] in {"required", "optional", "none"}
        assert entry["prompt_version"] == "edge-v1"
        assert entry["provider"] == "fake"
        assert edge.justification == entry["justification"]


def test_rerunning_makes_no_new_provider_calls(session, mock):
    course = _built(session, mock)
    provider = FakeProvider()
    llm = CachedLLM(provider, session, run_id="r")
    classify_edges(session, course.id, llm, "A")
    calls = provider.calls

    again = classify_edges(session, course.id, CachedLLM(provider, session, run_id="r2"), "A")

    assert provider.calls == calls
    assert (again.classified, again.already_done) == (0, len(session.exec(select(Edge)).all()))


def test_a_different_model_or_prompt_makes_edges_eligible_again(session, mock):
    course = _built(session, mock)
    classify_edges(session, course.id, CachedLLM(FakeProvider(model="fake-1"), session), "A")

    other = FakeProvider(model="fake-2")
    report = classify_edges(session, course.id, CachedLLM(other, session), "A")

    assert report.already_done == 0 and report.classified == other.calls > 0
    assert all(e.classifications["A"]["model"] == "fake-2" for e in session.exec(select(Edge)))


def test_a_killed_run_resumes_without_repeating_calls(session, mock, tmp_path):
    course = _built(session, mock)
    total = len(session.exec(select(Edge)).all())

    crashing = FakeProvider(fail_after=5)
    manifest = RunManifest.open(tmp_path, "edges")
    with pytest.raises(RuntimeError):
        classify_edges(
            session, course.id, CachedLLM(crashing, session, run_id="edges"), "A", manifest
        )
    assert crashing.calls == 5

    healthy = FakeProvider()
    report = classify_edges(
        session,
        course.id,
        CachedLLM(healthy, session, run_id="edges"),
        "A",
        RunManifest.open(tmp_path, "edges"),
    )

    assert report.already_done == 5
    assert healthy.calls == total - 5
    assert len(session.exec(select(LLMCall)).all()) == total


def test_manual_edges_are_never_reclassified(session, mock):
    course = _built(session, mock)
    manual = session.exec(select(Edge)).first()
    manual.source = EdgeSource.MANUAL.value
    manual.type = "optional"
    manual.justification = "Professor says so."
    session.add(manual)
    session.commit()

    report = classify_edges(session, course.id, CachedLLM(FakeProvider(), session), "A")

    session.refresh(manual)
    assert report.skipped_manual == 1
    assert manual.classifications == {}
    assert (manual.type, manual.justification) == ("optional", "Professor says so.")


def test_a_reviewed_edge_keeps_its_type_when_a_pipeline_runs(session, mock):
    course = _built(session, mock)
    edge = session.exec(select(Edge)).first()
    edge.status = EdgeStatus.ACCEPTED.value
    edge.type = "optional"
    session.add(edge)
    session.commit()

    classify_edges(session, course.id, CachedLLM(MockEdgeOracle("A"), session), "A")

    session.refresh(edge)
    assert "A" in edge.classifications  # the verdict is recorded
    assert edge.type == "optional"  # but the professor's decision stands


def test_pipeline_a_leads_and_b_is_recorded_alongside(session, mock):
    course = _built(session, mock)
    classify_edges(session, course.id, CachedLLM(MockEdgeOracle("B"), session), "B")
    classify_edges(session, course.id, CachedLLM(MockEdgeOracle("A"), session), "A")

    for edge in session.exec(select(Edge)):
        assert set(edge.classifications) == {"A", "B"}
        a = edge.classifications["A"]["type"]
        if a in ("required", "optional"):
            assert edge.type == a


def test_the_limit_stops_early(session, mock):
    course = _built(session, mock)
    report = classify_edges(session, course.id, CachedLLM(FakeProvider(), session), "A", limit=3)
    assert report.attempted == 3
    assert sum(1 for e in session.exec(select(Edge)) if e.classifications) == 3


def test_an_approved_graph_cannot_be_reclassified(session, mock):
    course = _built(session, mock)
    course.graph_status = GraphStatus.APPROVED.value
    session.add(course)
    session.commit()
    with pytest.raises(GraphFrozenError):
        classify_edges(session, course.id, CachedLLM(FakeProvider(), session), "A")


# --- Review ranking -------------------------------------------------------------------------------


def test_disagreement_and_rank():
    agree = {
        "A": {"type": "required", "confidence": 0.9},
        "B": {"type": "required", "confidence": 0.8},
    }
    differ = {
        "A": {"type": "required", "confidence": 0.9},
        "B": {"type": "optional", "confidence": 0.7},
    }
    single = {"A": {"type": "none", "confidence": 0.9}}

    assert not pipelines_disagree(agree)
    assert pipelines_disagree(differ)
    assert not pipelines_disagree(single)  # one opinion cannot disagree with itself
    assert not pipelines_disagree({})
    ranked = sorted(
        [("agree", agree, 5), ("differ", differ, 1), ("none", {}, 9)],
        key=lambda item: review_rank(item[1], item[2]),
    )
    assert [name for name, *_ in ranked] == ["differ", "none", "agree"]


# --- Mock data ------------------------------------------------------------------------------------


def test_mock_loading_is_idempotent(session):
    first = load_mock_course(session)
    second = load_mock_course(session)
    assert first[0].id == second[0].id and first[1].id == second[1].id
    assert len(session.exec(select(Course)).all()) == 1


def test_the_mock_oracle_follows_the_truth_and_pipeline_b_sometimes_disagrees(session, mock):
    course = _built(session, mock)
    classify_edges(session, course.id, CachedLLM(MockEdgeOracle("A"), session), "A")
    classify_edges(session, course.id, CachedLLM(MockEdgeOracle("B"), session), "B")

    disagreements = 0
    for edge in session.exec(select(Edge)):
        src, dst = _number_of(session, edge.src_node), _number_of(session, edge.dst_node)
        assert edge.classifications["A"]["type"] == physics.truth(src, dst)
        disagreements += pipelines_disagree(edge.classifications)
    assert 1 <= disagreements < len(physics.PAIRS) // 2


def test_seed_mock_builds_the_whole_sample_and_is_safe_to_repeat(session):
    summary = seed_mock(session)
    assert summary.sections == 16
    assert summary.build.edges_created == len([p for p in physics.PAIRS if p[2] >= 2])
    assert summary.classified["A"].classified == summary.build.edges_created
    assert summary.questions >= 30

    again = seed_mock(session)
    assert again.build.nodes_created == again.build.edges_created == again.questions == 0
    assert len(session.exec(select(Edge)).all()) == summary.build.edges_created


def test_mock_questions_are_well_formed_and_tagged_to_real_nodes(session, mock):
    course, book = mock
    build_candidate_graph(session, course.id, book.id, min_weight=2)
    assert load_mock_questions(session, course, book) > 0
    assert load_mock_questions(session, course, book) == 0  # repeat adds nothing

    node_ids = {n.id for n in session.exec(select(ConceptNode))}
    for question in session.exec(select(Question)):
        tags = session.exec(select(QuestionTag).where(QuestionTag.question_id == question.id)).all()
        assert 1 <= len(tags) <= 3  # the plan caps tags per question at three
        assert sum(t.is_primary for t in tags) == 1
        assert {t.node_id for t in tags} <= node_ids
        assert question.review_status == "approved" and question.content_hash
        if question.type == "numeric":
            assert question.answer_key["value"] >= 0
            assert question.answer_key["tolerance_rel"] > 0
        else:
            labels = [o["label"] for o in question.options]
            assert question.answer_key["correct"] in labels
            wrong = [o for o in question.options if o["label"] != question.answer_key["correct"]]
            assert all(o["misconception"] for o in wrong)  # every distractor names a misconception


def test_every_node_has_at_least_one_question(session):
    seed_mock(session)
    primary = {t.node_id for t in session.exec(select(QuestionTag)) if t.is_primary}
    assert primary == {n.id for n in session.exec(select(ConceptNode))}
