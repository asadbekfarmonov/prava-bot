"""QA adversarial gap coverage for the redesign + core endpoints (docs/spec/16, 17, 09).

These strengthen the existing test_core_expansion suite by asserting on the RAW
response bytes (not just dict keys) that answer-bearing fields never leak on the
media-carrying question surfaces, and by covering the next-action resume_mock
priority that the happy-path tests omit.
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

# Field names that must NEVER appear pre-answer on an embedding surface (docs/spec/09).
_LEAK_TOKENS = ("is_correct", "explanation", "short_explanation", '"rule"', "correct_option_id")


def _png_bytes(w=32, h=32, color=(9, 130, 210)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _publish_question_with_media(client) -> tuple[str, str]:
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    up = roles["author"].post(
        "/api/admin/media", files={"file": ("pic.png", _png_bytes(), "image/png")}
    ).json()
    payload = valid_question_payload(rule["code"], prompt="Rasmli savol?")
    payload["media_id"] = up["id"]
    vid = roles["author"].post("/api/admin/questions", json=payload).json()["id"]
    roles["author"].post(f"/api/admin/versions/{vid}/submit-review")
    roles["reviewer"].post(f"/api/admin/versions/{vid}/review")
    assert roles["reviewer"].post(f"/api/admin/versions/{vid}/publish").status_code == 200
    return up["id"], up["content_hash"]


def _student(client, tid=1001):
    s = new_client(client)
    dev_login(s, tid, "Student")
    onboard(s)
    return s


# --------------------------------------------------------------------------- #
# RAW-BYTES no-leak on the media-bearing practice next-question surface.
# --------------------------------------------------------------------------- #
def test_next_question_with_media_raw_body_has_no_answer_tokens(client):
    media_id, content_hash = _publish_question_with_media(client)
    s = _student(client)
    s.post("/api/practice/sessions", json={"topic": "general_rules"})
    resp = s.get("/api/practice/questions/next", params={"topic": "general_rules"})
    assert resp.status_code == 200
    raw = resp.text
    # Media metadata is present (the [media:id] bug is fixed) ...
    assert content_hash in raw
    assert f"/api/media/{media_id}/{content_hash}" in raw
    # ... but NOT a single answer-bearing token leaks pre-answer.
    for token in _LEAK_TOKENS:
        assert token not in raw, f"leak token {token!r} present in next-question body"


# --------------------------------------------------------------------------- #
# RAW-BYTES no-leak on a LIVE mock attempt (with a media-bearing question in the set).
# --------------------------------------------------------------------------- #
def test_live_mock_raw_body_has_no_answer_tokens(client):
    _publish_question_with_media(client)
    seed_demo_bank()
    s = _student(client)
    start = s.post("/api/mock/attempts", json={})
    assert start.status_code == 200
    raw = start.text
    assert start.json()["status"] == "in_progress"
    # A media URL is served in the live payload; answers are not.
    assert "/api/media/" in raw
    for token in _LEAK_TOKENS:
        assert token not in raw, f"leak token {token!r} present in live mock body"
    # The GET current view is equally clean.
    cur = s.get("/api/mock/attempts/current")
    for token in _LEAK_TOKENS:
        assert token not in cur.text, f"leak token {token!r} present in mock current body"


# --------------------------------------------------------------------------- #
# next-action resume priority: an in-progress mock outranks everything else.
# --------------------------------------------------------------------------- #
def test_next_action_resumes_active_mock_first(client):
    seed_demo_bank()
    s = _student(client)
    attempt = s.post("/api/mock/attempts", json={}).json()
    directive = s.get("/api/practice/next-action").json()
    assert directive["action"] == "resume_mock"
    assert directive["attempt_id"] == attempt["id"]
    # A resume directive carries no source/topic and never a leak.
    assert directive["source"] is None


# --------------------------------------------------------------------------- #
# Personalized source is server-authoritative: a client cannot smuggle is_correct
# into an answer submission to fake a pass (mass-assignment allowlist, docs/spec/09).
# --------------------------------------------------------------------------- #
def test_personalized_answer_ignores_client_supplied_is_correct(client):
    seed_demo_bank()
    s = _student(client)
    session = s.post("/api/practice/sessions", json={"source": "personalized"}).json()
    q = s.get("/api/practice/questions/next", params={"source": "personalized"}).json()
    # Submit picking option[0] but LIE with client-side is_correct/correct fields.
    resp = s.post(
        "/api/practice/answers",
        json={
            "practice_session_id": session["id"],
            "question_id": q["question_id"],
            "selected_option_id": q["options"][0]["id"],
            "is_correct": True,
            "correct_count": 999,
            "passed": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # Server graded from stored AnswerOption.is_correct, not the client's claim.
    server_truth = next(o["is_correct"] for o in body["options"] if o["id"] == q["options"][0]["id"])
    assert body["is_correct"] == server_truth


# --------------------------------------------------------------------------- #
# Topic mastery must reflect ACCURACY, not content completion (docs/spec/16 Phase 16).
# A fresh user has 0 mastery on every topic even though the bank is fully published.
# --------------------------------------------------------------------------- #
def test_topic_mastery_is_not_completion(client):
    seed_demo_bank()
    s = _student(client)
    rows = s.get("/api/progress/topics").json()["topics"]
    assert len(rows) == 15
    # No answers yet -> mastery 0 everywhere despite a fully-published bank.
    assert all(r["mastery"] == 0.0 for r in rows)
    assert all(r["accuracy"] == 0.0 for r in rows)
    assert all(r["questions_seen"] == 0 for r in rows)
