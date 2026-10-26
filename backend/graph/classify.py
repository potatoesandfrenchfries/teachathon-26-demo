"""Run one pipeline's classification over a course's proposed edges."""

from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session, select

from backend.graph.build import GraphFrozenError
from backend.graph.prompts import PROMPT_VERSION, edge_request
from backend.llm.base import EdgeClassification, LLMRequest, TextLLM
from backend.llm.run import RunManifest
from backend.models import Course, Edge
from backend.models.enums import EdgeSource, EdgeStatus, GraphStatus


@dataclass
class ClassifyReport:
    attempted: int = 0
    classified: int = 0  # edges handled in this call
    already_done: int = 0  # skipped: finished in this run, or already classified the same way
    skipped_manual: int = 0


def classifiable_edges(session: Session, course_id: int) -> list[Edge]:
    """Edges a pipeline may classify: everything except manual edges."""
    edges = session.exec(select(Edge).where(Edge.course_id == course_id).order_by(Edge.id)).all()
    return [edge for edge in edges if edge.source != EdgeSource.MANUAL.value]


def requests_for(session: Session, edges: list[Edge]) -> list[LLMRequest]:
    return [edge_request(session, edge) for edge in edges]


def classify_edges(
    session: Session,
    course_id: int,
    llm: TextLLM,
    pipeline: str,
    manifest: RunManifest | None = None,
    limit: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> ClassifyReport:
    """Classify edges with `llm` and store the verdict under `pipeline` (for example "A").

    Re-running is cheap: the LLM wrapper answers repeats from its cache, and `manifest` skips
    edges that already finished. Manual edges are never touched, and verdicts only move an edge's
    current type while the edge is still `proposed`.
    """
    course = session.get(Course, course_id)
    if course is None:
        raise ValueError(f"No course with id {course_id}")
    if course.graph_status == GraphStatus.APPROVED:
        raise GraphFrozenError("The graph is approved. Re-open it before re-classifying.")

    report = ClassifyReport()
    total_edges = session.exec(select(Edge).where(Edge.course_id == course_id)).all()
    report.skipped_manual = sum(1 for e in total_edges if e.source == EdgeSource.MANUAL.value)
    edges = classifiable_edges(session, course_id)
    if limit is not None:
        edges = edges[:limit]

    for index, edge in enumerate(edges, start=1):
        report.attempted += 1
        item_id = f"{pipeline}:edge-{edge.id}"
        if _already_classified(edge, pipeline, llm):
            report.already_done += 1
            if on_progress:
                on_progress(index, len(edges))
            continue

        def work(edge: Edge = edge) -> None:
            completion = llm.complete(edge_request(session, edge), EdgeClassification)
            _store(
                session, edge, pipeline, completion.result, completion.provider, completion.model
            )

        if manifest is None:
            work()
            report.classified += 1
        elif manifest.process(item_id, work):
            report.classified += 1
        else:
            report.already_done += 1
        if on_progress:
            on_progress(index, len(edges))
    return report


def _already_classified(edge: Edge, pipeline: str, llm: TextLLM) -> bool:
    """True when this pipeline already stored a verdict from the same provider, model and prompt.

    Switching the provider or bumping the prompt version makes the edge eligible again.
    """
    entry = edge.classifications.get(pipeline)
    return entry is not None and (
        entry.get("provider"),
        entry.get("model"),
        entry.get("prompt_version"),
    ) == (llm.provider, llm.model, PROMPT_VERSION)


def _store(
    session: Session,
    edge: Edge,
    pipeline: str,
    result: EdgeClassification,
    provider: str,
    model: str,
) -> None:
    entry = {
        "type": result.type,
        "justification": result.justification,
        "confidence": result.confidence,
        "provider": provider,
        "model": model,
        "prompt_version": PROMPT_VERSION,
    }
    # Assign a new dict: SQLAlchemy does not see in-place changes to a JSON column.
    edge.classifications = {**edge.classifications, pipeline: entry}

    if edge.status == EdgeStatus.PROPOSED.value:
        lead = edge.classifications.get("A", entry)  # Pipeline A leads when it has spoken
        if lead["type"] in ("required", "optional"):
            edge.type = lead["type"]
        edge.justification = lead["justification"]
    session.add(edge)
    session.commit()
