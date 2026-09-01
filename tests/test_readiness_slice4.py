"""Slice 4 — readiness scoring incl. curriculum-coverage gate (docs/spec/07)."""

from __future__ import annotations

from dataclasses import replace

import app.domain.exam_config as ec
from app.domain.enums import Topic
from tests import slice4_helper as h
from tests.seed_helper import seed_demo_bank

ALL_TOPICS = [t.value for t in Topic]


def test_insufficient_data_below_thresholds(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    # A couple of practice answers, no mock -> insufficient_data, no percentage.
    sid = h.start_session(c, topic="general_rules", source="topic")
    q = h.next_q(c, topic="general_rules")
    h.answer(c, sid, q, correct=True)

    r = c.get("/api/readiness")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "insufficient_data"
    assert body["label"] == "Ma'lumot yetarli emas"
    assert body["score"] is None
    assert body["exam_ready"] is False


def test_stays_initial_when_coverage_incomplete_even_with_high_accuracy(client, monkeypatch):
    """The 'only studied signs & parking' case: high accuracy but curriculum
    coverage incomplete must never reach ready_estimate or show an exam-ready badge."""
    seed_demo_bank()
    # Lower the count/mock gates so ONLY coverage keeps the state in `initial`.
    monkeypatch.setattr(ec, "READINESS_CONFIG", replace(
        ec.READINESS_CONFIG,
        min_unique_questions_for_display=5,
        min_unique_questions_for_full=15,
        min_mocks_for_full=1,
        gate_min_answers_per_topic=5,
        gate_last_n_mocks=1,
        gate_required_passes=1,
        gate_min_unique_questions=15,
    ))
    c = h.make_user(client, 1001, "A")

    # One perfect mock (covers all topics 1-2 each, none reaching 5) -> leaves
    # insufficient_data, and gives unique>=15.
    done = h.run_mock(c, num_correct=None)
    assert done["correct_count"] == 20

    # Heavily practise ONLY road signs + stopping/parking to >=5 answers each.
    for tp in ["road_signs", "stopping_parking"]:
        h.answer_specific_topic_correct(c, tp, times=6)

    body = c.get("/api/readiness").json()
    assert body["state"] == "initial"                 # NOT ready_estimate
    assert body["label"].startswith("Boshlang'ich daraja")
    assert body["exam_ready"] is False                # no badge without coverage
    assert body["coverage_met"] is False
    remaining = {t["topic"] for t in body["remaining_coverage"]}
    # Signs + parking are covered; the other topics remain.
    assert "road_signs" not in remaining
    assert "stopping_parking" not in remaining
    assert "intersections" in remaining


def test_ready_estimate_and_badge_only_when_all_gates_met(client, monkeypatch):
    seed_demo_bank()
    monkeypatch.setattr(ec, "READINESS_CONFIG", replace(
        ec.READINESS_CONFIG,
        min_unique_questions_for_display=5,
        min_unique_questions_for_full=15,
        min_mocks_for_full=3,
        gate_last_n_mocks=3,
        gate_required_passes=2,
        gate_min_unique_questions=15,
        gate_min_answers_per_topic=5,
    ))
    c = h.make_user(client, 1001, "A")

    # 3 perfect mocks -> mocks_completed=3, passes=3, unique=20.
    for _ in range(3):
        h.run_mock(c, num_correct=None)

    # Bring EVERY topic to >=5 correct answers (coverage + high mastery).
    for tp in ALL_TOPICS:
        h.answer_specific_topic_correct(c, tp, times=5)

    body = c.get("/api/readiness").json()
    assert body["coverage_met"] is True
    assert body["state"] == "ready_estimate"
    assert body["label"].startswith("Imtihonga tayyorlik")
    assert body["exam_ready"] is True
    assert body["score"] is not None and body["score"] >= 70


def test_readiness_components_and_weights_present(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    h.run_mock(c, num_correct=18)
    comps = c.get("/api/readiness").json()["components"]
    assert comps["mock_performance"]["weight"] == 0.40
    assert comps["topic_mastery"]["weight"] == 0.30
    assert comps["mistake_recovery"]["weight"] == 0.20
    assert comps["consistency_recency"]["weight"] == 0.10


def test_dashboard_returns_readiness_and_ranking(client):
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    sid = h.start_session(c, topic="general_rules", source="topic")
    h.answer(c, sid, h.next_q(c, topic="general_rules"), correct=True)
    body = c.get("/api/dashboard").json()
    assert "readiness" in body
    assert "weak_topics" in body
    assert "streak" in body
    assert "daily_goal" in body
    assert "ranking" in body and "week" in body["ranking"]
