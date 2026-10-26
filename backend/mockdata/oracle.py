"""A mock edge classifier that answers from the known structure of the sample curriculum.

It implements the same interface as a real provider, so the real classification runner, cache and
ledger run against it unchanged. Pipeline "B" disagrees with the truth on a fixed share of pairs,
so the review screen has disagreements to show.
"""

import hashlib
import re

from backend.llm.base import Completion, Cost, EdgeClassification, LLMRequest, T
from backend.mockdata.physics import truth

_FROM = re.compile(r"^FROM: (\S+)", re.MULTILINE)
_TO = re.compile(r"^TO: (\S+)", re.MULTILINE)

_JUSTIFICATION = {
    "required": "{to} builds directly on the ideas and methods introduced in {src}.",
    "optional": "{src} gives useful background for {to}, but {to} can be followed without it.",
    "none": "The references between {src} and {to} are incidental; there is no real dependency.",
}
# What the disagreeing pipeline says instead.
_FLIP = {"required": "optional", "optional": "required", "none": "optional"}


class MockEdgeOracle:
    def __init__(self, pipeline: str, disagree_share: int = 5) -> None:
        """`disagree_share` of 5 means Pipeline B contradicts the truth on about 1 pair in 5."""
        self.pipeline = pipeline
        self.provider = f"mock-{pipeline.lower()}"
        self.model = "oracle-v1"
        self.disagree_share = disagree_share
        self.calls = 0

    def complete(self, request: LLMRequest, schema: type[T]) -> Completion[T]:
        if schema is not EdgeClassification:
            raise TypeError("MockEdgeOracle only produces EdgeClassification")
        source = _FROM.search(request.user)
        target = _TO.search(request.user)
        if not source or not target:
            raise ValueError("MockEdgeOracle needs a prompt with FROM: and TO: lines")
        src, dst = source.group(1), target.group(1)
        self.calls += 1

        verdict = truth(src, dst)
        digest = int(hashlib.sha256(f"{src}>{dst}".encode()).hexdigest(), 16)
        confident = 0.8 + (digest % 15) / 100  # 0.80 to 0.94
        if self.pipeline == "B":
            confident = 0.55 + (digest % 20) / 100  # a less certain pipeline
            if digest % self.disagree_share == 0:
                verdict = _FLIP[verdict]
        result = EdgeClassification(
            type=verdict,
            justification=_JUSTIFICATION[verdict].format(src=src, to=dst),
            confidence=round(confident, 2),
        )
        cost = Cost(tokens_in=len(request.user) // 4, tokens_out=40, usd=0.0)
        return Completion(result=result, cost=cost, provider=self.provider, model=self.model)
