"""QA reviewer additions (Slice 1).

Closes edge cases the developer suite left uncovered:
- session lifecycle (logout truly invalidates; protected routes then 401);
- skipped-answer grading (no option selected -> graded incorrect, answer still recorded);
- injection with a *real* option id belonging to a DIFFERENT question -> rejected
  (stronger than the existing fake-id test; proves per-version option scoping);
- unknown topic -> 400 (input validation on both session + next-question);
- initData missing the user field -> 401 (identity must come only from signed data).
"""

import json
import time
from urllib.parse import quote, urlencode

import hashlib
import hmac

from tests.conftest import BOT_TOKEN
from tests.test_auth import signed_init_data
from tests.seed_helper import seed_demo_bank


def _login(client, telegram_id=1001, name="Dilnoza"):
    assert client.post(
        "/api/dev/login", json={"telegram_id": telegram_id, "first_name": name}
    ).status_code == 200


def _onboard(client, name="Dilnoza"):
    assert client.put(
        "/api/profile", json={"display_name": name, "category": "B", "language": "uz"}
    ).status_code == 200


# --------------------------------------------------------------------------- #
# Session lifecycle: logout must invalidate the session.
# --------------------------------------------------------------------------- #
def test_logout_invalidates_session(client):
    _login(client)
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    # After logout, identity is gone -> protected routes reject.
    assert client.get("/api/auth/me").status_code == 401


# --------------------------------------------------------------------------- #
# Skipped answer: no option selected still grades (incorrect) and records a row,
# and still reveals the correct option + explanations afterwards.
# --------------------------------------------------------------------------- #
def test_skipped_answer_graded_incorrect_and_recorded(client):
    seed_demo_bank()
    _login(client)
    _onboard(client)
    sid = client.post("/api/practice/sessions", json={"topic": "signals"}).json()["id"]
    q = client.get("/api/practice/questions/next", params={"topic": "signals"}).json()
    r = client.post(
        "/api/practice/answers",
        json={
            "practice_session_id": sid,
            "question_id": q["question_id"],
            "selected_option_id": None,  # user skipped
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_correct"] is False
    assert body["selected_option_id"] is None
    assert body["correct_option_id"] is not None  # correct answer still revealed post-hoc


# --------------------------------------------------------------------------- #
# Cross-question injection: a REAL option id from a different question must be
# rejected — options are scoped to the resolved version, not global.
# --------------------------------------------------------------------------- #
def test_real_option_id_from_other_question_rejected(client):
    seed_demo_bank()
    _login(client)
    _onboard(client)
    sid = client.post("/api/practice/sessions", json={}).json()["id"]

    q_signals = client.get("/api/practice/questions/next", params={"topic": "signals"}).json()
    q_signs = client.get("/api/practice/questions/next", params={"topic": "road_signs"}).json()
    assert q_signals["question_id"] != q_signs["question_id"]

    foreign_option_id = q_signs["options"][0]["id"]
    r = client.post(
        "/api/practice/answers",
        json={
            "practice_session_id": sid,
            "question_id": q_signals["question_id"],   # signals question
            "selected_option_id": foreign_option_id,   # but a road_signs option id
        },
    )
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Input validation: unknown topic -> 400 on both endpoints.
# --------------------------------------------------------------------------- #
def test_unknown_topic_rejected(client):
    seed_demo_bank()
    _login(client)
    _onboard(client)
    assert client.post(
        "/api/practice/sessions", json={"topic": "not_a_real_topic"}
    ).status_code == 400
    assert client.get(
        "/api/practice/questions/next", params={"topic": "not_a_real_topic"}
    ).status_code == 400


# --------------------------------------------------------------------------- #
# initData without a user field: a valid HMAC but no user must not create a
# session (identity must come only from the signed user object).
# --------------------------------------------------------------------------- #
def test_init_data_without_user_rejected(client):
    pairs = {"auth_date": str(int(time.time())), "query_id": "q1"}
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    init_data = urlencode(pairs, quote_via=quote)
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": init_data})
    assert r.status_code == 401
