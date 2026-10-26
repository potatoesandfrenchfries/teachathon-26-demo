"""Cycle detection, safe edge addition and transitive reduction.

The property tests compare against small independent oracles (Kahn's algorithm, a naive
transitive closure) so they do not just restate the implementation.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.graph.dag import (
    CycleError,
    add_edge,
    cycle_if_added,
    find_cycle,
    transitive_reduction,
)

# --- Examples -----------------------------------------------------------------------------


def test_find_cycle_returns_none_for_a_dag():
    assert find_cycle([("a", "b"), ("b", "c"), ("a", "c")]) is None
    assert find_cycle([]) is None


def test_find_cycle_names_the_cycle():
    cycle = find_cycle([("a", "b"), ("b", "c"), ("c", "a")])
    assert cycle is not None
    assert cycle[0] == cycle[-1]
    assert set(cycle) == {"a", "b", "c"}


def test_a_self_loop_is_a_cycle():
    assert find_cycle([("a", "a")]) == ["a", "a"]
    assert cycle_if_added([], ("a", "a")) == ["a", "a"]


def test_add_edge_refuses_a_cycle_with_a_message_naming_it():
    edges = [("a", "b"), ("b", "c")]
    with pytest.raises(CycleError) as raised:
        add_edge(edges, ("c", "a"))

    assert str(raised.value) == "Cycle: c -> a -> b -> c"
    assert raised.value.named({"a": "Vectors", "b": "Maps", "c": "Eigenvalues"}) == (
        "Cycle: Eigenvalues -> Vectors -> Maps -> Eigenvalues"
    )


def test_add_edge_accepts_a_safe_edge_and_ignores_a_duplicate():
    edges = [("a", "b")]
    assert add_edge(edges, ("b", "c")) == [("a", "b"), ("b", "c")]
    assert add_edge(edges, ("a", "b")) == [("a", "b")]


def test_reduction_hides_an_implied_edge():
    result = transitive_reduction([("a", "b"), ("b", "c"), ("a", "c")])
    assert result.kept == [("a", "b"), ("b", "c")]
    assert result.hidden == [("a", "c")]


def test_reduction_keeps_both_edges_of_a_diamond():
    diamond = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
    result = transitive_reduction(diamond)
    assert result.kept == diamond
    assert result.hidden == []


def test_reduction_ignores_duplicates_and_refuses_a_cycle():
    assert transitive_reduction([("a", "b"), ("a", "b")]).kept == [("a", "b")]
    with pytest.raises(CycleError):
        transitive_reduction([("a", "b"), ("b", "a")])


# --- Oracles --------------------------------------------------------------------------------


def _closure(edges) -> set[tuple[int, int]]:
    """All (u, v) pairs where v is reachable from u. Naive fixed-point iteration."""
    closure = set(edges)
    changed = True
    while changed:
        changed = False
        for u, v in list(closure):
            for x, y in list(closure):
                if v == x and (u, y) not in closure:
                    closure.add((u, y))
                    changed = True
    return closure


def _is_acyclic(edges) -> bool:
    """Kahn's algorithm."""
    nodes = {n for edge in edges for n in edge}
    indegree = {n: 0 for n in nodes}
    for _, v in set(edges):
        indegree[v] += 1
    ready = [n for n, degree in indegree.items() if degree == 0]
    removed = 0
    remaining = set(edges)
    while ready:
        node = ready.pop()
        removed += 1
        for edge in [e for e in remaining if e[0] == node]:
            remaining.discard(edge)
            indegree[edge[1]] -= 1
            if indegree[edge[1]] == 0:
                ready.append(edge[1])
    return removed == len(nodes)


# --- Strategies ---------------------------------------------------------------------------

NODES = st.integers(min_value=0, max_value=7)
ANY_GRAPH = st.lists(st.tuples(NODES, NODES), max_size=20)


@st.composite
def dags(draw):
    """A random DAG: edges only go forward in a random ordering of the nodes."""
    n = draw(st.integers(min_value=1, max_value=8))
    order = draw(st.permutations(range(n)))
    pairs = draw(
        st.lists(
            st.tuples(st.integers(0, n - 1), st.integers(0, n - 1)).filter(lambda p: p[0] < p[1]),
            max_size=20,
        )
    )
    return [(order[u], order[v]) for u, v in pairs]


# --- Properties ---------------------------------------------------------------------------


@given(ANY_GRAPH)
def test_find_cycle_agrees_with_kahn_and_returns_a_real_cycle(edges):
    cycle = find_cycle(edges)

    assert (cycle is None) == _is_acyclic(edges)
    if cycle is not None:
        assert cycle[0] == cycle[-1]
        assert all(pair in set(edges) for pair in zip(cycle, cycle[1:], strict=False))


@given(dags())
def test_reduction_partitions_the_edges_and_keeps_the_same_reachability(edges):
    result = transitive_reduction(edges)
    unique = list(dict.fromkeys(edges))

    assert sorted(result.kept + result.hidden) == sorted(unique)
    assert not set(result.kept) & set(result.hidden)
    assert _closure(result.kept) == _closure(unique)
    assert _is_acyclic(result.kept)


@given(dags())
def test_reduction_hides_only_implied_edges_and_keeps_only_needed_ones(edges):
    result = transitive_reduction(edges)

    for edge in result.hidden:
        # Implied: still reachable without it.
        assert edge in _closure(result.kept)
    for edge in result.kept:
        # Needed: removing it loses a reachable pair.
        others = [e for e in result.kept if e != edge]
        assert edge not in _closure(others)


@given(ANY_GRAPH)
def test_reduction_raises_exactly_when_there_is_a_cycle(edges):
    if _is_acyclic(edges):
        transitive_reduction(edges)
    else:
        with pytest.raises(CycleError) as raised:
            transitive_reduction(edges)
        assert raised.value.cycle[0] == raised.value.cycle[-1]


@given(dags(), NODES, NODES)
def test_cycle_if_added_agrees_with_checking_the_whole_graph(edges, src, dst):
    cycle = cycle_if_added(edges, (src, dst))

    assert (cycle is not None) == (find_cycle([*edges, (src, dst)]) is not None)
    if cycle is not None:
        assert cycle[0] == cycle[-1] == src
        allowed = {*edges, (src, dst)}
        assert all(pair in allowed for pair in zip(cycle, cycle[1:], strict=False))


@settings(max_examples=200)
@given(st.lists(st.tuples(NODES, NODES), max_size=30))
def test_any_sequence_of_edits_leaves_a_dag_or_is_refused(proposed):
    """Random edits: each is applied (still a DAG) or refused (and would really have cycled)."""
    graph: list[tuple[int, int]] = []
    for edge in proposed:
        try:
            graph = add_edge(graph, edge)
        except CycleError:
            assert find_cycle([*graph, edge]) is not None  # refusing was right
        assert _is_acyclic(graph)
