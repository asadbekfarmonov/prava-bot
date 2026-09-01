"""Media pipeline: upload validation (SVG/wrong-type/oversize/decompression bomb),
server-generated storage key, content-addressed serving, draft-vs-published visibility."""

from __future__ import annotations

import io

from PIL import Image

from tests.admin_helper import build_admins, new_client


def _png_bytes(w: int = 24, h: int = 24, color=(200, 30, 30)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _upload(c, data: bytes, filename: str, content_type: str):
    return c.post("/api/admin/media", files={"file": (filename, data, content_type)})


def test_upload_png_reencoded_to_webp_with_server_generated_key(client):
    roles = build_admins(client)
    r = _upload(roles["author"], _png_bytes(), "evil-name.png", "image/png")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["content_type"] == "image/webp"  # re-encoded
    assert body["media_type"] == "image"
    assert body["url"] == f"/api/media/{body['id']}/{body['content_hash']}"

    # storage_key is server-generated random (NOT the client filename).
    from app.domain.models import QuestionMedia
    from app.storage.db import session_scope

    with session_scope() as db:
        media = db.get(QuestionMedia, body["id"])
        assert media.storage_key.startswith("media/")
        assert "evil-name" not in media.storage_key
        assert media.storage_key.endswith(".webp")


def test_upload_rejects_svg(client):
    roles = build_admins(client)
    svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    r = _upload(roles["author"], svg, "pic.png", "image/png")  # lies about type
    assert r.status_code == 400
    assert "SVG" in r.json()["detail"]


def test_upload_rejects_wrong_sniffed_type(client):
    roles = build_admins(client)
    r = _upload(roles["author"], b"this is definitely not an image", "pic.png", "image/png")
    assert r.status_code == 400


def test_upload_rejects_oversize(client, monkeypatch):
    roles = build_admins(client)
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_image_bytes", 10)  # tiny cap
    r = _upload(roles["author"], _png_bytes(), "pic.png", "image/png")
    assert r.status_code == 400


def test_upload_rejects_decompression_bomb(client, monkeypatch):
    roles = build_admins(client)
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_image_pixels", 100)  # 10x10 max
    r = _upload(roles["author"], _png_bytes(50, 50), "pic.png", "image/png")
    assert r.status_code == 400


def test_upload_requires_admin(client):
    from tests.admin_helper import dev_login, onboard

    c = new_client(client)
    dev_login(c, 1001, "Student")
    onboard(c)
    r = _upload(c, _png_bytes(), "pic.png", "image/png")
    assert r.status_code == 403


def test_draft_media_is_admin_only_and_content_addressed(client):
    roles = build_admins(client)
    up = _upload(roles["author"], _png_bytes(), "pic.png", "image/png").json()
    media_id, content_hash = up["id"], up["content_hash"]

    # Draft (not linked to a published question): anonymous -> 404.
    anon = new_client(client)
    assert anon.get(f"/api/media/{media_id}/{content_hash}").status_code == 404
    # Admin can fetch draft media (private cache).
    admin_fetch = roles["author"].get(f"/api/media/{media_id}/{content_hash}")
    assert admin_fetch.status_code == 200
    assert admin_fetch.headers["Cache-Control"] == "private, no-store"
    # Wrong hash -> 404 (content-addressed, no existence leak).
    assert roles["author"].get(f"/api/media/{media_id}/deadbeef").status_code == 404


def test_published_media_is_public_and_immutably_cacheable(client):
    from tests.admin_helper import make_rule, valid_question_payload

    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    up = _upload(roles["author"], _png_bytes(32, 32, (10, 180, 10)), "pic.png", "image/png").json()
    media_id, content_hash = up["id"], up["content_hash"]

    payload = valid_question_payload(rule["code"])
    payload["media_id"] = media_id
    r = roles["author"].post("/api/admin/questions", json=payload)
    vid = r.json()["id"]
    roles["author"].post(f"/api/admin/versions/{vid}/submit-review")
    roles["reviewer"].post(f"/api/admin/versions/{vid}/review")
    assert roles["reviewer"].post(f"/api/admin/versions/{vid}/publish").status_code == 200

    anon = new_client(client)
    resp = anon.get(f"/api/media/{media_id}/{content_hash}")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert resp.headers["content-type"].startswith("image/webp")
