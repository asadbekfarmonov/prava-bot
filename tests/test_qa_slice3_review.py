"""QA review (adversarial, network-free) — closes thin spots in the Slice-3 matrix:

1. Media type is decided from BYTES, never the client Content-Type/filename
   (docs/spec/09 media-upload-security): a real PNG uploaded as text/plain with a
   ".txt" name must still ingest as image/webp.
2. Rule search returns the full picker field set (docs/spec/08 rule picker: code,
   text, effective version, source, verification date).
3. current_version_id repoints ONLY on publish, never on edit (docs/spec/02
   immutability): editing a published question forks a draft but leaves the
   container pointed at the old published version until the new one is published.
4. Media upload endpoint is part of the admin authz surface (non-admin -> 403).

All tests use the in-memory fake MediaStorage (conftest resets it); no real S3.
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
    question_id_for_version,
    valid_question_payload,
)


def _png_bytes(w: int = 20, h: int = 20, color=(12, 90, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


# 1. Byte-sniffing wins over a lying client Content-Type + extension. ------------
def test_media_type_sniffed_from_bytes_not_client_headers(client):
    roles = build_admins(client)
    png = _png_bytes()
    # Lie hard: extension .txt and Content-Type text/plain, but the bytes are a PNG.
    r = roles["author"].post(
        "/api/admin/media",
        files={"file": ("totally-a-note.txt", png, "text/plain")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # Decision came from the magic bytes, not the client-declared type/extension.
    assert body["media_type"] == "image"
    assert body["content_type"] == "image/webp"  # png -> re-encoded

    from app.domain.models import QuestionMedia
    from app.storage.db import session_scope

    with session_scope() as db:
        media = db.get(QuestionMedia, body["id"])
        assert media.storage_key.endswith(".webp")  # not ".txt"
        assert "note" not in media.storage_key  # filename never used for the key


# 2. Rule search returns the full expected picker field set. ---------------------
def test_rule_search_returns_expected_picker_fields(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code="YHQ:13.9", text="Chorrahada bosh yo'l imtiyozi")
    rows = roles["author"].get("/api/admin/rules", params={"q": "13.9"}).json()["rules"]
    assert rows, "search returned no rows"
    row = next(r for r in rows if r["code"] == "YHQ:13.9")
    # Picker needs: code, current text, effective version, source, verification date, status.
    for field in ("id", "code", "title", "text", "version", "source_url", "source_document", "status", "verified_at"):
        assert field in row, f"rule search missing field: {field}"
    assert row["text"] == "Chorrahada bosh yo'l imtiyozi"
    assert row["version"] == 1
    assert row["status"] == "active"


# 3. save=live: editing forks a new version AND repoints on save; the prior
#    published version is superseded and remains immutable (version pinning). --------
def _publish(roles, rule_code, prompt):
    r = roles["author"].post("/api/admin/questions", json=valid_question_payload(rule_code, prompt))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "published"
    return r.json()["id"]


def test_edit_forks_new_version_and_repoints_live(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:3.3", text="Qoida")
    v1 = _publish(roles, rule["code"], prompt="V1 MATN")
    qid = question_id_for_version(v1)

    from app.domain.models import Question, QuestionVersion
    from app.storage.db import session_scope

    with session_scope() as db:
        assert db.get(Question, qid).current_version_id == v1

    # Edit the published question -> forks a NEW version and publishes it live.
    r = roles["author"].put(
        f"/api/admin/questions/{qid}", json=valid_question_payload(rule["code"], prompt="V2 MATN")
    )
    assert r.status_code == 200, r.text
    v2 = r.json()["id"]
    assert v2 != v1
    assert r.json()["status"] == "published"

    # save=live: the container repoints to v2 immediately; v1 is superseded but the
    # original row stays immutable (retained for historical attempts / version pinning).
    with session_scope() as db:
        assert db.get(Question, qid).current_version_id == v2
        assert db.get(QuestionVersion, v1).status.value == "superseded"


# 4. Media upload endpoint is part of the admin authz surface. -------------------
def test_media_upload_requires_admin_role(client):
    c = new_client(client)
    dev_login(c, 1001, "Student")  # not in ADMIN_TELEGRAM_IDS
    onboard(c)
    r = c.post("/api/admin/media", files={"file": ("x.png", _png_bytes(), "image/png")})
    assert r.status_code == 403
    # And unauthenticated -> 401.
    anon = new_client(client)
    assert anon.post("/api/admin/media", files={"file": ("x.png", _png_bytes(), "image/png")}).status_code == 401
