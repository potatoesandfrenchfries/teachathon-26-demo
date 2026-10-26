"""Round-trip one row of each week 1 table, and check the constraints that matter."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.models import (
    Book,
    ConceptNode,
    Course,
    CrossRef,
    Edge,
    GraphEdit,
    LLMCall,
    NumberedResult,
    Question,
    QuestionTag,
    Section,
)
from backend.models.enums import EdgeStatus, EditOp, GraphStatus


def _course_with_two_nodes(session: Session) -> tuple[Course, ConceptNode, ConceptNode]:
    course = Course(name="Test course")
    session.add(course)
    session.commit()
    a = ConceptNode(course_id=course.id, title="A")
    b = ConceptNode(course_id=course.id, title="B")
    session.add_all([a, b])
    session.commit()
    return course, a, b


def test_course_and_book_defaults(session):
    course = Course(name="Linear algebra")
    book = Book(title="Linear Algebra Done Right", file_sha256="abc")
    session.add_all([course, book])
    session.commit()

    assert course.lock_mode == "soft"
    assert course.graph_status == GraphStatus.DRAFT
    assert course.graph_version == 1
    assert course.default_threshold == 0.95
    assert book.role == "main"
    assert book.visibility == "internal_only"


def test_book_section_result_and_cross_ref_round_trip(session):
    book = Book(title="B")
    session.add(book)
    session.commit()
    section = Section(book_id=book.id, number="3.A", title="Invariant subspaces", page_start=10)
    session.add(section)
    session.commit()
    r1 = NumberedResult(section_id=section.id, label="3.22", kind="definition", page=11)
    r2 = NumberedResult(section_id=section.id, label="3.23", kind="theorem", page=12)
    session.add_all([r1, r2])
    session.commit()
    session.add(CrossRef(src_result_id=r2.id, dst_result_id=r1.id, count=2))
    session.commit()

    ref = session.exec(select(CrossRef)).one()
    assert (ref.src_result_id, ref.dst_result_id, ref.count) == (r2.id, r1.id, 2)


def test_concept_node_edge_and_edit_round_trip(session):
    course, a, b = _course_with_two_nodes(session)
    classifications = {"A": {"type": "required", "confidence": 0.8}, "B": {"type": "optional"}}
    edge = Edge(
        course_id=course.id, src_node=a.id, dst_node=b.id, weight=3, classifications=classifications
    )
    session.add(edge)
    session.add(
        GraphEdit(
            course_id=course.id,
            graph_version=1,
            actor="admin",
            op=EditOp.ADD_EDGE,
            target_id=1,
            before=None,
            after={"src": a.id, "dst": b.id},
        )
    )
    session.commit()
    session.expire_all()

    stored = session.exec(select(Edge)).one()
    assert stored.classifications == classifications
    assert stored.status == EdgeStatus.PROPOSED
    edit = session.exec(select(GraphEdit)).one()
    assert edit.op == "add_edge"
    assert edit.before is None
    assert edit.after == {"src": a.id, "dst": b.id}


def test_edge_pair_is_unique_per_course(session):
    course, a, b = _course_with_two_nodes(session)
    session.add(Edge(course_id=course.id, src_node=a.id, dst_node=b.id))
    session.commit()
    session.add(Edge(course_id=course.id, src_node=a.id, dst_node=b.id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_foreign_keys_are_enforced(session):
    session.add(ConceptNode(course_id=999, title="orphan"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_llm_call_round_trip_and_unique_key(session):
    def call() -> LLMCall:
        return LLMCall(
            stage="edge",
            provider="fake",
            model="fake-1",
            prompt_version="edge-v1",
            input_hash="h",
            output={"type": "required"},
            tokens_in=10,
            tokens_out=5,
            cost_usd=0.001,
            run_id="run-1",
        )

    session.add(call())
    session.commit()
    stored = session.exec(select(LLMCall)).one()
    assert stored.output == {"type": "required"}
    assert stored.cost_usd == 0.001

    session.add(call())
    with pytest.raises(IntegrityError):
        session.commit()


def test_question_and_tag_round_trip_with_defaults(session):
    course, node, _ = _course_with_two_nodes(session)
    book = Book(title="B")
    session.add(book)
    session.commit()
    options = [
        {"label": "A", "text": "Zero", "misconception": None},
        {"label": "B", "text": "Along the motion", "misconception": "Force keeps things moving"},
    ]
    question = Question(
        book_id=book.id,
        latex=r"What is the net force on an object at constant velocity?",
        type="mcq",
        options=options,
        answer_key={"correct": "A"},
        difficulty_prior=-0.3,
    )
    session.add(question)
    session.commit()
    session.add(QuestionTag(question_id=question.id, node_id=node.id, is_primary=True))
    session.commit()
    session.expire_all()

    stored = session.exec(select(Question)).one()
    assert stored.options == options
    assert stored.answer_key == {"correct": "A"}
    assert stored.review_status == "needs_review"  # nothing is approved by default
    assert stored.pipeline is None  # hand-written or sample questions carry no provenance
    tag = session.exec(select(QuestionTag)).one()
    assert (tag.is_primary, tag.source, tag.status) == (True, "llm", "proposed")


def test_a_question_can_be_tagged_to_a_node_only_once(session):
    course, node, _ = _course_with_two_nodes(session)
    book = Book(title="B")
    session.add(book)
    session.commit()
    question = Question(book_id=book.id, latex="q", answer_key={})
    session.add(question)
    session.commit()
    session.add(QuestionTag(question_id=question.id, node_id=node.id))
    session.commit()
    session.add(QuestionTag(question_id=question.id, node_id=node.id))
    with pytest.raises(IntegrityError):
        session.commit()
