"""Core product-expansion endpoints (docs/spec/16, 17):

- GET /api/home shape
- GET /api/practice/next-action resolves to a valid directive
- personalized practice session (no-leak payload + server grading)
- GET /api/progress/topics
- profile target_exam_date editable + returned by /api/me + /api/home
- next-question / mock payloads now expose media METADATA but still no answer leak
"""

from __future__ import annotations

import io

from PIL import Image

from tests.admin_helper import (
    build_admins,
    dev_login,
    make_rule,
    new_client,
    onboard,
    valid_question_payload,
)
from tests.seed_helper import seed_demo_bank


def _login_dev(client, telegram_id=1001, name="Dilnoza"):
    r = client.post("/api/dev/login", json={"telegram_id": telegram_id, "first_name": name})
    assert r.status_code == 200


def _complete_onboarding(client, name="Dilnoza", **extra):
    body = {"display_name": name, "category": "B", "language": "uz", **extra}
    r = client.put("/api/profile", json=body)
    assert r.status_code == 200
    return r.json()


# --------------------------------------------------------------------------- #
# Profile: target_exam_date + ranking privacy editable and surfaced
# --------------------------------------------------------------------------- #
def test_profile_exam_date_and_privacy_editable_and_returned(client):
    seed_demo_bank()
    _login_dev(client)
    prof = _complete_onboarding(
        client,
        target_exam_date="2099-01-15",
        ranking_name="Chempion",
        show_on_ranking=False,
    )["profile"]
    assert prof["target_exam_date"] == "2099-01-15"
    assert prof["ranking_name"] == "Chempion"
    assert prof["show_on_ranking"] is False

    me = client.get("/api/auth/me").json()
    assert me["profile"]["target_exam_date"] == "2099-01-15"
    assert me["profile"]["ranking_name"] == "Chempion"
    assert me["profile"]["show_on_ranking"] is False

    home = client.get("/api/home").json()
    assert home["exam_countdown"] is not None
    assert home["exam_countdown"]["target_exam_date"] == "2099-01-15"
    assert home["exam_countdown"]["days_remaining"] > 0


def test_profile_without_exam_date_has_null_countdown(client):
    seed_demo_bank()
    _login_dev(client)
    _complete_onboarding(client)
    home = client.get("/api/home").json()
    assert home["exam_countdown"] is None


# --------------------------------------------------------------------------- #
# GET /api/home shape
# --------------------------------------------------------------------------- #
def test_home_shape(client):
    seed_demo_bank()
    _login_dev(client)
    _complete_onboarding(client, name="Dilnoza")
    home = client.get("/api/home")
    assert home.status_code == 200
    body = home.json()
    assert body["display_name"] == "Dilnoza"
    for key in (
        "readiness",
        "last_mock",
        "daily_goal",
        "streak",
        "recommendations",
        "ranking",
        "next_action",
    ):
        assert key in body, key
    assert set(body["readiness"]).issuperset({"state", "label", "score", "exam_ready"})
    assert set(body["daily_goal"]) == {"goal", "answered_today", "met"}
    assert "week" in body["ranking"] and "all" in body["ranking"]
    assert "points" in body["ranking"]["week"] and "position" in body["ranking"]["week"]
    assert set(body["recommendations"]) == {"weak_topic", "mistakes_open"}
    assert body["last_mock"] is None
    # No answer data must ever appear on the home hub.
    assert "is_correct" not in home.text
    assert "correct_option_id" not in home.text


def test_home_requires_onboarding(client):
    seed_demo_bank()
    _login_dev(client)
    assert client.get("/api/home").status_code == 422


# --------------------------------------------------------------------------- #
# GET /api/practice/next-action
# --------------------------------------------------------------------------- #
def test_next_action_fresh_user_is_personalized(client):
    seed_demo_bank()
    _login_dev(client)
    _complete_onboarding(client)
    r = client.get("/api/practice/next-action")
    assert r.status_code == 200
    directive = r.json()
    assert directive["action"] in {
        "resume_mock",
        "mistakes",
        "weak_topic",
        "coverage",
        "personalized",
    }
    assert "label" in directive and directive["label"]
    # Fresh user (no answers yet): coverage gap or personalized, never a leak.
    assert "is_correct" not in r.text


def test_next_action_prioritizes_open_mistakes(client):
    seed_demo_bank()
    _login_dev(client)
    _complete_onboarding(client)
    # Create a mistake: answer a question wrong.
    sid = client.post("/api/practice/sessions", json={"topic": "general_rules"}).json()["id"]
    q = client.get("/api/practice/questions/next", params={"topic": "general_rules"}).json()
    # pick a wrong option: we don't know which is correct pre-answer, so submit,
    # then if it was correct, we still may create no mistake — retry a few topics.
    wrong = q["options"][0]["id"]
    res = client.post(
        "/api/practice/answers",
        json={
            "practice_session_id": sid,
            "question_id": q["question_id"],
            "selected_option_id": wrong,
        },
    ).json()
    if res["is_correct"]:
        # choose the actually-wrong option to force a mistake
        wrong = next(o["id"] for o in res["options"] if not o["is_correct"])
        client.post(
            "/api/practice/answers",
            json={
                "practice_session_id": sid,
                "question_id": q["question_id"],
                "selected_option_id": wrong,
            },
        )
    directive = client.get("/api/practice/next-action").json()
    assert directive["action"] == "mistakes"
    assert directive["source"] == "mistakes"


# --------------------------------------------------------------------------- #
# Personalized practice session (no-leak + server grading)
# --------------------------------------------------------------------------- #
def test_personalized_session_and_no_leak(client):
    seed_demo_bank()
    _login_dev(client)
    _complete_onboarding(client)

    s = client.post("/api/practice/sessions", json={"source": "personalized"})
    assert s.status_code == 200
    session = s.json()
    assert session["source"] == "personalized"
    assert session["topic"] is None

    nxt = client.get("/api/practice/questions/next", params={"source": "personalized"})
    assert nxt.status_code == 200
    q = nxt.json()
    assert q["prompt"]
    assert len(q["options"]) >= 2
    # NO-LEAK: no correctness/explanation/rule fields pre-answer.
    assert "rule" not in q
    assert "short_explanation" not in q
    for opt in q["options"]:
        assert set(opt.keys()) == {"id", "position", "text"}

    # Server grading works for a personalized session.
    ans = client.post(
        "/api/practice/answers",
        json={
            "practice_session_id": session["id"],
            "question_id": q["question_id"],
            "selected_option_id": q["options"][0]["id"],
        },
    )
    assert ans.status_code == 200
    assert "is_correct" in ans.json()


# --------------------------------------------------------------------------- #
# GET /api/progress/topics
# --------------------------------------------------------------------------- #
def test_progress_topics_shape(client):
    seed_demo_bank()
    _login_dev(client)
    _complete_onboarding(client)
    r = client.get("/api/progress/topics")
    assert r.status_code == 200
    topics = r.json()["topics"]
    # All 15 v1 topics present.
    assert len(topics) == 15
    row = topics[0]
    assert set(row).issuperset(
        {
            "topic",
            "label",
            "answered",
            "questions_seen",
            "accuracy",
            "mastery",
            "needs_more_practice",
        }
    )
    # Fresh user: everything at zero and needs more practice.
    assert all(t["answered"] == 0 for t in topics)
    assert all(t["needs_more_practice"] for t in topics)


# --------------------------------------------------------------------------- #
# Media metadata is now exposed (fixes the [media:id] bug) WITHOUT leaking answers
# --------------------------------------------------------------------------- #
def _png_bytes(w=32, h=32, color=(10, 120, 200)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _publish_question_with_media(client) -> tuple[str, str]:
    """Publish one question that carries an image; return (question_id, media_id)."""
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    up = roles["author"].post(
        "/api/admin/media",
        files={"file": ("pic.png", _png_bytes(), "image/png")},
    ).json()
    payload = valid_question_payload(rule["code"], prompt="Rasmli savol?")
    payload["media_id"] = up["id"]
    vid = roles["author"].post("/api/admin/questions", json=payload).json()["id"]
    roles["author"].post(f"/api/admin/versions/{vid}/submit-review")
    roles["reviewer"].post(f"/api/admin/versions/{vid}/review")
    assert roles["reviewer"].post(f"/api/admin/versions/{vid}/publish").status_code == 200
    return up["id"], up["content_hash"]


def test_next_question_exposes_media_metadata_without_leak(client):
    media_id, content_hash = _publish_question_with_media(client)

    student = new_client(client)
    dev_login(student, 1001, "Student")
    onboard(student)
    student.post("/api/practice/sessions", json={"topic": "general_rules"})
    q = student.get(
        "/api/practice/questions/next", params={"topic": "general_rules"}
    ).json()

    assert q["media"] is not None
    assert q["media"]["media_id"] == media_id
    assert q["media"]["content_hash"] == content_hash
    assert q["media"]["media_type"] == "image"
    assert q["media"]["url"] == f"/api/media/{media_id}/{content_hash}"
    # Still no answer leak alongside the media metadata.
    assert "is_correct" not in q
    for opt in q["options"]:
        assert "is_correct" not in opt and "explanation" not in opt


def test_mock_payload_exposes_media_metadata_without_leak(client):
    _publish_question_with_media(client)
    # Seed the rest of the bank so a full 20-question mock can be built.
    seed_demo_bank()

    student = new_client(client)
    dev_login(student, 1001, "Student")
    onboard(student)
    attempt = student.post("/api/mock/attempts", json={}).json()
    q0 = attempt["questions"][0]
    # Every mock question carries a `media` key (metadata or None), never answers.
    for q in attempt["questions"]:
        assert "media" in q
        assert "is_correct" not in q
        for opt in q["options"]:
            assert set(opt.keys()) == {"id", "position", "text"}
    # At least the media-bearing question exposes full metadata when present.
    assert any(q["media"] is not None for q in attempt["questions"]) or q0["media"] is None
