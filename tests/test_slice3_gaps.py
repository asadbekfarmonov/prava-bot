"""QA gap coverage for Slice 3 (adversarial). Complements the implementer's tests:

- mass-assignment: a client cannot escalate by sending ``admin_role`` in a body;
- GIF frame-bomb rejection (docs/spec/09 media-upload-security);
- "no bytes in Postgres" — QuestionMedia is metadata-only (structural assertion);
- there is NO /api/questions/{id}/media route (docs/spec/05 content-addressed only);
- pre-publish QA flags a SUPERSEDED rule and INCOMPLETE uz individually;
- report resolve/reject records the resolver id; report queue is admin-only (no user read).

All tests are network-free (in-memory fake MediaStorage; no real S3).
"""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

from tests.admin_helper import (
    build_admins,
    dev_login,
    make_rule,
    new_client,
    onboard,
    question_id_for_version,
    valid_question_payload,
)


# --------------------------------------------------------------------------- #
# 1. Mass-assignment: admin_role in a request body must be ignored.
# --------------------------------------------------------------------------- #
def test_admin_role_in_profile_body_is_ignored(client):
    """A non-admin sends admin_role/is_correct in the profile body -> ignored;
    the user stays a non-admin and is 403 on admin endpoints."""
    c = new_client(client)
    u = dev_login(c, 1001, "Student")  # not in ADMIN_TELEGRAM_IDS
    # Smuggle privilege fields in the body.
    r = c.put(
        "/api/profile",
        json={
            "display_name": "X",
            "category": "B",
            "language": "uz",
            "admin_role": "superadmin",
            "is_correct": True,
            "role": "admin",
        },
    )
    assert r.status_code == 200, r.text
    # Still blocked from admin scope.
    assert c.get("/api/admin/overview").status_code == 403

    # And the persisted user row never received an admin_role.
    from app.domain.models import User
    from app.storage.db import session_scope

    with session_scope() as db:
        row = db.get(User, u["id"])
        assert row.admin_role is None


def test_author_cannot_escalate_own_role_via_body(client):
    """Even an authenticated content_author cannot lift their role by smuggling
    admin_role through the profile body."""
    roles = build_admins(client)
    author = roles["author"]
    author.put(
        "/api/profile",
        json={"display_name": "A", "category": "B", "language": "uz", "admin_role": "superadmin"},
    )
    # Author still cannot hit an admin-only (rule create) endpoint.
    assert author.post("/api/admin/rules", json={"code": "YHQ:6.6", "text": "x"}).status_code == 403
    # Role-assignment endpoint (superadmin) still forbidden.
    me = author.get("/api/auth/me").json()["user"]
    assert author.post(f"/api/admin/users/{me['id']}/role", json={"role": "superadmin"}).status_code == 403


# --------------------------------------------------------------------------- #
# 2. GIF frame-bomb rejection.
# --------------------------------------------------------------------------- #
def _multiframe_gif(frames: int, size=(16, 16)) -> bytes:
    # Each frame has genuinely distinct pixels so Pillow does not dedupe them to 1.
    imgs = []
    for i in range(frames):
        im = Image.new("RGB", size, (0, 0, 0))
        d = ImageDraw.Draw(im)
        x = i % size[0]
        d.rectangle([x, 0, x + 2, size[1]], fill=(255, (i * 20) % 256, (i * 7) % 256))
        imgs.append(im.convert("P"))
    buf = io.BytesIO()
    imgs[0].save(buf, format="GIF", save_all=True, append_images=imgs[1:], duration=10, loop=0, disposal=2)
    return buf.getvalue()


def test_upload_rejects_gif_frame_bomb(client, monkeypatch):
    roles = build_admins(client)
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_gif_frames", 3)
    data = _multiframe_gif(frames=12)
    # Sanity: it really is a multi-frame GIF.
    probe = Image.open(io.BytesIO(data))
    assert getattr(probe, "n_frames", 1) > 3
    r = roles["author"].post("/api/admin/media", files={"file": ("anim.gif", data, "image/gif")})
    assert r.status_code == 400, r.text
    assert "kadr" in r.json()["detail"].lower() or "frame" in r.json()["detail"].lower()


def test_upload_accepts_small_gif(client):
    roles = build_admins(client)
    data = _multiframe_gif(frames=2)
    r = roles["author"].post("/api/admin/media", files={"file": ("ok.gif", data, "image/gif")})
    assert r.status_code == 201, r.text
    assert r.json()["media_type"] == "gif"
    assert r.json()["content_type"] == "image/gif"


# --------------------------------------------------------------------------- #
# 3. No bytes in Postgres — QuestionMedia is metadata-only (structural).
# --------------------------------------------------------------------------- #
def test_question_media_stores_no_binary_bytes():
    from sqlalchemy import LargeBinary
    from sqlalchemy.dialects.postgresql import BYTEA

    from app.domain.models import QuestionMedia

    for col in QuestionMedia.__table__.columns:
        assert not isinstance(col.type, (LargeBinary, BYTEA)), (
            f"QuestionMedia.{col.name} is a binary column — bytes must live in object storage, not Postgres"
        )
    # The expected metadata columns exist (hash + server key), payload columns do not.
    names = set(QuestionMedia.__table__.columns.keys())
    assert {"content_hash", "storage_key", "byte_size"} <= names
    assert not (names & {"data", "bytes", "blob", "content", "payload"})


# --------------------------------------------------------------------------- #
# 4. There is NO /api/questions/{id}/media route (content-addressed only).
# --------------------------------------------------------------------------- #
def test_no_question_media_route_exists(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    r = roles["author"].post("/api/admin/questions", json=valid_question_payload(rule["code"]))
    qid = question_id_for_version(r.json()["id"])
    # Such a route was explicitly rejected by the spec; it must not resolve.
    assert roles["admin"].get(f"/api/questions/{qid}/media").status_code == 404

    # And no mounted route path matches the forbidden pattern.
    paths = {getattr(rt, "path", "") for rt in client.app.router.routes}
    assert not any("/media" in p and "/questions/" in p for p in paths), paths


# --------------------------------------------------------------------------- #
# 5. Pre-publish QA flags a SUPERSEDED rule and INCOMPLETE uz individually.
# --------------------------------------------------------------------------- #
def _publish(roles, rule_code, prompt="QA savol?"):
    r = roles["author"].post("/api/admin/questions", json=valid_question_payload(rule_code, prompt))
    vid = r.json()["id"]
    roles["author"].post(f"/api/admin/versions/{vid}/submit-review")
    roles["reviewer"].post(f"/api/admin/versions/{vid}/review")
    assert roles["reviewer"].post(f"/api/admin/versions/{vid}/publish").status_code == 200
    return vid


def test_qa_flags_superseded_rule(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:8.8", text="Amaldagi qoida")
    vid = _publish(roles, rule["code"])
    qid = question_id_for_version(vid)

    # Before supersede: current_rule_linked passes.
    qa_before = roles["reviewer"].get(f"/api/admin/questions/{qid}/qa").json()
    before = {c["key"]: c["passed"] for c in qa_before["checklist"]}
    assert before["current_rule_linked"] is True

    # Supersede the rule -> the linked (snapshot older) version is now stale.
    assert roles["admin"].post(
        f"/api/admin/rules/{rule['id']}/supersede", json={"new_status": "superseded"}
    ).status_code == 200

    qa_after = roles["reviewer"].get(f"/api/admin/questions/{qid}/qa").json()
    after = {c["key"]: c["passed"] for c in qa_after["checklist"]}
    assert after["current_rule_linked"] is False
    assert qa_after["all_passed"] is False


def test_qa_flags_incomplete_uz(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:9.9", text="Qoida")
    # Valid EXCEPT the uz prompt is empty -> uz_translation_complete must fail while
    # exactly_one_correct / explanation_per_option still pass (isolates the uz flag).
    payload = valid_question_payload(rule["code"], prompt="")
    r = roles["author"].post("/api/admin/questions", json=payload)
    qid = question_id_for_version(r.json()["id"])

    qa = roles["reviewer"].get(f"/api/admin/questions/{qid}/qa").json()
    checks = {c["key"]: c["passed"] for c in qa["checklist"]}
    assert checks["uz_translation_complete"] is False
    assert checks["exactly_one_correct"] is True
    assert checks["explanation_per_option"] is True
    assert qa["all_passed"] is False


def test_publish_blocked_when_uz_prompt_empty(client):
    """The publish gate (not just the display checklist) rejects incomplete uz."""
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:9.1", text="Qoida")
    r = roles["author"].post("/api/admin/questions", json=valid_question_payload(rule["code"], prompt=""))
    vid = r.json()["id"]
    roles["author"].post(f"/api/admin/versions/{vid}/submit-review")
    roles["reviewer"].post(f"/api/admin/versions/{vid}/review")
    resp = roles["reviewer"].post(f"/api/admin/versions/{vid}/publish")
    assert resp.status_code == 422
    assert any("Savol matni" in e for e in resp.json()["detail"]["errors"])


# --------------------------------------------------------------------------- #
# 6. Report resolve/reject records the resolver; queue is admin-only (no user read).
# --------------------------------------------------------------------------- #
def _seed_and_report(client, roles, reason="wrong_answer"):
    from tests.seed_helper import seed_demo_bank

    # seed_demo_bank is idempotent-friendly per test DB; call once per test.
    seed_demo_bank()
    from app.domain.models import QuestionVersion
    from app.storage.db import session_scope

    with session_scope() as db:
        vid = db.query(QuestionVersion).first().id

    student = new_client(client)
    dev_login(student, 1001, "Student")
    onboard(student)
    rr = student.post("/api/reports", json={"question_version_id": vid, "reason": reason, "note": "x"})
    assert rr.status_code == 201, rr.text
    return vid, rr.json()["id"], student


def test_report_resolve_records_resolver(client):
    roles = build_admins(client)
    vid, report_id, _ = _seed_and_report(client, roles)
    reviewer_id = roles["reviewer"].get("/api/auth/me").json()["user"]["id"]

    resp = roles["reviewer"].post(
        f"/api/admin/reports/{report_id}/resolve", json={"action": "resolve", "note": "Tuzatildi"}
    )
    assert resp.status_code == 200

    from app.domain.models import ContentReport
    from app.storage.db import session_scope

    with session_scope() as db:
        rep = db.get(ContentReport, report_id)
        assert rep.status.value == "resolved"
        assert rep.resolved_by_user_id == reviewer_id
        assert rep.resolved_at is not None
        assert rep.question_version_id == vid  # exact version captured


def test_report_reject_records_resolver(client):
    roles = build_admins(client)
    _, report_id, _ = _seed_and_report(client, roles, reason="typo")
    reviewer_id = roles["reviewer"].get("/api/auth/me").json()["user"]["id"]

    resp = roles["reviewer"].post(
        f"/api/admin/reports/{report_id}/resolve", json={"action": "reject", "note": "Asossiz"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    from app.domain.models import ContentReport
    from app.storage.db import session_scope

    with session_scope() as db:
        rep = db.get(ContentReport, report_id)
        assert rep.resolved_by_user_id == reviewer_id
        assert rep.resolved_at is not None


def test_report_queue_is_admin_only_and_no_user_read_route(client):
    roles = build_admins(client)
    _, report_id, student = _seed_and_report(client, roles)

    # Non-admin (the reporter) cannot read the admin queue.
    assert student.get("/api/admin/reports").status_code == 403
    # There is no user-facing report-read endpoint (IDOR surface absent by design):
    # neither the collection nor an item id is exposed to ordinary users.
    assert student.get("/api/reports").status_code in (404, 405)
    assert student.get(f"/api/reports/{report_id}").status_code in (403, 404, 405)
