"""Slice 4 — learning-weighted ranking + anti-cheat (docs/spec/10)."""

from __future__ import annotations

from dataclasses import replace

import app.domain.exam_config as ec
from app.domain.enums import MockStatus, PointsSource
from app.domain.models import MockAttempt, User
from app.storage.db import session_scope
from tests import slice4_helper as h
from tests.seed_helper import seed_demo_bank


def test_unique_correct_credited_once_repeat_earns_zero(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    sid = h.start_session(c, topic="general_rules", source="topic")
    q = h.next_q(c, topic="general_rules")
    h.answer(c, sid, q, correct=True)
    h.answer(c, sid, q, correct=True)  # repeat correct earns nothing
    # answering it in a brand new session still earns nothing (unique per question).
    sid2 = h.start_session(c, topic="general_rules", source="topic")
    h.answer(c, sid2, q, correct=True)
    assert h.ledger_points(1001, PointsSource.PRACTICE_UNIQUE) == 1


def test_incorrect_earns_zero(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    sid = h.start_session(c, topic="signals", source="topic")
    q = h.next_q(c, topic="signals")
    h.answer(c, sid, q, correct=False)
    assert h.ledger_points(1001, PointsSource.PRACTICE_UNIQUE) == 0


def test_sub_min_answer_seconds_earns_zero(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    sid = h.start_session(c, topic="road_markings", source="topic")
    q = h.next_q(c, topic="road_markings")
    h.answer(c, sid, q, correct=True, time_spent=0)  # impossibly fast
    assert h.ledger_points(1001, PointsSource.PRACTICE_UNIQUE) == 0


def test_client_submitted_points_ignored(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    sid = h.start_session(c, topic="speed_distance", source="topic")
    q = h.next_q(c, topic="speed_distance")
    # Client tries to inject points / is_correct -> ignored (mass-assignment allowlist).
    h.answer(c, sid, q, correct=True, extra={"points": 9999, "is_correct": True})
    assert h.ledger_points(1001, PointsSource.PRACTICE_UNIQUE) == 1


def test_mistake_recovery_awarded_once(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    sid = h.start_session(c, topic="manoeuvring", source="topic")
    q = h.next_q(c, topic="manoeuvring")
    h.answer(c, sid, q, correct=False)  # create mistake
    h.answer(c, sid, q, correct=True)   # resolve -> +2
    assert h.ledger_points(1001, PointsSource.MISTAKE_RECOVERY) == 2
    # Re-miss then re-resolve -> no re-award (ledger UNIQUE).
    h.answer(c, sid, q, correct=False)
    h.answer(c, sid, q, correct=True)
    assert h.ledger_points(1001, PointsSource.MISTAKE_RECOVERY) == 2


def test_daily_practice_cap_enforced(client, monkeypatch):
    seed_demo_bank()
    monkeypatch.setattr(ec, "RANKING_CONFIG", replace(ec.RANKING_CONFIG, daily_practice_cap=2))
    c = h.make_user(client, 1001, "A")
    topics = ["general_rules", "road_signs", "signals", "intersections"]
    for tp in topics:
        sid = h.start_session(c, topic=tp, source="topic")
        q = h.next_q(c, topic=tp)
        h.answer(c, sid, q, correct=True)
    # 4 distinct unique-correct answers but cap = 2.
    assert h.ledger_points(1001, PointsSource.PRACTICE_UNIQUE) == 2


def test_mock_bonus_matches_server_correct_count(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    done = h.run_mock(c, num_correct=None)  # all 20 correct
    assert done["correct_count"] == 20
    assert h.ledger_points(1001, PointsSource.MOCK_CORRECT) == 20
    assert h.ledger_points(1001, PointsSource.MOCK_BONUS) == 35


def test_mock_bonus_scales_with_correct_count(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    done = h.run_mock(c, num_correct=18)  # 18/20 -> pass, bonus 10
    assert done["correct_count"] == 18
    assert h.ledger_points(1001, PointsSource.MOCK_CORRECT) == 18
    assert h.ledger_points(1001, PointsSource.MOCK_BONUS) == 10


def test_failed_mock_no_bonus(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    done = h.run_mock(c, num_correct=10)  # fail
    assert done["passed"] is False
    assert h.ledger_points(1001, PointsSource.MOCK_CORRECT) == 10
    assert h.ledger_points(1001, PointsSource.MOCK_BONUS) == 0


def test_abandoned_mock_earns_nothing(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    start = c.post("/api/mock/attempts", json={})
    attempt_id = start.json()["id"]
    # Mark it abandoned server-side without submitting.
    with session_scope() as db:
        att = db.get(MockAttempt, attempt_id)
        att.status = MockStatus.ABANDONED
    assert h.ledger_points(1001, PointsSource.MOCK_CORRECT) == 0
    assert h.ledger_points(1001, PointsSource.MOCK_BONUS) == 0


def test_max_mock_bonus_per_day_enforced(client, monkeypatch):
    seed_demo_bank()
    monkeypatch.setattr(ec, "RANKING_CONFIG", replace(ec.RANKING_CONFIG, max_mock_bonus_per_day=1))
    c = h.make_user(client, 1001, "A")
    h.run_mock(c, num_correct=None)  # bonus 35
    h.run_mock(c, num_correct=None)  # second bonus capped out
    assert h.ledger_count(1001, PointsSource.MOCK_BONUS) == 1


def test_concurrent_duplicate_credit_idempotent(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    uid = h.user_id_by_telegram(1001)
    from datetime import date

    import app.services.ranking as rk

    with session_scope() as db:
        user = db.get(User, uid)
        ok1 = rk._credit(db, uid, PointsSource.PRACTICE_UNIQUE, 1, "question", "q-x", date.today())
        ok2 = rk._credit(db, uid, PointsSource.PRACTICE_UNIQUE, 1, "question", "q-x", date.today())
    assert ok1 is True and ok2 is False
    assert h.ledger_count(1001, PointsSource.PRACTICE_UNIQUE) == 1


def test_own_position_shown_outside_top_list(client):
    seed_demo_bank()
    # A(3), B(2), C(1) points via unique-correct answers.
    a = h.make_user(client, 1001, "A")
    for tp in ["general_rules", "road_signs", "signals"]:
        sid = h.start_session(a, topic=tp, source="topic")
        h.answer(a, sid, h.next_q(a, topic=tp), correct=True)
    b = h.make_user(client, 2002, "B")
    for tp in ["general_rules", "road_signs"]:
        sid = h.start_session(b, topic=tp, source="topic")
        h.answer(b, sid, h.next_q(b, topic=tp), correct=True)
    c = h.make_user(client, 3003, "C")
    sid = h.start_session(c, topic="general_rules", source="topic")
    h.answer(c, sid, h.next_q(c, topic="general_rules"), correct=True)

    # limit=1 -> only top user visible, but C still sees own position (3).
    r = c.get("/api/ranking", params={"range": "all", "limit": 1})
    assert r.status_code == 200
    body = r.json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["name"] == "A"
    assert body["own"]["is_self"] is True
    assert body["own"]["position"] == 3
    assert body["own"]["points"] == 1


def test_opted_out_user_absent_from_board_but_sees_self(client):
    seed_demo_bank()
    a = h.make_user(client, 1001, "A")
    for tp in ["general_rules", "road_signs"]:
        sid = h.start_session(a, topic=tp, source="topic")
        h.answer(a, sid, h.next_q(a, topic=tp), correct=True)
    # Opted-out user with the most points.
    d = h.make_user(client, 4004, "D", show_on_ranking=False)
    for tp in ["general_rules", "road_signs", "signals", "intersections", "overtaking"]:
        sid = h.start_session(d, topic=tp, source="topic")
        h.answer(d, sid, h.next_q(d, topic=tp), correct=True)

    # A sees the public board WITHOUT D.
    board = a.get("/api/ranking", params={"range": "all", "limit": 50}).json()
    assert all(e["name"] != "D" for e in board["entries"])

    # D sees their own row even though absent from the public board.
    own_view = d.get("/api/ranking", params={"range": "all", "limit": 50}).json()
    # Public entries never expose internal user_id and never flag the opted-out
    # user as self; D still gets their own self-row below.
    assert all("user_id" not in e for e in own_view["entries"])
    assert all(e["is_self"] is False for e in own_view["entries"])
    assert own_view["own"]["points"] == 5
    assert own_view["own"]["position"] == 1


def test_ranking_uses_ranking_name(client):
    seed_demo_bank()
    a = h.make_user(client, 1001, "A", ranking_name="Chempion")
    sid = h.start_session(a, topic="general_rules", source="topic")
    h.answer(a, sid, h.next_q(a, topic="general_rules"), correct=True)
    board = a.get("/api/ranking", params={"range": "all"}).json()
    assert board["own"]["name"] == "Chempion"
