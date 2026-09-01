"""Slice 4 — road-sign trainer (docs/spec/03)."""

from __future__ import annotations

from tests import slice4_helper as h
from tests.seed_helper import seed_demo_bank


def test_sign_trainer_serves_only_sign_questions_no_leak(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    sid = h.start_session(c, source="sign_trainer")
    assert sid  # session created

    # Serve several sign cards; every one must be a sign question with a no-leak payload.
    for _ in range(8):
        q = h.next_q(c, source="sign_trainer")
        assert q["is_sign_question"] is True
        assert q["prompt"]
        for opt in q["options"]:
            assert set(opt.keys()) == {"id", "position", "text"}
        assert "rule" not in q and "short_explanation" not in q


def test_sign_trainer_wrong_answer_feeds_mistakes(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    sid = h.start_session(c, source="sign_trainer")
    q = h.next_q(c, source="sign_trainer")
    res = h.answer(c, sid, q, correct=False)
    assert res["is_correct"] is False
    # The missed sign question now appears in the mistakes queue.
    queue = c.get("/api/practice/mistakes").json()["mistakes"]
    assert any(m["question_id"] == q["question_id"] for m in queue)


def test_sign_trainer_answer_reveals_explanation_and_rule(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    sid = h.start_session(c, source="sign_trainer")
    q = h.next_q(c, source="sign_trainer")
    res = h.answer(c, sid, q, correct=True)
    assert res["correct_option_id"] is not None
    assert all(o["explanation"] for o in res["options"])
    assert res["rule"] and res["rule"]["text"]
