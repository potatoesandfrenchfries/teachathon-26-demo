"""The edge-classification prompt. Bump PROMPT_VERSION whenever the wording changes, so the cache
treats old answers as stale."""

from sqlmodel import Session, select

from backend.llm.base import LLMRequest
from backend.models import ConceptNode, CrossRef, Edge, NumberedResult

STAGE = "edge"
PROMPT_VERSION = "edge-v1"

SYSTEM = """\
You help a physics professor build a prerequisite graph from a textbook.

You are given two sections. A student studies FROM before TO. Decide how much TO depends on FROM:

- required: a student cannot follow TO without having learned FROM (it uses FROM's ideas, results \
or methods directly).
- optional: FROM is helpful background, but TO can be followed without it.
- none: there is no real dependency. Any cross-references between them are incidental.

Use the section titles, the numbered results and the cross-references as evidence. \
Cross-references are a hint, not proof: a reference can be incidental, and a dependency can exist \
without one.

Answer with JSON only: {"type": "required" | "optional" | "none", "justification": "<one or two \
sentences that cite the evidence>", "confidence": <number from 0 to 1>}.
"""


def _results(session: Session, section_id: int | None) -> list[NumberedResult]:
    if section_id is None:
        return []
    return list(
        session.exec(
            select(NumberedResult)
            .where(NumberedResult.section_id == section_id)
            .order_by(NumberedResult.id)
        )
    )


def _describe(session: Session, label: str, node: ConceptNode) -> tuple[str, list[NumberedResult]]:
    results = _results(session, node.section_id)
    listing = ", ".join(f"{r.label} ({r.kind})" for r in results) or "none recorded"
    return f"{label}: {node.title}\n  numbered results: {listing}\n", results


def edge_request(session: Session, edge: Edge) -> LLMRequest:
    """The classification request for one edge, built from the stored sections and references."""
    source = session.get(ConceptNode, edge.src_node)
    target = session.get(ConceptNode, edge.dst_node)
    from_text, from_results = _describe(session, "FROM", source)
    to_text, to_results = _describe(session, "TO", target)

    from_ids = {r.id: r for r in from_results}
    to_ids = {r.id: r for r in to_results}
    lines: list[str] = []
    total = 0
    if from_ids and to_ids:
        refs = session.exec(
            select(CrossRef).where(
                CrossRef.src_result_id.in_([*from_ids, *to_ids]),
                CrossRef.dst_result_id.in_([*from_ids, *to_ids]),
            )
        ).all()
        for ref in sorted(refs, key=lambda r: (r.src_result_id, r.dst_result_id)):
            one = from_ids.get(ref.src_result_id) or to_ids.get(ref.src_result_id)
            other = from_ids.get(ref.dst_result_id) or to_ids.get(ref.dst_result_id)
            same_side = (ref.src_result_id in from_ids) == (ref.dst_result_id in from_ids)
            if same_side:
                continue
            where = "FROM" if ref.src_result_id in from_ids else "TO"
            elsewhere = "TO" if where == "FROM" else "FROM"
            times = f"{ref.count} times" if ref.count != 1 else "once"
            lines.append(
                f"  - {one.label} in {where} refers to {other.label} in {elsewhere} ({times})"
            )
            total += ref.count

    header = f"Cross-references between the two sections (total {total}):\n"
    body = "\n".join(lines) if lines else "  none recorded"
    user = f"{from_text}{to_text}\n{header}{body}\n\nHow much does TO depend on FROM?"
    return LLMRequest(stage=STAGE, prompt_version=PROMPT_VERSION, system=SYSTEM, user=user)
