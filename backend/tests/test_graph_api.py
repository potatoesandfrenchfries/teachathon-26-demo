"""The graph read and review API, run against the mock sample graph."""

import pytest
from sqlmodel import select

from backend.graph.build import build_candidate_graph
from backend.graph.classify import classify_edges
from backend.llm.cache import CachedLLM
from backend.llm.fake import FakeProvider
from backend.mockdata.load import seed_mock
from backend.models import Edge, GraphEdit

KEY = {"X-Admin-Key": "test-key"}


@pytest.fixture
def summary(session):
    return seed_mock(session)


@pytest.fixture
def graph(client, summary):
    return client.get("/graph").json()


def _edge(graph: dict, src: str, dst: str) -> dict:
    """The edge between two section numbers, for example ("2.2", "2.4")."""
    node_id = {n["section_number"]: n["id"] for n in graph["nodes"]}
    pair = (node_id[src], node_id[dst])
    return next(e for e in graph["edges"] if (e["src_node"], e["dst_node"]) == pair)


def _node(graph: dict, number: str) -> int:
    return next(n["id"] for n in graph["nodes"] if n["section_number"] == number)


# --- Reading (W1-27) --------------------------------------------------------------------------


def test_courses_lists_the_sample_course(client, summary):
    (course,) = client.get("/courses").json()
    assert course["name"] == "Mock Physics (sample data)"
    assert course["graph_status"] == "draft"


def test_the_graph_has_nodes_edges_status_and_the_draft_flag(client, graph):
    assert graph["course"]["graph_status"] == "draft"  # nothing gates before approval
    assert len(graph["nodes"]) == 16
    assert len(graph["edges"]) == 29
    node = graph["nodes"][0]
    assert set(node) >= {"id", "title", "section_number", "world_group", "question_count"}
    assert all(n["question_count"] > 0 for n in graph["nodes"])
    assert {n["world_group"] for n in graph["nodes"]} == {
        "Foundations",
        "Kinematics",
        "Dynamics",
        "Energy",
        "Momentum",
    }


def test_every_edge_carries_its_evidence(client, graph):
    for edge in graph["edges"]:
        evidence = edge["evidence"]
        assert evidence["total"] == edge["weight"] > 0
        assert sum(r["count"] for r in evidence["crossrefs"]) == evidence["total"]
        assert set(edge["classifications"]) == {"A", "B"}
        assert edge["justification"]
        assert edge["status"] == "proposed"

    ref = _edge(graph, "3.1", "3.2")["evidence"]["crossrefs"][0]
    assert {ref["referring_section"], ref["referred_section"]} == {"3.1", "3.2"}
    assert ref["referring"] and ref["referred"]


def test_each_pipelines_verdict_is_exposed_and_disagreements_are_flagged(client, graph):
    flagged = [e for e in graph["edges"] if e["disagreement"]]
    assert flagged
    for edge in flagged:
        types = {c["type"] for c in edge["classifications"].values()}
        assert len(types) > 1
    entry = _edge(graph, "2.1", "2.2")["classifications"]["A"]
    assert set(entry) == {
        "type",
        "justification",
        "confidence",
        "provider",
        "model",
        "prompt_version",
    }


def test_the_review_queue_puts_disagreements_first(client, graph):
    by_id = {e["id"]: e for e in graph["edges"]}
    queue = graph["review_queue"]
    assert sorted(queue) == sorted(by_id)  # every edge is unreviewed
    flags = [by_id[i]["disagreement"] for i in queue]
    assert flags == sorted(flags, reverse=True)  # all True first, then all False
    assert any(flags)


def test_implied_edges_are_marked_hidden(client, graph):
    assert _edge(graph, "2.2", "2.4")["hidden"]  # implied by 2.2 -> 2.3 -> 2.4
    assert _edge(graph, "3.1", "3.3")["hidden"]  # implied by 3.1 -> 3.2 -> 3.3
    assert not _edge(graph, "2.1", "2.2")["hidden"]
    assert not _edge(graph, "2.2", "2.3")["hidden"]


def test_unknown_course_is_a_404_and_an_empty_database_says_so(client, engine):
    assert client.get("/graph", params={"course_id": 99}).status_code == 404
    assert client.get("/graph").status_code == 404  # no course seeded in this database


# --- Admin key (W1-28) ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/admin/graph/edges/1/accept", None),
        ("post", "/admin/graph/edges/1/reject", None),
        ("patch", "/admin/graph/edges/1", {"type": "optional"}),
        ("delete", "/admin/graph/edges/1", None),
        ("post", "/admin/graph/edges", {"src_node": 1, "dst_node": 2}),
        ("post", "/admin/graph/approve", {}),
        ("get", "/admin/graph/edits", None),
    ],
)
def test_every_admin_route_needs_the_key(client, summary, method, path, body):
    send = getattr(client, method)
    kwargs = {"json": body} if body is not None else {}
    assert send(path, **kwargs).status_code == 401
    assert send(path, headers={"X-Admin-Key": "wrong"}, **kwargs).status_code == 401
    assert send(path, headers=KEY, **kwargs).status_code != 401


# --- Accept, reject, retype (W1-28) ---------------------------------------------------------------


def test_accept_reject_and_retype_update_the_edge_and_return_the_graph(client, graph):
    first = _edge(graph, "2.1", "2.2")["id"]
    second = _edge(graph, "2.2", "2.3")["id"]

    accepted = client.post(f"/admin/graph/edges/{first}/accept", headers=KEY).json()
    assert next(e for e in accepted["edges"] if e["id"] == first)["status"] == "accepted"
    assert first not in accepted["review_queue"]

    rejected = client.post(f"/admin/graph/edges/{second}/reject", headers=KEY).json()
    assert next(e for e in rejected["edges"] if e["id"] == second)["status"] == "rejected"

    retyped = client.patch(
        f"/admin/graph/edges/{first}", json={"type": "optional"}, headers=KEY
    ).json()
    assert next(e for e in retyped["edges"] if e["id"] == first)["type"] == "optional"


def test_a_retype_must_be_required_or_optional(client, graph):
    edge_id = graph["edges"][0]["id"]
    response = client.patch(f"/admin/graph/edges/{edge_id}", json={"type": "none"}, headers=KEY)
    assert response.status_code == 422


def test_an_unknown_edge_is_a_404(client, summary):
    assert client.post("/admin/graph/edges/9999/accept", headers=KEY).status_code == 404


def test_reviews_are_written_to_the_audit_log_with_before_and_after(client, graph):
    edge_id = _edge(graph, "2.1", "2.2")["id"]
    client.post(f"/admin/graph/edges/{edge_id}/accept", headers=KEY)

    (edit,) = client.get("/admin/graph/edits", headers=KEY).json()
    assert (edit["op"], edit["actor"], edit["target_id"]) == ("review_edge", "admin", edge_id)
    assert edit["before"]["status"] == "proposed"
    assert edit["after"]["status"] == "accepted"


# --- Add and delete with the cycle check (W1-29) --------------------------------------------------


def test_adding_an_edge_by_hand_makes_a_manual_accepted_edge_and_logs_it(client, graph):
    src, dst = _node(graph, "1.1"), _node(graph, "5.1")
    result = client.post(
        "/admin/graph/edges",
        json={"src_node": src, "dst_node": dst, "type": "optional"},
        headers=KEY,
    )

    assert result.status_code == 200
    edge = _edge(result.json(), "1.1", "5.1")
    assert (edge["source"], edge["status"], edge["type"]) == ("manual", "accepted", "optional")
    ops = [e["op"] for e in client.get("/admin/graph/edits", headers=KEY).json()]
    assert ops == ["add_edge"]


def test_an_edit_that_creates_a_cycle_is_refused_with_a_message_naming_it(client, graph):
    # 1.1 leads to 5.2 through the chain, so 5.2 -> 1.1 would close a loop.
    src, dst = _node(graph, "5.2"), _node(graph, "1.1")
    response = client.post(
        "/admin/graph/edges", json={"src_node": src, "dst_node": dst}, headers=KEY
    )

    assert response.status_code == 409
    message = response.json()["detail"]
    assert message.startswith("Cycle: 5.2 Conservation of momentum and collisions -> 1.1 Units")
    assert message.endswith("5.2 Conservation of momentum and collisions")
    assert client.get("/graph").json()["edges"] == graph["edges"]  # nothing changed
    assert client.get("/admin/graph/edits", headers=KEY).json() == []  # and nothing was logged


@pytest.mark.parametrize(
    "case",
    ["self", "duplicate", "missing"],
)
def test_other_invalid_additions_are_refused(client, graph, case):
    existing = _edge(graph, "2.1", "2.2")
    body = {
        "self": {"src_node": existing["src_node"], "dst_node": existing["src_node"]},
        "duplicate": {"src_node": existing["src_node"], "dst_node": existing["dst_node"]},
        "missing": {"src_node": existing["src_node"], "dst_node": 99999},
    }[case]
    response = client.post("/admin/graph/edges", json=body, headers=KEY)
    assert response.status_code == (404 if case == "missing" else 409)


def test_deleting_a_manual_edge_removes_it_and_a_pipeline_edge_is_rejected_instead(
    client, graph, session
):
    manual = client.post(
        "/admin/graph/edges",
        json={"src_node": _node(graph, "1.1"), "dst_node": _node(graph, "5.1")},
        headers=KEY,
    ).json()
    manual_id = _edge(manual, "1.1", "5.1")["id"]
    after = client.delete(f"/admin/graph/edges/{manual_id}", headers=KEY).json()
    assert all(e["id"] != manual_id for e in after["edges"])  # gone

    pipeline_id = _edge(graph, "2.1", "2.2")["id"]
    after = client.delete(f"/admin/graph/edges/{pipeline_id}", headers=KEY).json()
    assert next(e for e in after["edges"] if e["id"] == pipeline_id)["status"] == "rejected"

    ops = [e["op"] for e in client.get("/admin/graph/edits", headers=KEY).json()]
    assert ops == ["delete_edge", "delete_edge", "add_edge"]  # newest first


def test_a_deleted_pipeline_edge_is_not_proposed_again_when_the_graph_is_rebuilt(
    client, graph, session, summary
):
    edge_id = _edge(graph, "2.1", "2.2")["id"]
    client.delete(f"/admin/graph/edges/{edge_id}", headers=KEY)

    report = build_candidate_graph(session, summary.course_id, summary.book_id, min_weight=2)

    assert report.edges_created == 0
    assert session.get(Edge, edge_id).status == "rejected"


def test_a_rejected_edge_does_not_count_when_checking_for_cycles(client, graph):
    forward = _edge(graph, "5.1", "5.2")
    back = {"src_node": forward["dst_node"], "dst_node": forward["src_node"]}
    assert client.post("/admin/graph/edges", json=back, headers=KEY).status_code == 409

    client.post(f"/admin/graph/edges/{forward['id']}/reject", headers=KEY)
    assert client.post("/admin/graph/edges", json=back, headers=KEY).status_code == 200

    # Bringing the forward edge back would now close a loop, so it is refused too.
    response = client.post(f"/admin/graph/edges/{forward['id']}/accept", headers=KEY)
    assert response.status_code == 409 and response.json()["detail"].startswith("Cycle:")


def test_adding_over_a_rejected_edge_reactivates_it_as_manual(client, graph):
    edge = _edge(graph, "2.1", "2.2")
    client.delete(f"/admin/graph/edges/{edge['id']}", headers=KEY)
    result = client.post(
        "/admin/graph/edges",
        json={"src_node": edge["src_node"], "dst_node": edge["dst_node"], "type": "optional"},
        headers=KEY,
    ).json()

    revived = next(e for e in result["edges"] if e["id"] == edge["id"])
    assert (revived["source"], revived["status"], revived["type"]) == (
        "manual",
        "accepted",
        "optional",
    )


def test_a_pipeline_rerun_never_overwrites_a_manual_edge(client, graph, session, summary):
    edge = _edge(graph, "2.1", "2.2")
    client.delete(f"/admin/graph/edges/{edge['id']}", headers=KEY)
    client.post(
        "/admin/graph/edges",
        json={"src_node": edge["src_node"], "dst_node": edge["dst_node"], "type": "optional"},
        headers=KEY,
    )
    before = session.get(Edge, edge["id"])
    snapshot = (before.type, before.source, before.status, dict(before.classifications))

    classify_edges(session, summary.course_id, CachedLLM(FakeProvider(), session), "A")
    build_candidate_graph(session, summary.course_id, summary.book_id, min_weight=2)

    after = session.get(Edge, edge["id"])
    assert (after.type, after.source, after.status, dict(after.classifications)) == snapshot


# --- Approval (W1-30) -----------------------------------------------------------------------------


def test_approval_needs_every_edge_reviewed_or_an_explicit_accept_remaining(client, graph):
    response = client.post("/admin/graph/approve", json={}, headers=KEY)
    assert response.status_code == 409
    assert "29 edges are still unreviewed" in response.json()["detail"]
    assert client.get("/graph").json()["course"]["graph_status"] == "draft"


def test_approving_freezes_the_graph_and_flips_the_status(client, graph, session):
    result = client.post(
        "/admin/graph/approve", json={"accept_remaining": True}, headers=KEY
    ).json()

    assert result["course"]["graph_status"] == "approved"
    assert {e["status"] for e in result["edges"]} == {"accepted"}
    assert result["review_queue"] == []
    assert client.get("/graph").json()["course"]["graph_status"] == "approved"

    ops = [e["op"] for e in client.get("/admin/graph/edits", headers=KEY).json()]
    assert ops[0] == "approve" and ops.count("review_edge") == 29


def test_nothing_can_be_edited_after_approval(client, graph, session, summary):
    client.post("/admin/graph/approve", json={"accept_remaining": True}, headers=KEY)
    edge_id = graph["edges"][0]["id"]

    assert client.post(f"/admin/graph/edges/{edge_id}/reject", headers=KEY).status_code == 409
    assert (
        client.patch(
            f"/admin/graph/edges/{edge_id}", json={"type": "optional"}, headers=KEY
        ).status_code
        == 409
    )
    assert client.delete(f"/admin/graph/edges/{edge_id}", headers=KEY).status_code == 409
    body = {"src_node": _node(graph, "1.1"), "dst_node": _node(graph, "5.1")}
    assert client.post("/admin/graph/edges", json=body, headers=KEY).status_code == 409
    assert client.post("/admin/graph/approve", json={}, headers=KEY).status_code == 409
    assert session.exec(select(GraphEdit)).all()  # the approval itself is on record
