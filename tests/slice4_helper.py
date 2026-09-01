"""Helpers for Slice 4 tests (mistakes / ranking / readiness / dashboard)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.domain.enums import PointsSource
from app.domain.models import (
    AnswerOption,
    MockAttempt,
    QuestionVersion,
    User,
    UserPointsLedger,
)
from app.storage.db import session_scope
from sqlalchemy import func, select


def new_client(client) -> TestClient:
    return TestClient(client.app)


def login(c: TestClient, telegram_id: int, name: str = "U") -> dict:
    r = c.post("/api/dev/login", json={"telegram_id": telegram_id, "first_name": name})
    assert r.status_code == 200, r.text
    return r.json()["user"]


def onboard(c: TestClient, name: str = "U", ranking_name: str | None = None,
            show_on_ranking: bool = True, daily_goal: int | None = None) -> None:
    body = {"display_name": name, "category": "B", "language": "uz",
            "show_on_ranking": show_on_ranking}
    if ranking_name is not None:
        body["ranking_name"] = ranking_name
    if daily_goal is not None:
        body["daily_goal"] = daily_goal
    r = c.put("/api/profile", json=body)
    assert r.status_code == 200, r.text


def make_user(client, telegram_id: int, name: str = "U", **kw) -> TestClient:
    c = new_client(client)
    login(c, telegram_id, name)
    onboard(c, name=name, **kw)
    return c


def user_id_by_telegram(telegram_id: int) -> str:
    with session_scope() as db:
        u = db.scalar(select(User).where(User.telegram_id == str(telegram_id)))
        assert u is not None
        return u.id


def correct_option_id(version_id: str) -> str:
    with session_scope() as db:
        opt = db.scalar(
            select(AnswerOption).where(
                AnswerOption.question_version_id == version_id,
                AnswerOption.is_correct.is_(True),
            )
        )
        assert opt is not None, f"no correct option for {version_id}"
        return opt.id


def wrong_option_id(version_id: str) -> str:
    with session_scope() as db:
        opt = db.scalar(
            select(AnswerOption).where(
                AnswerOption.question_version_id == version_id,
                AnswerOption.is_correct.is_(False),
            )
        )
        assert opt is not None, f"no wrong option for {version_id}"
        return opt.id


def correct_option_for_question(question_id: str) -> str:
    with session_scope() as db:
        from app.domain.models import Question

        q = db.get(Question, question_id)
        return correct_option_id(q.current_version_id)


def ledger_points(telegram_id: int, source: PointsSource | None = None) -> int:
    uid = user_id_by_telegram(telegram_id)
    with session_scope() as db:
        q = select(func.coalesce(func.sum(UserPointsLedger.points), 0)).where(
            UserPointsLedger.user_id == uid
        )
        if source is not None:
            q = q.where(UserPointsLedger.source == source)
        return int(db.scalar(q) or 0)


def ledger_count(telegram_id: int, source: PointsSource | None = None) -> int:
    uid = user_id_by_telegram(telegram_id)
    with session_scope() as db:
        q = select(func.count(UserPointsLedger.id)).where(UserPointsLedger.user_id == uid)
        if source is not None:
            q = q.where(UserPointsLedger.source == source)
        return int(db.scalar(q) or 0)


# --------------------------------------------------------------------------- #
# Practice answering
# --------------------------------------------------------------------------- #
def start_session(c: TestClient, topic: str | None = None, source: str | None = None) -> str:
    body: dict = {}
    if topic is not None:
        body["topic"] = topic
    if source is not None:
        body["source"] = source
    r = c.post("/api/practice/sessions", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def next_q(c: TestClient, topic: str | None = None, source: str | None = None) -> dict:
    params = {}
    if topic is not None:
        params["topic"] = topic
    if source is not None:
        params["source"] = source
    r = c.get("/api/practice/questions/next", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def answer(c: TestClient, session_id: str, q: dict, correct: bool,
           time_spent: int | None = None, extra: dict | None = None) -> dict:
    version_id = q["question_version_id"]
    opt = correct_option_id(version_id) if correct else wrong_option_id(version_id)
    body = {
        "practice_session_id": session_id,
        "question_id": q["question_id"],
        "selected_option_id": opt,
    }
    if time_spent is not None:
        body["time_spent_seconds"] = time_spent
    if extra:
        body.update(extra)
    r = c.post("/api/practice/answers", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def answer_specific_topic_correct(c: TestClient, topic: str, times: int) -> str | None:
    """Answer the topic's question correctly ``times`` (repeats allowed). Returns qid."""
    sid = start_session(c, topic=topic, source="topic")
    q = next_q(c, topic=topic)
    for _ in range(times):
        answer(c, sid, q, correct=True)
    return q["question_id"]


# --------------------------------------------------------------------------- #
# Mock answering
# --------------------------------------------------------------------------- #
def mock_question_versions(attempt_id: str) -> list[str]:
    with session_scope() as db:
        from app.domain.models import MockQuestion

        rows = db.scalars(
            select(MockQuestion.question_version_id)
            .where(MockQuestion.mock_attempt_id == attempt_id)
            .order_by(MockQuestion.position)
        )
        return list(rows)


def run_mock(c: TestClient, num_correct: int | None = None) -> dict:
    """Start a mock, answer ``num_correct`` questions correctly (rest wrong), submit.
    ``num_correct=None`` -> all correct. Returns the completed attempt state."""
    start = c.post("/api/mock/attempts", json={})
    assert start.status_code == 200, start.text
    attempt = start.json()
    attempt_id = attempt["id"]
    versions = [q["question_version_id"] for q in attempt["questions"]]
    total = len(versions)
    target = total if num_correct is None else num_correct
    for i, vid in enumerate(versions):
        want_correct = i < target
        opt = correct_option_id(vid) if want_correct else wrong_option_id(vid)
        r = c.post(
            f"/api/mock/attempts/{attempt_id}/answers",
            json={"question_version_id": vid, "selected_option_id": opt,
                  "marked_for_review": False},
        )
        assert r.status_code == 200, r.text
    done = c.post(f"/api/mock/attempts/{attempt_id}/submit", json={})
    assert done.status_code == 200, done.text
    return done.json()
