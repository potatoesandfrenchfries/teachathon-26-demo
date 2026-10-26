"""Graph commands. Run from the repo root:

    uv run --project backend python -m backend.graph build --course-id 1 --book-id 1
    uv run --project backend python -m backend.graph classify --course-id 1 --pipeline A --dry-run
    uv run --project backend python -m backend.graph classify --course-id 1 --pipeline A --yes
    uv run --project backend python -m backend.graph status --course-id 1

A real (paid) provider needs `--yes`. Run with `--dry-run` first and look at the estimate.
"""

import argparse
import sys

from sqlmodel import Session, select

from backend.db import default_engine
from backend.graph.build import GraphFrozenError, build_candidate_graph
from backend.graph.classify import classifiable_edges, classify_edges, requests_for
from backend.graph.review import pipelines_disagree
from backend.llm.base import EdgeClassification
from backend.llm.cache import CachedLLM, spent_usd
from backend.llm.estimate import estimate_cost
from backend.llm.factory import PIPELINE_PROVIDERS, PROVIDER_NAMES, make_provider
from backend.llm.openai_compat import ProviderError
from backend.llm.openrouter import fetch_model_pricing
from backend.llm.run import BudgetExceeded, RunManifest
from backend.models import ConceptNode, Edge
from backend.settings import get_settings

PAID_PROVIDERS = {"openrouter"}


def _build(args: argparse.Namespace, session: Session) -> int:
    settings = get_settings()
    min_weight = args.min_weight if args.min_weight is not None else settings.edge_min_weight
    report = build_candidate_graph(session, args.course_id, args.book_id, min_weight)
    print(
        f"nodes created {report.nodes_created}, edges created {report.edges_created}, "
        f"updated {report.edges_updated}, manual left alone {report.edges_skipped_manual}, "
        f"pairs below weight {min_weight}: {report.pairs_below_threshold}"
    )
    return 0


def _classify(args: argparse.Namespace, session: Session) -> int:
    settings = get_settings()
    provider_name = args.provider or PIPELINE_PROVIDERS[args.pipeline]
    edges = classifiable_edges(session, args.course_id)
    if args.limit is not None:
        edges = edges[: args.limit]
    if not edges:
        print("No edges to classify. Run `build` first.")
        return 1

    usd_in = usd_out = 0.0
    if provider_name == "openrouter":
        usd_in, usd_out = fetch_model_pricing(
            settings.openrouter_model, settings.openrouter_base_url
        )
    estimate = estimate_cost(requests_for(session, edges), EdgeClassification, usd_in, usd_out)
    model = settings.openrouter_model if provider_name == "openrouter" else provider_name
    print(
        f"{len(edges)} edges via {provider_name} ({model}): "
        f"about {estimate.tokens_in} tokens in, {estimate.tokens_out} out, "
        f"estimated ${estimate.usd:.4f} "
        f"(a rough estimate; the cap is ${settings.llm_budget_usd:.2f})"
    )
    if args.dry_run:
        return 0
    if provider_name in PAID_PROVIDERS and not args.yes:
        print("This would spend money. Re-run with --yes once you are happy with the estimate.")
        return 2

    run_id = args.run_id or f"edges-{args.pipeline}-{args.course_id}"
    manifest = RunManifest.open(settings.runs_dir, run_id)
    llm = CachedLLM(
        make_provider(provider_name, settings, (usd_in, usd_out)),
        session,
        run_id=run_id,
        budget_usd=settings.llm_budget_usd,
    )
    try:
        report = classify_edges(
            session,
            args.course_id,
            llm,
            args.pipeline,
            manifest=manifest,
            limit=args.limit,
            on_progress=lambda done, total: print(f"\r{done}/{total}", end="", flush=True),
        )
    except BudgetExceeded as error:
        print(f"\nStopped: {error}. Raise TA_LLM_BUDGET_USD and re-run to resume.")
        return 3
    print(
        f"\nclassified {report.classified}, already done {report.already_done}, "
        f"manual skipped {report.skipped_manual}; "
        f"provider calls {llm.misses}, cache hits {llm.hits}; "
        f"spent ${spent_usd(session, run_id):.4f} in run {run_id}"
    )
    return 0


def _status(args: argparse.Namespace, session: Session) -> int:
    nodes = session.exec(select(ConceptNode).where(ConceptNode.course_id == args.course_id)).all()
    edges = session.exec(select(Edge).where(Edge.course_id == args.course_id)).all()
    by_pipeline: dict[str, int] = {}
    for edge in edges:
        for pipeline in edge.classifications:
            by_pipeline[pipeline] = by_pipeline.get(pipeline, 0) + 1
    disagreements = sum(1 for edge in edges if pipelines_disagree(edge.classifications))
    print(f"nodes {len(nodes)}, edges {len(edges)}, classified by pipeline {by_pipeline}")
    print(f"pipeline disagreements {disagreements}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.graph", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="create nodes and proposed edges from ingested rows")
    build.add_argument("--course-id", type=int, required=True)
    build.add_argument("--book-id", type=int, required=True)
    build.add_argument("--min-weight", type=int, default=None)
    build.set_defaults(run=_build)

    classify = commands.add_parser("classify", help="classify proposed edges with one pipeline")
    classify.add_argument("--course-id", type=int, required=True)
    classify.add_argument("--pipeline", choices=sorted(PIPELINE_PROVIDERS), required=True)
    classify.add_argument("--provider", choices=PROVIDER_NAMES, default=None)
    classify.add_argument("--limit", type=int, default=None)
    classify.add_argument("--run-id", default=None)
    classify.add_argument("--dry-run", action="store_true", help="estimate cost, call nothing")
    classify.add_argument("--yes", action="store_true", help="allow a paid provider to be called")
    classify.set_defaults(run=_classify)

    status = commands.add_parser("status", help="counts of nodes, edges and classifications")
    status.add_argument("--course-id", type=int, required=True)
    status.set_defaults(run=_status)

    args = parser.parse_args(argv)
    with Session(default_engine()) as session:
        try:
            return args.run(args, session)
        except (ProviderError, GraphFrozenError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
