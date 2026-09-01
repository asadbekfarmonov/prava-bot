import pytest

from tests.seed_helper import seed_demo_bank


def _login_dev(client, telegram_id=1001, name="Dilnoza"):
    r = client.post("/api/dev/login", json={"telegram_id": telegram_id, "first_name": name})
    assert r.status_code == 200


def _complete_onboarding(client, name="Dilnoza"):
    r = client.put("/api/profile", json={"display_name": name, "category": "B", "language": "uz"})
    assert r.status_code == 200


def test_practice_requires_onboarding(client):
    seed_demo_bank()
    _login_dev(client)
    # No profile yet -> onboarding gate returns 422
    r = client.post("/api/practice/sessions", json={})
    assert r.status_code == 422


def test_practice_happy_path(client):
    seed_demo_bank()
    _login_dev(client)
    _complete_onboarding(client)

    session = client.post("/api/practice/sessions", json={"topic": "road_signs"})
    assert session.status_code == 200
    session_id = session.json()["id"]

    nxt = client.get("/api/practice/questions/next", params={"topic": "road_signs"})
    assert nxt.status_code == 200
    q = nxt.json()
    assert q["prompt"]
    assert len(q["options"]) >= 2

    # Submit the first option; grading is server-side.
    ans = client.post(
        "/api/practice/answers",
        json={
            "practice_session_id": session_id,
            "question_id": q["question_id"],
            "selected_option_id": q["options"][0]["id"],
        },
    )
    assert ans.status_code == 200
    result = ans.json()
    assert "is_correct" in result
    assert result["correct_option_id"] is not None
    # Exactly one correct option, each option has an explanation, rule text present.
    correct = [o for o in result["options"] if o["is_correct"]]
    assert len(correct) == 1
    assert all(o["explanation"] for o in result["options"])
    assert result["rule"] and result["rule"]["text"]
    assert result["short_explanation"]


def test_next_question_does_not_leak_answer(client):
    seed_demo_bank()
    _login_dev(client)
    _complete_onboarding(client)
    client.post("/api/practice/sessions", json={})
    nxt = client.get("/api/practice/questions/next")
    assert nxt.status_code == 200
    q = nxt.json()
    # No correctness/explanation/rule fields anywhere in the payload.
    assert "rule" not in q
    assert "short_explanation" not in q
    for opt in q["options"]:
        assert set(opt.keys()) == {"id", "position", "text"}
        assert "is_correct" not in opt
        assert "explanation" not in opt


def test_idor_cannot_read_another_users_session(client):
    seed_demo_bank()
    # User A creates a session.
    _login_dev(client, telegram_id=1001, name="Aziz")
    _complete_onboarding(client, name="Aziz")
    session_id = client.post("/api/practice/sessions", json={}).json()["id"]

    # User B logs in (same client -> session cookie replaced) and tries to read it.
    _login_dev(client, telegram_id=2002, name="Bek")
    _complete_onboarding(client, name="Bek")
    r = client.get(f"/api/practice/sessions/{session_id}")
    assert r.status_code == 404

    # And cannot submit an answer into A's session either.
    nxt = client.get("/api/practice/questions/next").json()
    r2 = client.post(
        "/api/practice/answers",
        json={
            "practice_session_id": session_id,
            "question_id": nxt["question_id"],
            "selected_option_id": nxt["options"][0]["id"],
        },
    )
    assert r2.status_code == 404


def test_practice_repeatable_across_sessions(client):
    seed_demo_bank()
    _login_dev(client)
    _complete_onboarding(client)

    # Answer the same question in two different sessions -> both succeed (no global unique).
    nxt = client.get("/api/practice/questions/next", params={"topic": "general_rules"}).json()
    question_id = nxt["question_id"]
    option_id = nxt["options"][0]["id"]

    for _ in range(2):
        sid = client.post("/api/practice/sessions", json={"topic": "general_rules"}).json()["id"]
        r = client.post(
            "/api/practice/answers",
            json={
                "practice_session_id": sid,
                "question_id": question_id,
                "selected_option_id": option_id,
            },
        )
        assert r.status_code == 200


def test_injected_option_id_rejected(client):
    seed_demo_bank()
    _login_dev(client)
    _complete_onboarding(client)
    sid = client.post("/api/practice/sessions", json={}).json()["id"]
    nxt = client.get("/api/practice/questions/next").json()
    r = client.post(
        "/api/practice/answers",
        json={
            "practice_session_id": sid,
            "question_id": nxt["question_id"],
            "selected_option_id": "not-a-real-option-id",
        },
    )
    assert r.status_code == 400
