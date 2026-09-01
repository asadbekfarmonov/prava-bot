"""QA Slice 4 — adversarial gap coverage (docs/spec/07 readiness + 10 ranking + 03).

These extend the implementer's Slice 4 tests with cases they left uncovered:
- ranking mock bonus middle tier (19/20 -> +20)
- daily-consistency +5 credited once per active day
- Telegram username never exposed on the leaderboard
- readiness mistake_recovery neutral 1.0 when there are no mistakes
- answer speed does NOT affect readiness score but DOES gate ranking credit
- a wrong MOCK answer upserts a MistakeEntry
- mistakes queue is ordered hardest-first (miss_count desc)
"""

from __future__ import annotations

from dataclasses import replace

import app.domain.exam_config as ec
from app.domain.enums import PointsSource
from tests import slice4_helper as h
from tests.seed_helper import seed_demo_bank


# --------------------------------------------------------------------------- #
# RANKING gaps
# --------------------------------------------------------------------------- #
def test_mock_bonus_19_of_20_is_middle_tier(client):
    """19/20 is a pass and must award exactly the +20 middle-tier bonus."""
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    done = h.run_mock(c, num_correct=19)
    assert done["correct_count"] == 19
    assert done["passed"] is True
    assert h.ledger_points(1001, PointsSource.MOCK_CORRECT) == 19
    assert h.ledger_points(1001, PointsSource.MOCK_BONUS) == 20


def test_daily_consistency_awarded_once_per_active_day(client):
    """+5 once per active day; a second qualifying answer the same day re-credits nothing."""
    seed_demo_bank()
    c = h.make_user(client, 1001, "A", daily_goal=1)  # 1 answer => active day
    for tp in ["general_rules", "road_signs"]:
        sid = h.start_session(c, topic=tp, source="topic")
        h.answer(c, sid, h.next_q(c, topic=tp), correct=True)
    assert h.ledger_points(1001, PointsSource.DAILY_CONSISTENCY) == 5
    assert h.ledger_count(1001, PointsSource.DAILY_CONSISTENCY) == 1


def test_leaderboard_never_exposes_telegram_username(client):
    """The dev user's Telegram username ('dev_student') must never appear; only the
    ranking_name/display_name is shown, and there is no username field on rows."""
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")  # display_name 'A', tg username defaults to 'dev_student'
    sid = h.start_session(c, topic="general_rules", source="topic")
    h.answer(c, sid, h.next_q(c, topic="general_rules"), correct=True)
    board = c.get("/api/ranking", params={"range": "all"}).json()
    own = board["own"]
    assert own["name"] == "A"
    assert "username" not in own
    for e in board["entries"]:
        assert "username" not in e
        assert e["name"] != "dev_student"


# --------------------------------------------------------------------------- #
# READINESS gaps
# --------------------------------------------------------------------------- #
def test_mistake_recovery_neutral_one_when_no_mistakes(client):
    """total == 0 mistakes -> mistake_recovery component is the neutral 1.0 (not 0)."""
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    h.run_mock(c, num_correct=None)  # a perfect mock: zero mistakes ever created
    comps = c.get("/api/readiness").json()["components"]
    assert comps["mistake_recovery"]["total"] == 0
    assert comps["mistake_recovery"]["value"] == 1.0


def test_answer_speed_does_not_affect_readiness_but_gates_ranking(client, monkeypatch):
    """Two users with identical (all-correct) activity that differ ONLY in answer time
    must get the SAME readiness score; the too-fast user earns fewer ranking points."""
    seed_demo_bank()
    # Keep state at `initial` (needs a mock) so a numeric score is produced.
    monkeypatch.setattr(
        ec, "READINESS_CONFIG",
        replace(ec.READINESS_CONFIG, min_unique_questions_for_display=5),
    )

    # User FAST: perfect mock + 5x correct general_rules answered impossibly fast.
    fast = h.make_user(client, 1001, "FAST")
    h.run_mock(fast, num_correct=None)
    sid_f = h.start_session(fast, topic="general_rules", source="topic")
    qf = h.next_q(fast, topic="general_rules")
    for _ in range(5):
        h.answer(fast, sid_f, qf, correct=True, time_spent=0)  # < min_answer_seconds

    # User SLOW: identical activity but with a legitimate answer time.
    slow = h.make_user(client, 2002, "SLOW")
    h.run_mock(slow, num_correct=None)
    sid_s = h.start_session(slow, topic="general_rules", source="topic")
    qs = h.next_q(slow, topic="general_rules")
    for _ in range(5):
        h.answer(slow, sid_s, qs, correct=True, time_spent=90)

    score_fast = fast.get("/api/readiness").json()["score"]
    score_slow = slow.get("/api/readiness").json()["score"]
    assert score_fast is not None and score_slow is not None
    assert score_fast == score_slow  # answer speed does NOT change readiness

    # But speed DOES gate ranking: the too-fast unique-correct earned 0.
    assert h.ledger_points(1001, PointsSource.PRACTICE_UNIQUE) == 0
    assert h.ledger_points(2002, PointsSource.PRACTICE_UNIQUE) == 1


# --------------------------------------------------------------------------- #
# MISTAKES gaps
# --------------------------------------------------------------------------- #
def test_wrong_mock_answer_upserts_mistake_entries(client):
    """A wrong answer inside a MOCK (not just practice) must upsert MistakeEntry."""
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    h.run_mock(c, num_correct=18)  # 2 wrong of 20
    queue = c.get("/api/practice/mistakes").json()["mistakes"]
    assert len(queue) == 2


def test_mistakes_queue_ordered_hardest_first(client):
    """Queue is unresolved, ordered by miss_count desc (hardest first)."""
    seed_demo_bank()
    c = h.make_user(client, 1001, "A")
    # intersections missed twice; overtaking missed once.
    sid_i = h.start_session(c, topic="intersections", source="topic")
    qi = h.next_q(c, topic="intersections")
    h.answer(c, sid_i, qi, correct=False)
    h.answer(c, sid_i, qi, correct=False)
    sid_o = h.start_session(c, topic="overtaking", source="topic")
    qo = h.next_q(c, topic="overtaking")
    h.answer(c, sid_o, qo, correct=False)

    queue = c.get("/api/practice/mistakes").json()["mistakes"]
    assert len(queue) == 2
    assert queue[0]["question_id"] == qi["question_id"]
    assert queue[0]["miss_count"] == 2
    assert queue[1]["question_id"] == qo["question_id"]
    assert queue[1]["miss_count"] == 1
