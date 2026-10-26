"""Load the sample curriculum into the database, then build and classify its graph.

Everything after the data load is the real code path: `build_candidate_graph`, the edge prompt,
`classify_edges`, the cache and the ledger. Only the data and the classifier are synthetic.
"""

import hashlib
import json
from dataclasses import dataclass

from sqlmodel import Session, select

from backend.graph.build import BuildReport, build_candidate_graph
from backend.graph.classify import ClassifyReport, classify_edges
from backend.llm.cache import CachedLLM
from backend.mockdata import physics
from backend.mockdata.oracle import MockEdgeOracle
from backend.mockdata.questions import build as build_questions
from backend.models import (
    Book,
    ConceptNode,
    Course,
    CrossRef,
    NumberedResult,
    Question,
    QuestionTag,
    Section,
)
from backend.models.enums import (
    BookRole,
    QuestionType,
    ReviewStatus,
    TagSource,
    TagStatus,
    Visibility,
)


@dataclass
class MockSummary:
    course_id: int
    book_id: int
    sections: int
    questions: int
    build: BuildReport
    classified: dict[str, ClassifyReport]


def load_mock_course(session: Session) -> tuple[Course, Book]:
    """Create the sample course, book, sections, numbered results, references and questions.

    Idempotent: if the sample course already exists it is returned untouched.
    """
    course = session.exec(select(Course).where(Course.name == physics.COURSE_NAME)).first()
    book = session.exec(select(Book).where(Book.title == physics.BOOK_TITLE)).first()
    if course is not None and book is not None:
        return course, book

    course = Course(name=physics.COURSE_NAME)
    book = Book(
        title=physics.BOOK_TITLE,
        authors="Synthetic",
        role=BookRole.MAIN.value,
        license="Synthetic sample data. Not taken from any book.",
        visibility=Visibility.OPEN.value,
    )
    session.add_all([course, book])
    session.flush()

    by_number: dict[str, Section] = {}
    results_of: dict[str, list[NumberedResult]] = {}
    page = 1
    for number, title in physics.SECTIONS:
        section = Section(
            book_id=book.id, number=number, title=title, page_start=page, page_end=page + 5
        )
        session.add(section)
        session.flush()
        by_number[number] = section
        results_of[number] = []
        for offset, (kind, label) in enumerate(physics.RESULT_KINDS):
            result = NumberedResult(
                section_id=section.id,
                label=label.format(n=number),
                kind=kind,
                page=page + offset,
            )
            session.add(result)
            session.flush()
            results_of[number].append(result)
        page += 6

    def add_refs(earlier: str, later: str, count: int, forward: bool = False) -> None:
        """`count` references between two sections, spread over up to three results."""
        parts = min(count, 3)
        sizes = [count // parts + (1 if i < count % parts else 0) for i in range(parts)]
        for i, size in enumerate(sizes):
            referring, referred = (earlier, later) if forward else (later, earlier)
            session.add(
                CrossRef(
                    src_result_id=results_of[referring][i].id,
                    dst_result_id=results_of[referred][i].id,
                    count=size,
                )
            )

    for earlier, later, count, _truth in physics.PAIRS:
        add_refs(earlier, later, count)
    for earlier, later, count in physics.FORWARD_REFS:
        add_refs(earlier, later, count, forward=True)
    session.flush()

    # Questions are tagged to nodes, so the graph has to be built first (see seed_mock).
    session.commit()
    session.refresh(course)
    session.refresh(book)
    return course, book


def load_mock_questions(session: Session, course: Course, book: Book) -> int:
    """Add the sample questions and tag them to nodes. Needs the nodes to exist."""
    if session.exec(select(Question).where(Question.book_id == book.id)).first():
        return 0
    node_of_number = {
        section.number: node.id
        for node in session.exec(select(ConceptNode).where(ConceptNode.course_id == course.id))
        for section in [session.get(Section, node.section_id)]
        if section is not None
    }
    section_of_number = {
        s.number: s.id for s in session.exec(select(Section).where(Section.book_id == book.id))
    }
    created = 0
    for mock in build_questions():
        digest = hashlib.sha256(
            (mock.latex + json.dumps(mock.answer_key, sort_keys=True)).encode()
        ).hexdigest()
        question = Question(
            book_id=book.id,
            section_id=section_of_number[mock.sections[0]],
            latex=mock.latex,
            type=QuestionType(mock.type).value,
            options=mock.options,
            answer_key=mock.answer_key,
            difficulty_prior=mock.difficulty,
            review_status=ReviewStatus.APPROVED.value,
            content_hash=digest,
        )
        session.add(question)
        session.flush()
        for index, number in enumerate(mock.sections):
            session.add(
                QuestionTag(
                    question_id=question.id,
                    node_id=node_of_number[number],
                    is_primary=index == 0,
                    source=TagSource.MOCK.value,
                    confidence=1.0,
                    status=TagStatus.ACCEPTED.value,
                )
            )
        created += 1
    session.commit()
    return created


def seed_mock(session: Session, min_weight: int = 2) -> MockSummary:
    """Load the sample data, build its candidate graph and classify it with both mock pipelines."""
    course, book = load_mock_course(session)
    report = build_candidate_graph(
        session,
        course.id,
        book.id,
        min_weight=min_weight,
        world_of=lambda section: physics.WORLDS[section.number.split(".")[0]],
    )
    classified: dict[str, ClassifyReport] = {}
    for pipeline in ("A", "B"):
        llm = CachedLLM(MockEdgeOracle(pipeline), session, run_id=f"mock-{pipeline}")
        classified[pipeline] = classify_edges(session, course.id, llm, pipeline)
    questions = load_mock_questions(session, course, book)
    sections = len(session.exec(select(Section).where(Section.book_id == book.id)).all())
    return MockSummary(course.id, book.id, sections, questions, report, classified)
