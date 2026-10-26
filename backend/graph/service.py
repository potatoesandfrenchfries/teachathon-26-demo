"""Reading the graph and the professor's edits to it. Plain functions over a Session.

Every write checks for cycles first, is recorded in the GraphEdit audit log, and returns the
resulting graph, so a client never has to guess what the server now holds.
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from backend.graph.dag import CycleError, cycle_if_added, transitive_reduction
from backend.graph.review import pipelines_disagree, review_rank
from backend.models import (
    ConceptNode,
    Course,
    CrossRef,
    Edge,
    GraphEdit,
    NumberedResult,
    QuestionTag,
    Section,
)
from backend.models.enums import EdgeSource, EdgeStatus, EdgeType, EditOp, GraphStatus, TagStatus
from backend.schemas.graph import (
    ClassificationOut,
    CourseOut,
    CrossRefOut,
    EdgeOut,
    EvidenceOut,
    GraphOut,
    NodeOut,
)

ACTOR = "admin"  # one shared admin key for now, so there is only one actor


class GraphError(Exception):
    """A request the server refuses. `status_code` is the HTTP status the API should send."""

    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFound(GraphError):
    status_code = 404


class Conflict(GraphError):
    status_code = 409


# --- Reading --------------------------------------------------------------------------------------


def list_courses(session: Session) -> list[CourseOut]:
    return [_course_out(c) for c in session.exec(select(Course).order_by(Course.id))]


def _course_out(course: Course) -> CourseOut:
    return CourseOut(
        id=course.id,
        name=course.name,
        graph_status=course.graph_status,
        graph_version=course.graph_version,
        lock_mode=course.lock_mode,
    )


def _course(session: Session, course_id: int | None) -> Course:
    if course_id is None:
        course = session.exec(select(Course).order_by(Course.id)).first()
        if course is None:
            raise NotFound("There is no course yet. Seed one first.")
        return course
    course = session.get(Course, course_id)
    if course is None:
        raise NotFound(f"No course with id {course_id}")
    return course


def _active_pairs(
    session: Session, course_id: int, skip_edge_id: int | None = None
) -> list[tuple[int, int]]:
    """Node pairs of the edges that count: everything not rejected."""
    return [
        (e.src_node, e.dst_node)
        for e in session.exec(select(Edge).where(Edge.course_id == course_id))
        if e.status != EdgeStatus.REJECTED.value and e.id != skip_edge_id
    ]


def _evidence(session: Session, nodes: list[ConceptNode]) -> dict[frozenset[int], EvidenceOut]:
    """Cross-references grouped by the pair of nodes whose sections they connect."""
    node_of_section = {n.section_id: n.id for n in nodes if n.section_id is not None}
    if not node_of_section:
        return {}
    sections = {
        s.id: s.number
        for s in session.exec(select(Section).where(Section.id.in_(list(node_of_section))))
    }
    results = {
        r.id: r
        for r in session.exec(
            select(NumberedResult).where(NumberedResult.section_id.in_(list(node_of_section)))
        )
    }
    grouped: dict[frozenset[int], list[CrossRefOut]] = defaultdict(list)
    for ref in session.exec(select(CrossRef)):
        referring, referred = results.get(ref.src_result_id), results.get(ref.dst_result_id)
        if referring is None or referred is None or referring.section_id == referred.section_id:
            continue
        pair = frozenset(
            (node_of_section[referring.section_id], node_of_section[referred.section_id])
        )
        grouped[pair].append(
            CrossRefOut(
                referring=referring.label,
                referring_section=sections[referring.section_id],
                referred=referred.label,
                referred_section=sections[referred.section_id],
                count=ref.count,
            )
        )
    return {
        pair: EvidenceOut(total=sum(r.count for r in refs), crossrefs=refs)
        for pair, refs in grouped.items()
    }


def get_graph(session: Session, course_id: int | None = None) -> GraphOut:
    course = _course(session, course_id)
    nodes = session.exec(
        select(ConceptNode).where(ConceptNode.course_id == course.id).order_by(ConceptNode.id)
    ).all()
    edges = session.exec(select(Edge).where(Edge.course_id == course.id).order_by(Edge.id)).all()

    section_numbers = {
        s.id: s.number
        for s in session.exec(
            select(Section).where(Section.id.in_([n.section_id for n in nodes if n.section_id]))
        )
    }
    question_counts = dict(
        session.exec(
            select(QuestionTag.node_id, func.count(QuestionTag.question_id))
            .where(QuestionTag.status != TagStatus.REJECTED.value)
            .group_by(QuestionTag.node_id)
        ).all()
    )
    evidence = _evidence(session, list(nodes))

    active = [(e.src_node, e.dst_node) for e in edges if e.status != EdgeStatus.REJECTED.value]
    try:
        hidden_pairs = set(transitive_reduction(active).hidden)
    except CycleError:  # cannot happen while edits are checked, but never fail a read over it
        hidden_pairs = set()

    edge_outs: list[EdgeOut] = []
    for edge in edges:
        pair = (edge.src_node, edge.dst_node)
        edge_outs.append(
            EdgeOut(
                id=edge.id,
                src_node=edge.src_node,
                dst_node=edge.dst_node,
                type=edge.type,
                weight=edge.weight,
                source=edge.source,
                status=edge.status,
                justification=edge.justification,
                classifications={
                    pipeline: ClassificationOut(**entry)
                    for pipeline, entry in edge.classifications.items()
                },
                disagreement=pipelines_disagree(edge.classifications),
                hidden=pair in hidden_pairs and edge.status != EdgeStatus.REJECTED.value,
                evidence=evidence.get(frozenset(pair), EvidenceOut(total=0, crossrefs=[])),
            )
        )

    queue = sorted(
        (e for e in edges if e.status == EdgeStatus.PROPOSED.value),
        key=lambda e: review_rank(e.classifications, e.weight),
    )
    return GraphOut(
        course=_course_out(course),
        nodes=[
            NodeOut(
                id=n.id,
                title=n.title,
                section_number=section_numbers.get(n.section_id),
                world_group=n.world_group,
                threshold=n.threshold,
                k_required=n.k_required,
                origin=n.origin,
                question_count=question_counts.get(n.id, 0),
            )
            for n in nodes
        ],
        edges=edge_outs,
        review_queue=[e.id for e in queue],
    )


def list_edits(session: Session, course_id: int | None = None, limit: int = 200) -> list[GraphEdit]:
    course = _course(session, course_id)
    return list(
        session.exec(
            select(GraphEdit)
            .where(GraphEdit.course_id == course.id)
            .order_by(GraphEdit.id.desc())
            .limit(limit)
        )
    )


# --- Writing --------------------------------------------------------------------------------------


def _editable(session: Session, course_id: int) -> Course:
    course = session.get(Course, course_id)
    if course.graph_status == GraphStatus.APPROVED.value:
        raise Conflict("The graph is approved and frozen. Re-open it to make changes.")
    return course


def _edge(session: Session, edge_id: int) -> Edge:
    edge = session.get(Edge, edge_id)
    if edge is None:
        raise NotFound(f"No edge with id {edge_id}")
    return edge


def _snapshot(edge: Edge) -> dict[str, Any]:
    return {
        "src_node": edge.src_node,
        "dst_node": edge.dst_node,
        "type": edge.type,
        "status": edge.status,
        "source": edge.source,
    }


def _log(
    session: Session,
    course: Course,
    op: EditOp,
    target_id: int | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    session.add(
        GraphEdit(
            course_id=course.id,
            graph_version=course.graph_version,
            actor=ACTOR,
            op=op.value,
            target_id=target_id,
            before=before,
            after=after,
        )
    )


def _refuse_cycle(
    session: Session, course_id: int, pair: tuple[int, int], skip: int | None
) -> None:
    cycle = cycle_if_added(_active_pairs(session, course_id, skip_edge_id=skip), pair)
    if cycle is not None:
        titles = {n.id: n.title for n in session.exec(select(ConceptNode))}
        raise Conflict(CycleError(cycle).named(titles))


def set_edge_status(session: Session, edge_id: int, status: EdgeStatus) -> GraphOut:
    edge = _edge(session, edge_id)
    course = _editable(session, edge.course_id)
    if status != EdgeStatus.REJECTED and edge.status == EdgeStatus.REJECTED.value:
        # Bringing a rejected edge back is an addition, so it must not close a cycle.
        _refuse_cycle(session, course.id, (edge.src_node, edge.dst_node), skip=edge.id)
    before = _snapshot(edge)
    edge.status = status.value
    session.add(edge)
    _log(session, course, EditOp.REVIEW_EDGE, edge.id, before, _snapshot(edge))
    session.commit()
    return get_graph(session, course.id)


def retype_edge(session: Session, edge_id: int, edge_type: EdgeType) -> GraphOut:
    edge = _edge(session, edge_id)
    course = _editable(session, edge.course_id)
    before = _snapshot(edge)
    edge.type = edge_type.value
    session.add(edge)
    _log(session, course, EditOp.RETYPE_EDGE, edge.id, before, _snapshot(edge))
    session.commit()
    return get_graph(session, course.id)


def add_edge(
    session: Session, course_id: int | None, src_node: int, dst_node: int, edge_type: EdgeType
) -> GraphOut:
    course = _editable(session, _course(session, course_id).id)
    if src_node == dst_node:
        raise Conflict("A concept cannot be a prerequisite of itself.")
    for node_id in (src_node, dst_node):
        node = session.get(ConceptNode, node_id)
        if node is None or node.course_id != course.id:
            raise NotFound(f"Node {node_id} is not in this course")

    existing = session.exec(
        select(Edge).where(
            Edge.course_id == course.id, Edge.src_node == src_node, Edge.dst_node == dst_node
        )
    ).first()
    if existing is not None and existing.status != EdgeStatus.REJECTED.value:
        raise Conflict("That edge already exists.")
    _refuse_cycle(session, course.id, (src_node, dst_node), skip=existing.id if existing else None)

    if existing is None:
        edge = Edge(course_id=course.id, src_node=src_node, dst_node=dst_node)
        before = None
    else:  # the professor is overriding an earlier rejection
        edge, before = existing, _snapshot(existing)
    edge.type = edge_type.value
    edge.source = EdgeSource.MANUAL.value  # from now on no pipeline run may touch it
    edge.status = EdgeStatus.ACCEPTED.value
    edge.graph_version = course.graph_version
    session.add(edge)
    session.flush()
    _log(session, course, EditOp.ADD_EDGE, edge.id, before, _snapshot(edge))
    session.commit()
    return get_graph(session, course.id)


def delete_edge(session: Session, edge_id: int) -> GraphOut:
    """Delete an edge. A manual edge is removed. A pipeline edge is marked rejected instead of
    removed, so that rebuilding the graph does not propose it again."""
    edge = _edge(session, edge_id)
    course = _editable(session, edge.course_id)
    before = _snapshot(edge)
    if edge.source == EdgeSource.MANUAL.value:
        session.delete(edge)
        after = None
    else:
        edge.status = EdgeStatus.REJECTED.value
        session.add(edge)
        after = _snapshot(edge)
    _log(session, course, EditOp.DELETE_EDGE, edge_id, before, after)
    session.commit()
    return get_graph(session, course.id)


def approve(session: Session, course_id: int | None, accept_remaining: bool) -> GraphOut:
    course = _editable(session, _course(session, course_id).id)
    proposed = [
        e
        for e in session.exec(select(Edge).where(Edge.course_id == course.id))
        if e.status == EdgeStatus.PROPOSED.value
    ]
    if proposed and not accept_remaining:
        raise Conflict(
            f"{len(proposed)} edges are still unreviewed. Review them, or approve with "
            "accept_remaining to accept them all."
        )
    for edge in proposed:
        before = _snapshot(edge)
        edge.status = EdgeStatus.ACCEPTED.value
        session.add(edge)
        _log(session, course, EditOp.REVIEW_EDGE, edge.id, before, _snapshot(edge))
    course.graph_status = GraphStatus.APPROVED.value
    session.add(course)
    _log(
        session,
        course,
        EditOp.APPROVE,
        None,
        {"graph_status": GraphStatus.DRAFT.value},
        {"graph_status": GraphStatus.APPROVED.value, "accepted_remaining": len(proposed)},
    )
    session.commit()
    return get_graph(session, course.id)
