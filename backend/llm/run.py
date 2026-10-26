"""A run manifest: which items of a long run have finished, so an interrupted run can resume."""

import json
import os
from collections.abc import Callable
from pathlib import Path


class BudgetExceeded(RuntimeError):
    """Raised before a provider call when the run has already spent its cap."""


class RunManifest:
    """Finished item ids for one run, saved to `<runs_dir>/<run_id>.json` after every item.

    Spend is not kept here. It is summed from the LLMCall ledger by `run_id`, so there is one
    source of truth. The same file is reopened on resume, and finished items are skipped.
    """

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.done: set[str] = set()

    @classmethod
    def open(cls, runs_dir: Path, run_id: str) -> "RunManifest":
        manifest = cls(runs_dir / f"{run_id}.json", run_id)
        if manifest.path.exists():
            manifest.done = set(json.loads(manifest.path.read_text())["done"])
        return manifest

    def is_done(self, item_id: str) -> bool:
        return item_id in self.done

    def mark_done(self, item_id: str) -> None:
        self.done.add(item_id)
        self._save()

    def process(self, item_id: str, work: Callable[[], object]) -> bool:
        """Run `work` unless the item already finished. Returns whether it ran."""
        if self.is_done(item_id):
            return False
        work()
        self.mark_done(item_id)
        return True

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"run_id": self.run_id, "done": sorted(self.done)}))
        os.replace(tmp, self.path)  # atomic, so a kill never leaves a half-written manifest
