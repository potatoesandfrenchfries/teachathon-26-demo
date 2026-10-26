"""Candidate graph: one concept node per section, one proposed edge per well-linked section pair.

Works on whatever the ingestion stage stored (Section, NumberedResult, CrossRef), so it does not
care which book the rows came from. "Earlier" means a smaller Section id, which is document order.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from backend.models import ConceptNode, Course, CrossRef, Edge, NumberedResult, Section
from backend.models.enums import EdgeSource, EdgeStatus, EdgeType, GraphStatus, NodeOrigin


class GraphFrozenError(RuntimeError):
    """The course's graph is approved, so it can no longer be rebuilt or re-classified."""


@dataclass
class BuildReport:
    nodes_created: int = 0
    edges_created: int = 0
    edges_updated: int = 0
    edges_skipped_manual: int = 0
    pairs_below_threshold: int = 0


def default_world(section: Section) -> str:
    """Group sections by chapter: "2.3" belongs to "Chapter 2"."""
    return f"Chapter {section.number.split('.')[0]}"


def section_pair_weights(session: Session, book_id: int) -> dict[tuple[int, int], int]:
    """Cross-reference counts between pairs of sections, keyed (earlier id, later id).

    References in either direction count, and references inside one section are ignored.
    """
    referring = aliased(NumberedResult)
    referred = aliased(NumberedResult)
    rows = session.exec(
        select(referring.section_id, referred.section_id, CrossRef.count)
        .select_from(CrossRef)
        .join(referring, referring.id == CrossRef.src_result_id)
        .join(referred, referred.id == CrossRef.dst_result_id)
        .join(Section, Section.id == referring.section_id)
        .where(Section.book_id == book_id)
    ).all()
    weights: dict[tuple[int, int], int] = defaultdict(int)
    for one, other, count in rows:
        if one != other:
            weights[(min(one, other), max(one, other))] += count
    return dict(weights)


def build_candidate_graph(
    session: Session,
    course_id: int,
    book_id: int,
    min_weight: int,
    world_of: Callable[[Section], str] = default_world,
) -> BuildReport:
    """Create missing nodes and proposed edges. Safe to re-run.

    Existing edges only get their weight refreshed. Manual edges are never touched, and nothing is
    deleted. Edges start as unclassified "required" proposals until a pipeline classifies them.
    """
    course = session.get(Course, course_id)
    if course is None:
        raise ValueError(f"No course with id {course_id}")
    if course.graph_status == GraphStatus.APPROVED:
        raise GraphFrozenError("The graph is approved. Re-open it before rebuilding.")

    report = BuildReport()
    sections = session.exec(
        select(Section).where(Section.book_id == book_id).order_by(Section.id)
    ).all()
    node_of: dict[int, int] = {
        node.section_id: node.id
        for node in session.exec(select(ConceptNode).where(ConceptNode.course_id == course_id))
        if node.section_id is not None
    }
    for section in sections:
        if section.id in node_of:
            continue
        node = ConceptNode(
            course_id=course_id,
            section_id=section.id,
            title=f"{section.number} {section.title}",
            world_group=world_of(section),
            origin=NodeOrigin.SECTION.value,
        )
        session.add(node)
        session.flush()
        node_of[section.id] = node.id
        report.nodes_created += 1

    existing = {
        (edge.src_node, edge.dst_node): edge
        for edge in session.exec(select(Edge).where(Edge.course_id == course_id))
    }
    for (earlier, later), weight in sorted(section_pair_weights(session, book_id).items()):
        if weight < min_weight:
            report.pairs_below_threshold += 1
            continue
        pair = (node_of[earlier], node_of[later])
        edge = existing.get(pair)
        if edge is None:
            session.add(
                Edge(
                    course_id=course_id,
                    src_node=pair[0],
                    dst_node=pair[1],
                    type=EdgeType.REQUIRED.value,
                    weight=weight,
                    source=EdgeSource.XREF.value,
                    status=EdgeStatus.PROPOSED.value,
                    graph_version=course.graph_version,
                )
            )
            report.edges_created += 1
        elif edge.source == EdgeSource.MANUAL.value:
            report.edges_skipped_manual += 1
        elif edge.weight != weight:
            edge.weight = weight
            report.edges_updated += 1
    session.commit()
    return report
