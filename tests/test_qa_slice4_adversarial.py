"""QA Slice 4 — additional adversarial gaps (docs/spec/07 + 10).

These target edge cases the implementer's + earlier QA suites left uncovered:
- min_answer_seconds is a strict boundary (== earns, < earns 0)
- zero completed mocks -> insufficient_data even when unique-questions gate is met
- a completed mock re-fetched / re-submitted never double-credits the ledger
- the daily practice cap bounds ONLY practice_unique (not mistake-recovery / mock)
- mistake-recovery credit primitive is idempotent per question (mock-resolution path)
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import app.domain.exam_config as ec
import app.services.mistakes as mistakes_service
import app.services.ranking as rk
from app.domain.enums import PointsSource
from app.domain.models import Question, User
from app.storage.db import session_scope
from tests import slice4_helper as h
from tests.seed_helper import seed_demo_bank


# --------------------------------------------------------------------------- #
# Anti-cheat: min_answer_seconds is a strict boundary
# --------------------------------------------------------------------------- #
def test_min_answer_seconds_is_strict_boundary(client):
    """time_spent == min_answer_seconds earns; time_spent == min-1 earns 0."""
    seed_demo_bank()
    min_s = ec.get_ranking_config().min_answer_seconds  # 2

    c = h.make_user(client, 1001, "A")
    # exactly-at-threshold answer is honest -> credited
    sid = h.start_session(c, topic="general_rules", source="topic")
    h.answer(c, sid, h.next_q(c, topic="general_rules"), correct=True, time_spent=min_s)
    assert h.ledger_points(1001, PointsSource.PRACTICE_UNIQUE) == 1

    # just-below-threshold answer is too fast -> 0
    c2 = h.make_user(client, 2002, "B")
    sid2 = h.start_session(c2, topic="general_rules", source="topic")
    h.answer(c2, sid2, h.next_q(c2, topic="general_rules"), correct=True, time_spent=min_s - 1)
    assert h.ledger_points(2002, PointsSource.PRACTICE_UNIQUE) == 0


# --------------------------------------------------------------------------- #
# Readiness: zero mocks forces insufficient_data regardless of unique count
# --------------------------------------------------------------------------- #
def test_zero_mocks_is_insufficient_data_even_when_unique_gate_met(client, monkeypatch):
    """State resolution requires >=1 completed mock. With the unique-question
    display gate lowered so it is satisfied by practice alone, zero mocks must
    still yield insufficient_data (no score)."""
    seed_demo_bank()
    monkeypatch.setattr(
        ec, "READINESS_CONFIG",
        replace(ec.READINESS_CONFIG, min_unique_questions_for_display=1),
    )
    c = h.make_user(client, 1001, "A")
    # Several distinct practice answers, but NO mock started/completed.
    for tp in ["general_rules", "road_signs", "signals", "intersections"]:
        sid = h.start_session(c, topic=tp, source="topic")
        h.answer(c, sid, h.next_q(c, topic=tp), correct=True)

    body = c.get("/api/readiness").json()
    assert body["mocks_completed"] == 0
    assert body["state"] == "insufficient_data"
    assert body["score"] is None
    assert "Imtihonga tayyorlik" not in body["label"]


# --------------------------------------------------------------------------- #
# Ledger idempotency across a re-fetched / re-submitted completed mock
# --------------------------------------------------------------------------- #
def test_completed_mock_refetch_and_resubmit_never_double_credits(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    done = h.run_mock(c, num_correct=None)  # 20/20 -> +20 base, +35 bonus
    attempt_id = done["id"]
    base = h.ledger_points(1001, PointsSource.MOCK_CORRECT)
    bonus = h.ledger_points(1001, PointsSource.MOCK_BONUS)
    assert base == 20 and bonus == 35

    # Re-fetch the completed attempt and try to submit it again.
    assert c.get(f"/api/mock/attempts/{attempt_id}").status_code == 200
    c.post(f"/api/mock/attempts/{attempt_id}/submit", json={})
    assert c.get(f"/api/mock/attempts/{attempt_id}").status_code == 200

    # Ledger is unchanged (finalize is a no-op post-completion + UNIQUE guard).
    assert h.ledger_points(1001, PointsSource.MOCK_CORRECT) == base
    assert h.ledger_points(1001, PointsSource.MOCK_BONUS) == bonus
    assert h.ledger_count(1001, PointsSource.MOCK_CORRECT) == 1
    assert h.ledger_count(1001, PointsSource.MOCK_BONUS) == 1


# --------------------------------------------------------------------------- #
# Daily practice cap bounds ONLY practice_unique, not recovery / mock
# --------------------------------------------------------------------------- #
def test_daily_cap_bounds_only_practice_unique_not_recovery(client, monkeypatch):
    seed_demo_bank()
    monkeypatch.setattr(ec, "RANKING_CONFIG", replace(ec.RANKING_CONFIG, daily_practice_cap=1))
    c = h.make_user(client, 1001, "A")

    # Miss a question first (creates a mistake; incorrect earns no points).
    sid_m = h.start_session(c, topic="intersections", source="topic")
    q_miss = h.next_q(c, topic="intersections")
    h.answer(c, sid_m, q_miss, correct=False)

    # Consume the entire practice cap with ONE unrelated unique-correct answer.
    sid_g = h.start_session(c, topic="general_rules", source="topic")
    h.answer(c, sid_g, h.next_q(c, topic="general_rules"), correct=True)
    assert h.ledger_points(1001, PointsSource.PRACTICE_UNIQUE) == 1

    # Another unique-correct answer is now BLOCKED by the cap.
    sid_s = h.start_session(c, topic="signals", source="topic")
    h.answer(c, sid_s, h.next_q(c, topic="signals"), correct=True)
    assert h.ledger_points(1001, PointsSource.PRACTICE_UNIQUE) == 1  # still capped

    # But RESOLVING the earlier mistake still awards +2 (recovery is not capped).
    h.answer(c, sid_m, q_miss, correct=True)
    assert h.ledger_points(1001, PointsSource.MISTAKE_RECOVERY) == 2
    # Practice-unique remains capped at 1 despite the resolving answer.
    assert h.ledger_points(1001, PointsSource.PRACTICE_UNIQUE) == 1


# --------------------------------------------------------------------------- #
# Mistake-recovery credit primitive is idempotent per question (mock path)
# --------------------------------------------------------------------------- #
def test_mock_path_mistake_recovery_credit_idempotent(client):
    """The mock finalize hook resolves mistakes via mistakes.record_answer and
    credits +2 via ranking.credit_mistake_recovery. Verify the exact primitives:
    a resolution transition is reported once, and the +2 credit is idempotent
    per question (so re-resolving via any path never re-awards)."""
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    # Create a mistake through practice.
    sid = h.start_session(c, topic="overtaking", source="topic")
    q = h.next_q(c, topic="overtaking")
    h.answer(c, sid, q, correct=False)
    qid = q["question_id"]

    uid = h.user_id_by_telegram(1001)
    with session_scope() as db:
        user = db.get(User, uid)
        # First correct re-answer -> resolves (as the mock hook would detect).
        res1 = mistakes_service.record_answer(db, user, qid, True)
        assert res1["resolved"] is True
        ok1 = rk.credit_mistake_recovery(db, user, qid)
        # A duplicate credit (e.g. a second graded path touching the same question).
        ok2 = rk.credit_mistake_recovery(db, user, qid)
        assert ok1 is True and ok2 is False

    assert h.ledger_points(1001, PointsSource.MISTAKE_RECOVERY) == 2
    assert h.ledger_count(1001, PointsSource.MISTAKE_RECOVERY) == 1
