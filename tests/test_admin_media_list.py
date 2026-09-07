"""Admin media library listing (GET /api/admin/media).

Covers: auth gate (401 unauth / 403 non-admin), newest-first listing, media_type filter
(+ bad value -> 400), q filter on alt_text/content_type, the bulk in_use flag (true for a
published question's base image AND its outcome clip, false for an orphan upload), and the
pagination limit/offset with the server-max clamp (>100 clamped)."""

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


def _png(color=(200, 30, 30), w=24, h=24) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(c, color=(200, 30, 30), name="pic.png", alt=None) -> dict:
    data = {"alt_text": alt} if alt is not None else None
    r = c.post("/api/admin/media", files={"file": (name, _png(color), "image/png")}, data=data)
    assert r.status_code == 201, r.text
    return r.json()


def _student(client, tid=1001):
    c = new_client(client)
    dev_login(c, tid, "Student")
    onboard(c)
    return c


# --------------------------------------------------------------------------- #
# Auth gate
# --------------------------------------------------------------------------- #
def test_list_requires_auth_401_when_anonymous(client):
    anon = new_client(client)
    assert anon.get("/api/admin/media").status_code == 401


def test_list_forbidden_403_for_non_admin_user(client):
    c = _student(client)
    assert c.get("/api/admin/media").status_code == 403


# --------------------------------------------------------------------------- #
# Listing / ordering
# --------------------------------------------------------------------------- #
def test_lists_uploaded_media_newest_first(client):
    roles = build_admins(client)
    first = _upload(roles["author"], (10, 10, 200), "first.png")
    second = _upload(roles["author"], (10, 200, 10), "second.png")
    third = _upload(roles["author"], (200, 10, 10), "third.png")

    # Force distinct created_at (SQLite CURRENT_TIMESTAMP is second-resolution, so rapid
    # uploads would otherwise tie) to assert the created_at DESC ordering deterministically.
    from datetime import datetime, timedelta, timezone

    from app.domain.models import QuestionMedia
    from app.storage.db import session_scope

    base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with session_scope() as db:
        for offset_min, up in ((0, first), (1, second), (2, third)):
            m = db.get(QuestionMedia, up["id"])
            m.created_at = base_ts + timedelta(minutes=offset_min)

    body = roles["author"].get("/api/admin/media").json()
    assert body["total"] == 3
    assert body["limit"] == 50
    assert body["offset"] == 0
    ids = [it["id"] for it in body["items"]]
    # newest first (created_at desc): third, second, first
    assert ids == [third["id"], second["id"], first["id"]]
    item = body["items"][0]
    assert item["url"] == f"/api/media/{third['id']}/{third['content_hash']}"
    assert item["media_type"] == "image"
    assert item["content_type"] == "image/webp"
    assert item["in_use"] is False
    assert set(item) >= {
        "id", "media_type", "content_type", "content_hash", "url", "alt",
        "width", "height", "duration_ms", "byte_size", "in_use", "created_at",
    }


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
def test_media_type_filter_and_bad_value(client):
    roles = build_admins(client)
    _upload(roles["author"], (1, 2, 3), "a.png")
    _upload(roles["author"], (4, 5, 6), "b.png")

    only_images = roles["author"].get("/api/admin/media?media_type=image").json()
    assert only_images["total"] == 2
    assert all(it["media_type"] == "image" for it in only_images["items"])

    none_videos = roles["author"].get("/api/admin/media?media_type=video").json()
    assert none_videos["total"] == 0
    assert none_videos["items"] == []

    bad = roles["author"].get("/api/admin/media?media_type=bogus")
    assert bad.status_code == 400


def test_q_filter_matches_alt_and_content_type(client):
    roles = build_admins(client)
    tagged = _upload(roles["author"], (9, 9, 9), "tagged.png", alt="Chorraha belgisi")
    _upload(roles["author"], (7, 7, 7), "plain.png")

    # matches uz alt_text (case-insensitive substring)
    by_alt = roles["author"].get("/api/admin/media?q=chorraha").json()
    assert [it["id"] for it in by_alt["items"]] == [tagged["id"]]
    assert by_alt["items"][0]["alt"] == "Chorraha belgisi"

    # matches content_type -> both webp images
    by_ct = roles["author"].get("/api/admin/media?q=webp").json()
    assert by_ct["total"] == 2

    # no match
    assert roles["author"].get("/api/admin/media?q=zzz-nomatch").json()["total"] == 0


# --------------------------------------------------------------------------- #
# in_use (bulk)
# --------------------------------------------------------------------------- #
def test_in_use_true_for_published_base_and_outcome_clip_false_for_orphan(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    base = _upload(roles["author"], (10, 180, 10), "base.png")
    success = _upload(roles["author"], (20, 20, 200), "success.png")
    orphan = _upload(roles["author"], (90, 90, 90), "orphan.png")

    payload = valid_question_payload(rule["code"])
    payload["media_id"] = base["id"]
    payload["success_media_id"] = success["id"]
    r = roles["author"].post("/api/admin/questions", json=payload)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "published"

    body = roles["author"].get("/api/admin/media?limit=100").json()
    flags = {it["id"]: it["in_use"] for it in body["items"]}
    assert flags[base["id"]] is True          # base image on a published question
    assert flags[success["id"]] is True       # outcome clip on a published question
    assert flags[orphan["id"]] is False       # never referenced


# --------------------------------------------------------------------------- #
# Pagination + server-max clamp
# --------------------------------------------------------------------------- #
def test_pagination_limit_offset(client):
    roles = build_admins(client)
    for i in range(5):
        _upload(roles["author"], (i * 20 % 255, 30, 60), f"p{i}.png")

    # Canonical order is whatever the server returns for the full page (created_at desc,
    # id desc as a stable tiebreaker for uploads sharing the same second).
    full = roles["author"].get("/api/admin/media?limit=100").json()
    order = [it["id"] for it in full["items"]]
    assert len(order) == 5

    page1 = roles["author"].get("/api/admin/media?limit=2&offset=0").json()
    assert page1["total"] == 5
    assert page1["limit"] == 2
    assert [it["id"] for it in page1["items"]] == order[0:2]

    page2 = roles["author"].get("/api/admin/media?limit=2&offset=2").json()
    assert page2["offset"] == 2
    assert [it["id"] for it in page2["items"]] == order[2:4]


def test_server_max_limit_clamp(client):
    """The service clamps limit to the [1, 100] server max (defense-in-depth)."""
    from app.services import media as media_service
    from app.storage.db import session_scope

    roles = build_admins(client)
    _upload(roles["author"], (5, 5, 5), "one.png")

    with session_scope() as db:
        clamped_high = media_service.list_media(db, limit=500)
        assert clamped_high["limit"] == 100  # >100 clamped down to server max
        clamped_low = media_service.list_media(db, limit=0)
        assert clamped_low["limit"] == 1     # <1 clamped up to 1
        neg_offset = media_service.list_media(db, offset=-10)
        assert neg_offset["offset"] == 0     # negative offset clamped to 0
