"""Allowed values for string columns.

Columns store these as plain strings (portable to Postgres, no native enum types). Validation
happens in the API schemas, and the model fields default to the `.value` of a member.
"""

from enum import StrEnum


class LockMode(StrEnum):
    SOFT = "soft"
    HARD = "hard"


class GraphStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class BookRole(StrEnum):
    MAIN = "main"
    SUPPLEMENTARY = "supplementary"


class Visibility(StrEnum):
    INTERNAL_ONLY = "internal_only"
    OPEN = "open"


class NodeOrigin(StrEnum):
    SECTION = "section"
    MERGED = "merged"
    SPLIT = "split"
    MANUAL = "manual"


class EdgeType(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class EdgeSource(StrEnum):
    XREF = "xref"
    LLM = "llm"
    MANUAL = "manual"


class EdgeStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class EditOp(StrEnum):
    ADD_EDGE = "add_edge"
    DELETE_EDGE = "delete_edge"
    RETYPE_EDGE = "retype_edge"
    # Accept or reject a proposed edge. Not in PLAN.md section 4, added so reviews are audited too.
    REVIEW_EDGE = "review_edge"
    RENAME_NODE = "rename_node"
    MERGE_NODES = "merge_nodes"
    SPLIT_NODE = "split_node"
    ADD_NODE = "add_node"
    REOPEN = "reopen"
    # Freezing the graph. Not in PLAN.md section 4 either; added so approval is audited.
    APPROVE = "approve"


class QuestionType(StrEnum):
    MCQ = "mcq"
    NUMERIC = "numeric"
    SHORT = "short"
    PROOF = "proof"  # stored and shown, never graded or gated on


class ReviewStatus(StrEnum):
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class TagSource(StrEnum):
    LLM = "llm"
    MANUAL = "manual"
    MOCK = "mock"  # sample data only, never produced by a pipeline


class TagStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
