"""Helpers for ranking what the professor should look at first. Pure functions."""

from collections.abc import Mapping
from typing import Any


def pipelines_disagree(classifications: Mapping[str, Mapping[str, Any]]) -> bool:
    """True when two or more pipelines classified the edge and did not all say the same type."""
    types = {entry["type"] for entry in classifications.values()}
    return len(classifications) >= 2 and len(types) > 1


def review_rank(
    classifications: Mapping[str, Mapping[str, Any]], weight: int
) -> tuple[int, float, int]:
    """Sort key, smallest first: disagreements, then the least confident, then the most-referenced.

    An edge no pipeline has classified sorts as least confident (0.0), so it surfaces early.
    """
    confidences = [entry["confidence"] for entry in classifications.values()]
    lowest = min(confidences) if confidences else 0.0
    return (0 if pipelines_disagree(classifications) else 1, lowest, -weight)
