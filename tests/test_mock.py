"""Slice 2 — mock exam tests (docs/spec/03, 05, 09, 12).

Covers: version-pinned 20-question selection (unique, without replacement),
no-regeneration on reopen, single in-progress attempt, no-answer-leak payloads,
server-side grading + 18/20 boundary, IDOR, injected question_version_id rejection,
server-authoritative timer with lazy finalize, review-only-after-completion,
late-answer-after-expiry ignored, and idempotent duplicate submit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.domain.enums import Category, Topic
from app.domain.models import AnswerOption, MockAttempt, MockQuestion
from app.services.content_source import OptionDraft, QuestionDraft, SourceRefDraft
from app.services.ingestion import publish_question
from app.storage.db import get_session_factory
from tests.seed_helper import seed_demo_bank


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _login(client, telegram_id=1001, name="Dilnoza"):
    r = client.post("/api/dev/login", json={"telegram_id": telegram_id, "first_name": name})
    assert r.status_code == 200


def _onboard(client, name="Dilnoza"):
    r = client.put("/api/profile", json={"display_name": name, "category": "B", "language": "uz"})
    assert r.status_code == 200


def _seed_extra_questions(n: int) -> None:
    """Publish ``n`` extra category-B questions (uz) so the eligible pool > 20.

    Reuses an existing demo rule code (seeded by seed_demo_bank)."""
    sf = get_session_factory()
    with sf() as db:
        from app.domain.models import User

        author = db.scalar(select(User).where(User.telegram_id == "0"))
        if author is None:
            author = User(telegram_id="0", first_name="Seed")
            db.add(author)
            db.flush()
        for i in range(n):
            draft = QuestionDraft(
                category=Category.B,
                topic=Topic.GENERAL_RULES,
                prompt=f"Qo'shimcha test savoli #{i}?",
                short_explanation="Test uchun qo'shimcha savol.",
                options=[
                    OptionDraft(text="To'g'ri variant", is_correct=True, explanation="To'g'ri."),
                    OptionDraft(text="Noto'g'ri A", is_correct=False, explanation="Noto'g'ri."),
                    OptionDraft(text="Noto'g'ri B", is_correct=False, explanation="Noto'g'ri."),
                ],
                rule_code="YHQ:2.1",
                ai_assisted=True,
                sources=[SourceRefDraft(url="", note="test")],
            )
            publish_question(db, draft, author)
        db.commit()


def _big_bank(extra: int = 15) -> None:
    seed_demo_bank()
    _seed_extra_questions(extra)


def _grade_map(attempt_id: str):
    """Return [(question_version_id, correct_option_id, wrong_option_id), ...] ordered by position."""
    sf = get_session_factory()
    with sf() as db:
        mqs = db.scalars(
            select(MockQuestion)
            .where(MockQuestion.mock_attempt_id == attempt_id)
            .order_by(MockQuestion.position)
        ).all()
        out = []
        for mq in mqs:
            opts = db.scalars(
                select(AnswerOption).where(
                    AnswerOption.question_version_id == mq.question_version_id
                )
            ).all()
            correct = next(o.id for o in opts if o.is_correct)
            wrong = next((o.id for o in opts if not o.is_correct), None)
            out.append((mq.question_version_id, correct, wrong))
        return out


def _start(client) -> dict:
    r = client.post("/api/mock/attempts")
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------- #
# Selection / pinning
# --------------------------------------------------------------------------- #
def test_start_selects_20_unique_pinned_versions(client):
    _big_bank(extra=15)  # pool = 35
    _login(client)
    _onboard(client)
    state = _start(client)

    assert state["status"] == "in_progress"
    assert state["question_count"] == 20
    assert state["time_limit_seconds"] == 1500
    assert state["pass_correct"] == 18
    assert state["exam_config_version"] == 1

    qs = state["questions"]
    assert len(qs) == 20
    version_ids = [q["question_version_id"] for q in qs]
    assert len(set(version_ids)) == 20  # unique, without replacement
    positions = sorted(q["position"] for q in qs)
    assert positions == list(range(1, 21))

    # Pinned to CURRENT published versions.
    sf = get_session_factory()
    with sf() as db:
        from app.domain.models import Question, QuestionVersion

        for vid in version_ids:
            v = db.get(QuestionVersion, vid)
            assert v is not None
            q = db.get(Question, v.question_id)
            assert q.current_version_id == vid


def test_reopen_returns_same_set_no_regeneration(client):
    _big_bank(extra=15)
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]
    first = sorted((q["position"], q["question_version_id"]) for q in state["questions"])

    # Reopen via /current and via /{id}: identical pinned set + positions.
    cur = client.get("/api/mock/attempts/current").json()
    assert sorted((q["position"], q["question_version_id"]) for q in cur["questions"]) == first
    byid = client.get(f"/api/mock/attempts/{attempt_id}").json()
    assert sorted((q["position"], q["question_version_id"]) for q in byid["questions"]) == first


def test_only_one_in_progress_attempt(client):
    _big_bank()
    _login(client)
    _onboard(client)
    _start(client)
    r = client.post("/api/mock/attempts")
    assert r.status_code == 409


# --------------------------------------------------------------------------- #
# No-answer-leak
# --------------------------------------------------------------------------- #
def test_in_progress_payload_does_not_leak_answers(client):
    _big_bank()
    _login(client)
    _onboard(client)
    state = _start(client)
    for q in state["questions"]:
        assert "is_correct" not in q
        assert "explanation" not in q
        assert "short_explanation" not in q
        assert "rule" not in q
        assert "correct_option_id" not in q
        for opt in q["options"]:
            assert set(opt.keys()) == {"id", "position", "text"}

    # Same guarantee on reopen.
    cur = client.get("/api/mock/attempts/current").json()
    for q in cur["questions"]:
        for opt in q["options"]:
            assert set(opt.keys()) == {"id", "position", "text"}


# --------------------------------------------------------------------------- #
# Grading + boundary
# --------------------------------------------------------------------------- #
def _answer(client, attempt_id, qvid, option_id, marked=False):
    return client.post(
        f"/api/mock/attempts/{attempt_id}/answers",
        json={
            "question_version_id": qvid,
            "selected_option_id": option_id,
            "marked_for_review": marked,
        },
    )


def test_grading_server_side_pass_at_18(client):
    _big_bank()
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]
    grade = _grade_map(attempt_id)

    # Answer exactly 18 correctly, leave 2 unanswered.
    for qvid, correct, _wrong in grade[:18]:
        assert _answer(client, attempt_id, qvid, correct).status_code == 200

    res = client.post(f"/api/mock/attempts/{attempt_id}/submit").json()
    assert res["status"] == "completed"
    assert res["correct_count"] == 18
    assert res["answered_count"] == 18
    assert res["passed"] is True
    # Client never supplied correctness; result has server-side breakdown.
    assert res["result"]["per_topic"]
    assert isinstance(res["result"]["missed"], list)


def test_boundary_17_fails(client):
    _big_bank()
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]
    grade = _grade_map(attempt_id)

    for qvid, correct, _wrong in grade[:17]:
        assert _answer(client, attempt_id, qvid, correct).status_code == 200
    res = client.post(f"/api/mock/attempts/{attempt_id}/submit").json()
    assert res["correct_count"] == 17
    assert res["passed"] is False


def test_client_supplied_grade_fields_ignored(client):
    _big_bank()
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]
    grade = _grade_map(attempt_id)
    # Send a WRONG option but try to smuggle is_correct/correct_count/passed.
    qvid, _correct, wrong = grade[0]
    r = client.post(
        f"/api/mock/attempts/{attempt_id}/answers",
        json={
            "question_version_id": qvid,
            "selected_option_id": wrong,
            "is_correct": True,
            "correct_count": 20,
            "passed": True,
        },
    )
    assert r.status_code == 200
    res = client.post(f"/api/mock/attempts/{attempt_id}/submit").json()
    # Only the one wrong answer was recorded; smuggled fields ignored.
    assert res["correct_count"] == 0
    assert res["answered_count"] == 1
    assert res["passed"] is False


# --------------------------------------------------------------------------- #
# IDOR
# --------------------------------------------------------------------------- #
def test_idor_user_b_cannot_touch_user_a_attempt(client):
    _big_bank()
    _login(client, telegram_id=1001, name="Aziz")
    _onboard(client, name="Aziz")
    state = _start(client)
    attempt_id = state["id"]
    qvid = state["questions"][0]["question_version_id"]
    option_id = state["questions"][0]["options"][0]["id"]

    # User B logs in on the same client (session cookie replaced).
    _login(client, telegram_id=2002, name="Bek")
    _onboard(client, name="Bek")

    assert client.get(f"/api/mock/attempts/{attempt_id}").status_code == 404
    assert _answer(client, attempt_id, qvid, option_id).status_code == 404
    assert client.post(f"/api/mock/attempts/{attempt_id}/submit").status_code == 404
    assert client.get(f"/api/mock/attempts/{attempt_id}/review").status_code == 404


# --------------------------------------------------------------------------- #
# Injected question_version_id
# --------------------------------------------------------------------------- #
def test_answer_for_foreign_version_rejected(client):
    _big_bank()
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]
    r = _answer(client, attempt_id, "not-in-this-attempt", None)
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Timer / lazy finalize
# --------------------------------------------------------------------------- #
def _expire(attempt_id: str) -> None:
    sf = get_session_factory()
    with sf() as db:
        attempt = db.get(MockAttempt, attempt_id)
        attempt.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        db.commit()


def test_expired_attempt_auto_finalizes_on_next_access(client):
    _big_bank()
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]
    grade = _grade_map(attempt_id)
    # Answer 3 correctly before "time" runs out.
    for qvid, correct, _wrong in grade[:3]:
        assert _answer(client, attempt_id, qvid, correct).status_code == 200

    _expire(attempt_id)

    # Next access lazily finalizes -> completed, graded from saved answers.
    cur = client.get("/api/mock/attempts/current").json()
    assert cur["status"] == "completed"
    assert cur["correct_count"] == 3
    assert cur["passed"] is False

    # Further answers are rejected after finalize.
    qvid = grade[5][0]
    r = _answer(client, attempt_id, qvid, grade[5][1])
    assert r.status_code == 409


def test_late_answer_after_expiry_does_not_change_result(client):
    _big_bank()
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]
    grade = _grade_map(attempt_id)
    for qvid, correct, _wrong in grade[:5]:
        assert _answer(client, attempt_id, qvid, correct).status_code == 200

    _expire(attempt_id)
    finalized = client.get(f"/api/mock/attempts/{attempt_id}").json()
    assert finalized["status"] == "completed"
    baseline = finalized["correct_count"]
    assert baseline == 5

    # Attempt to add more correct answers after expiry -> rejected, result unchanged.
    for qvid, correct, _wrong in grade[5:10]:
        assert _answer(client, attempt_id, qvid, correct).status_code == 409
    again = client.get(f"/api/mock/attempts/{attempt_id}").json()
    assert again["correct_count"] == baseline


# --------------------------------------------------------------------------- #
# Review gating
# --------------------------------------------------------------------------- #
def test_review_only_after_completion(client):
    _big_bank()
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]

    # In progress -> review is blocked.
    assert client.get(f"/api/mock/attempts/{attempt_id}/review").status_code == 409

    grade = _grade_map(attempt_id)
    for qvid, correct, _wrong in grade[:18]:
        _answer(client, attempt_id, qvid, correct)
    client.post(f"/api/mock/attempts/{attempt_id}/submit")

    review = client.get(f"/api/mock/attempts/{attempt_id}/review")
    assert review.status_code == 200
    body = review.json()
    assert len(body["items"]) == 20
    # Review reveals full keys (correct answer, per-option explanation, rule).
    item = body["items"][0]
    assert item["correct_option_id"] is not None
    assert all("is_correct" in o and "explanation" in o for o in item["options"])
    assert item["rule"] and item["rule"]["text"]


# --------------------------------------------------------------------------- #
# Duplicate submit idempotent
# --------------------------------------------------------------------------- #
def test_duplicate_submit_is_idempotent(client):
    _big_bank()
    _login(client)
    _onboard(client)
    state = _start(client)
    attempt_id = state["id"]
    grade = _grade_map(attempt_id)
    for qvid, correct, _wrong in grade[:18]:
        _answer(client, attempt_id, qvid, correct)

    first = client.post(f"/api/mock/attempts/{attempt_id}/submit").json()
    second = client.post(f"/api/mock/attempts/{attempt_id}/submit").json()
    assert first["status"] == second["status"] == "completed"
    assert first["correct_count"] == second["correct_count"] == 18
    assert first["completed_at"] == second["completed_at"]  # not re-graded / re-timestamped
