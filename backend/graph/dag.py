"""Pure graph helpers: cycle detection, safe edge addition and transitive reduction.

No database and no I/O. Nodes can be any hashable value. An edge `(u, v)` means u is a
prerequisite of v. Duplicate edges are ignored. A self-loop counts as a cycle.
"""

from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass

Edge = tuple[Hashable, Hashable]


class CycleError(ValueError):
    """Raised when an edge would create, or the graph already contains, a cycle."""

    def __init__(self, cycle: Sequence[Hashable]) -> None:
        self.cycle = list(cycle)  # first node repeated at the end: [a, b, c, a]
        super().__init__("Cycle: " + " -> ".join(str(node) for node in self.cycle))

    def named(self, names: dict[Hashable, str]) -> str:
        """The same message with display names (for example section titles) instead of ids."""
        return "Cycle: " + " -> ".join(names.get(node, str(node)) for node in self.cycle)


def _adjacency(edges: Iterable[Edge]) -> dict[Hashable, list[Hashable]]:
    adjacency: dict[Hashable, list[Hashable]] = {}
    for src, dst in edges:
        adjacency.setdefault(src, [])
        adjacency.setdefault(dst, [])
        if dst not in adjacency[src]:
            adjacency[src].append(dst)
    return adjacency


def find_cycle(edges: Iterable[Edge]) -> list[Hashable] | None:
    """Return one cycle as [a, b, ..., a], or None if the graph is acyclic."""
    adjacency = _adjacency(edges)
    state: dict[Hashable, int] = {}  # absent: unvisited, 1: on the current path, 2: finished
    for root in adjacency:
        if root in state:
            continue
        path = [root]
        iterators = [iter(adjacency[root])]
        state[root] = 1
        while iterators:
            for child in iterators[-1]:
                if state.get(child) == 1:
                    return path[path.index(child) :] + [child]
                if child not in state:
                    state[child] = 1
                    path.append(child)
                    iterators.append(iter(adjacency[child]))
                    break
            else:
                state[path.pop()] = 2
                iterators.pop()
    return None


def reachable_from(edges: Iterable[Edge], start: Hashable) -> set[Hashable]:
    """Every node that can be reached from `start` by following edges (excluding `start`)."""
    adjacency = _adjacency(edges)
    seen: set[Hashable] = set()
    stack = list(adjacency.get(start, []))
    while stack:
        node = stack.pop()
        if node not in seen:
            seen.add(node)
            stack.extend(adjacency.get(node, []))
    return seen


def cycle_if_added(edges: Iterable[Edge], new_edge: Edge) -> list[Hashable] | None:
    """The cycle that adding `new_edge` would create, or None if it is safe.

    Adding u -> v closes a cycle exactly when v already reaches u.
    """
    src, dst = new_edge
    if src == dst:
        return [src, src]
    edges = list(edges)
    adjacency = _adjacency(edges)
    # Breadth-first from dst, remembering how each node was reached, to recover the path.
    parent: dict[Hashable, Hashable | None] = {dst: None}
    queue = [dst]
    for node in queue:
        if node == src:
            path = [src]
            while parent[path[-1]] is not None:
                path.append(parent[path[-1]])
            path.reverse()  # dst ... src
            return [src] + path  # src -> dst ... -> src
        for child in adjacency.get(node, []):
            if child not in parent:
                parent[child] = node
                queue.append(child)
    return None


def add_edge(edges: Iterable[Edge], new_edge: Edge) -> list[Edge]:
    """Return the edges plus `new_edge`, or raise CycleError naming the cycle it would create."""
    edges = list(edges)
    cycle = cycle_if_added(edges, new_edge)
    if cycle is not None:
        raise CycleError(cycle)
    return edges if new_edge in edges else [*edges, new_edge]


@dataclass(frozen=True)
class Reduction:
    kept: list[Edge]  # the transitive reduction
    hidden: list[Edge]  # edges implied by a longer path, in their original order


def transitive_reduction(edges: Iterable[Edge]) -> Reduction:
    """Split a DAG's edges into those that matter and those implied by a longer path.

    An edge u -> v is hidden when some other successor w of u (w != v) can reach v. Raises
    CycleError if the graph has a cycle, because the reduction is only defined for a DAG.
    """
    unique: list[Edge] = list(dict.fromkeys(edges))
    cycle = find_cycle(unique)
    if cycle is not None:
        raise CycleError(cycle)

    adjacency = _adjacency(unique)
    reach: dict[Hashable, set[Hashable]] = {}

    def reach_of(node: Hashable) -> set[Hashable]:
        if node not in reach:
            found: set[Hashable] = set()
            for child in adjacency[node]:
                found.add(child)
                found |= reach_of(child)
            reach[node] = found
        return reach[node]

    kept: list[Edge] = []
    hidden: list[Edge] = []
    for src, dst in unique:
        implied = any(dst in reach_of(other) for other in adjacency[src] if other != dst)
        (hidden if implied else kept).append((src, dst))
    return Reduction(kept=kept, hidden=hidden)
