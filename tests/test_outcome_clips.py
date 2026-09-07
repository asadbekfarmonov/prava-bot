"""Per-question 'animated outcome' clips (success/fail media).

Covers (docs/spec/09 no-answer-leak):
  * authoring persists success_media_id/fail_media_id on the version (create + edit),
    and a nonexistent id is rejected at save=live with HTTP 422;
  * the clips (and even their key names) are ABSENT from every pre-answer / live
    payload (practice next-question, live mock start + current) — asserted on the RAW
    response bytes;
  * the clips ARE revealed post-answer: practice submit-answer result + mock review.
"""

from __future__ import annotations

import io

from PIL import Image
from sqlalchemy import select

from app.domain.models import AnswerOption, Question
from app.storage.db import session_scope
from tests.admin_helper import (
    build_admins,
    dev_login,
    make_rule,
    new_client,
    onboard,
    question_id_for_version,
    valid_question_payload,
)

# Tokens that must NEVER appear in a pre-answer / live payload.
_CLIP_TOKENS = ("success_media", "fail_media", "success_media_id", "fail_media_id")


def _png(color) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(roles, name, color) -> dict:
    r = roles["author"].post(
        "/api/admin/media", files={"file": (name, _png(color), "image/png")}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _publish_clip_question(client, *, prompt="Animatsiyali savol?"):
    """Author a published question carrying both outcome clips. Returns dict with
    roles, version body, question_id, and the two uploaded media ids/hashes."""
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    success = _upload(roles, "success.png", (10, 200, 10))
    fail = _upload(roles, "fail.png", (200, 10, 10))
    payload = valid_question_payload(rule["code"], prompt=prompt)
    payload["success_media_id"] = success["id"]
    payload["fail_media_id"] = fail["id"]
    r = roles["author"].post("/api/admin/questions", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    return {
        "roles": roles,
        "rule": rule,
        "version": body,
        "question_id": question_id_for_version(body["id"]),
        "success": success,
        "fail": fail,
    }


def _student(client, tid=1001):
    s = new_client(client)
    dev_login(s, tid, "Student")
    onboard(s)
    return s


# --------------------------------------------------------------------------- #
# Authoring persistence + validation
# --------------------------------------------------------------------------- #
def test_create_persists_outcome_clips_on_version(client):
    ctx = _publish_clip_question(client)
    body = ctx["version"]
    assert body["status"] == "published"
    # _version_out (admin-only) surfaces the ids for editor prefill.
    assert body["success_media_id"] == ctx["success"]["id"]
    assert body["fail_media_id"] == ctx["fail"]["id"]
    # Persisted on the actual version row.
    from app.domain.models import QuestionVersion

    with session_scope() as db:
        v = db.get(QuestionVersion, body["id"])
        assert v.success_media_id == ctx["success"]["id"]
        assert v.fail_media_id == ctx["fail"]["id"]


def test_edit_forks_new_version_keeping_clips(client):
    ctx = _publish_clip_question(client)
    roles, qid = ctx["roles"], ctx["question_id"]
    # Edit a PUBLISHED question -> forks a NEW immutable version; clips carried through.
    payload = valid_question_payload(ctx["rule"]["code"], prompt="Tahrirlangan?")
    payload["success_media_id"] = ctx["success"]["id"]
    payload["fail_media_id"] = ctx["fail"]["id"]
    r = roles["author"].put(f"/api/admin/questions/{qid}", json=payload)
    assert r.status_code == 200, r.text
    new_body = r.json()
    assert new_body["id"] != ctx["version"]["id"]  # forked
    assert new_body["version"] > ctx["version"]["version"]
    assert new_body["success_media_id"] == ctx["success"]["id"]
    assert new_body["fail_media_id"] == ctx["fail"]["id"]


def test_nonexistent_clip_media_id_rejected_422(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:88.1")
    payload = valid_question_payload(rule["code"], prompt="Yomon media?")
    payload["success_media_id"] = "does-not-exist-id"
    r = roles["author"].post("/api/admin/questions", json=payload)
    assert r.status_code == 422, r.text
    assert "errors" in r.json()["detail"]
    # fail side too
    payload2 = valid_question_payload(rule["code"], prompt="Yomon media 2?")
    payload2["fail_media_id"] = "nope-id"
    r2 = roles["author"].post("/api/admin/questions", json=payload2)
    assert r2.status_code == 422, r2.text


def test_clips_are_optional(client):
    """Omitting clips must not affect the relaxed publish floor (create=live)."""
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:88.2")
    r = roles["author"].post(
        "/api/admin/questions", json=valid_question_payload(rule["code"])
    )
    assert r.status_code == 201, r.text
    assert r.json()["success_media_id"] is None
    assert r.json()["fail_media_id"] is None


# --------------------------------------------------------------------------- #
# NO-LEAK: clips absent from pre-answer / live payloads (raw bytes)
# --------------------------------------------------------------------------- #
def test_practice_next_question_has_no_clip_tokens(client):
    _publish_clip_question(client)
    s = _student(client)
    s.post("/api/practice/sessions", json={"topic": "general_rules"})
    resp = s.get("/api/practice/questions/next", params={"topic": "general_rules"})
    assert resp.status_code == 200
    raw = resp.text
    for token in _CLIP_TOKENS:
        assert token not in raw, f"clip token {token!r} leaked in next-question body"


def test_live_mock_has_no_clip_tokens(client):
    # Publish exactly 20 category-B questions (pool == question_count) so ALL are
    # selected; one of them carries the outcome clips.
    ctx = _publish_clip_question(client, prompt="Mock klipli savol?")
    roles, rule = ctx["roles"], ctx["rule"]
    for i in range(19):
        p = valid_question_payload(rule["code"], prompt=f"Mock savol #{i}?")
        assert roles["author"].post("/api/admin/questions", json=p).status_code == 201

    s = _student(client)
    start = s.post("/api/mock/attempts", json={})
    assert start.status_code == 200, start.text
    assert start.json()["status"] == "in_progress"
    for token in _CLIP_TOKENS:
        assert token not in start.text, f"clip token {token!r} leaked in live mock start"
    cur = s.get("/api/mock/attempts/current")
    for token in _CLIP_TOKENS:
        assert token not in cur.text, f"clip token {token!r} leaked in live mock current"


# --------------------------------------------------------------------------- #
# REVEAL: clips exposed post-answer (practice result) + post-completion (review)
# --------------------------------------------------------------------------- #
def test_practice_result_reveals_clips(client):
    ctx = _publish_clip_question(client)
    s = _student(client)
    session_id = s.post("/api/practice/sessions", json={"topic": "general_rules"}).json()["id"]
    qid = ctx["question_id"]
    with session_scope() as db:
        q = db.get(Question, qid)
        opts = list(
            db.scalars(
                select(AnswerOption)
                .where(AnswerOption.question_version_id == q.current_version_id)
                .order_by(AnswerOption.position)
            )
        )
        correct_id = next(o.id for o in opts if o.is_correct)

    resp = s.post(
        "/api/practice/answers",
        json={
            "practice_session_id": session_id,
            "question_id": qid,
            "selected_option_id": correct_id,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_correct"] is True
    # Both clips present in the post-answer result.
    assert body["success_media"] is not None
    assert body["success_media"]["media_id"] == ctx["success"]["id"]
    assert body["fail_media"] is not None
    assert body["fail_media"]["media_id"] == ctx["fail"]["id"]


def test_practice_result_clips_null_when_absent(client):
    """A question without clips returns explicit null clip fields (keys always present)."""
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:77.1")
    vid = roles["author"].post(
        "/api/admin/questions", json=valid_question_payload(rule["code"])
    ).json()["id"]
    qid = question_id_for_version(vid)
    s = _student(client)
    session_id = s.post("/api/practice/sessions", json={"topic": "general_rules"}).json()["id"]
    with session_scope() as db:
        q = db.get(Question, qid)
        opt = db.scalar(
            select(AnswerOption).where(AnswerOption.question_version_id == q.current_version_id)
        )
        opt_id = opt.id
    body = s.post(
        "/api/practice/answers",
        json={
            "practice_session_id": session_id,
            "question_id": qid,
            "selected_option_id": opt_id,
        },
    ).json()
    assert body["success_media"] is None
    assert body["fail_media"] is None


def test_mock_review_reveals_clips(client):
    # Pool == 20 so the clip question is guaranteed in the pinned set.
    ctx = _publish_clip_question(client, prompt="Mock klipli savol?")
    roles, rule = ctx["roles"], ctx["rule"]
    for i in range(19):
        p = valid_question_payload(rule["code"], prompt=f"Mock savol #{i}?")
        assert roles["author"].post("/api/admin/questions", json=p).status_code == 201

    s = _student(client)
    start = s.post("/api/mock/attempts", json={}).json()
    attempt_id = start["id"]
    # Submit immediately (no answers needed to reach review after completion).
    s.post(f"/api/mock/attempts/{attempt_id}/submit")
    review = s.get(f"/api/mock/attempts/{attempt_id}/review")
    assert review.status_code == 200, review.text
    items = review.json()["items"]
    # Every review item carries the clip keys (may be null) ...
    for it in items:
        assert "success_media" in it
        assert "fail_media" in it
    # ... and the clip-bearing question reveals the concrete clips.
    clip_items = [
        it for it in items if it["success_media"] is not None or it["fail_media"] is not None
    ]
    assert len(clip_items) >= 1
    ci = clip_items[0]
    assert ci["success_media"]["media_id"] == ctx["success"]["id"]
    assert ci["fail_media"]["media_id"] == ctx["fail"]["id"]


# --------------------------------------------------------------------------- #
# Media visibility: outcome clips on a PUBLISHED question are public; an
# unreferenced clip stays admin-only (regression for _is_published_media).
# --------------------------------------------------------------------------- #
def test_published_outcome_clips_are_public_media(client):
    ctx = _publish_clip_question(client)  # create = live -> question PUBLISHED
    s = new_client(client)
    dev_login(s, 4242, "Student")
    onboard(s)
    for m in (ctx["success"], ctx["fail"]):
        url = f"/api/media/{m['id']}/{m['content_hash']}"
        resp = s.get(url)
        assert resp.status_code == 200, (url, resp.status_code, resp.text)
        assert resp.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_unreferenced_clip_media_is_admin_only(client):
    roles = build_admins(client)
    up = _upload(roles, "orphan.png", (5, 5, 5))  # uploaded, never attached
    anon = new_client(client)
    assert anon.get(f"/api/media/{up['id']}/{up['content_hash']}").status_code == 404
    # Admin can still fetch the draft/unused media (private).
    admin_resp = roles["author"].get(f"/api/media/{up['id']}/{up['content_hash']}")
    assert admin_resp.status_code == 200
    assert admin_resp.headers["Cache-Control"] == "private, no-store"
