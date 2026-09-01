"""Slice 4 — mistakes review (docs/spec/03 + 02)."""

from __future__ import annotations

from tests import slice4_helper as h
from tests.seed_helper import seed_demo_bank


def test_wrong_answer_upserts_mistake_and_queue(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    sid = h.start_session(c, topic="intersections", source="topic")
    q = h.next_q(c, topic="intersections")
    h.answer(c, sid, q, correct=False)

    r = c.get("/api/practice/mistakes")
    assert r.status_code == 200
    queue = r.json()["mistakes"]
    assert len(queue) == 1
    entry = queue[0]
    assert entry["question_id"] == q["question_id"]
    assert entry["miss_count"] == 1
    assert entry["prompt"]  # prompt resolved from current version

    # Missing again increments miss_count (upsert, not duplicate).
    h.answer(c, sid, q, correct=False)
    queue = c.get("/api/practice/mistakes").json()["mistakes"]
    assert len(queue) == 1
    assert queue[0]["miss_count"] == 2


def test_mistake_resolves_on_correct_via_mistakes_session(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    # Miss a question in practice.
    sid = h.start_session(c, topic="overtaking", source="topic")
    q = h.next_q(c, topic="overtaking")
    h.answer(c, sid, q, correct=False)
    assert len(c.get("/api/practice/mistakes").json()["mistakes"]) == 1

    # Start a mistakes-source session and serve the queued question (no-leak).
    msid = h.start_session(c, source="mistakes")
    served = h.next_q(c, source="mistakes")
    assert served["question_id"] == q["question_id"]
    for opt in served["options"]:
        assert set(opt.keys()) == {"id", "position", "text"}  # no correctness leak
    assert "rule" not in served and "short_explanation" not in served

    # Answer correctly -> resolves; queue empties.
    res = h.answer(c, msid, served, correct=True)
    assert res["is_correct"] is True
    assert c.get("/api/practice/mistakes").json()["mistakes"] == []


def test_mistakes_session_idor_returns_404(client):
    seed_demo_bank()
    a = h.make_user(client, 1001, "A")
    a_sid = h.start_session(a, source="mistakes")
    b = h.make_user(client, 2002, "B")
    r = b.get(f"/api/practice/sessions/{a_sid}")
    assert r.status_code == 404


def test_empty_mistakes_queue_next_returns_404(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    h.start_session(c, source="mistakes")
    r = c.get("/api/practice/questions/next", params={"source": "mistakes"})
    assert r.status_code == 404
