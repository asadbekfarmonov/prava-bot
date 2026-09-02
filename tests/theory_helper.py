"""Helpers for Theory / catalogue tests: build published theory content via the admin
API (exercising role-gating) over one app/DB, plus a student client."""

from __future__ import annotations

import io

from PIL import Image
from fastapi.testclient import TestClient

from tests.admin_helper import (
    build_admins,
    dev_login,
    make_rule,
    new_client,
    onboard,
    question_id_for_version,
    valid_question_payload,
)


def png_bytes(w: int = 24, h: int = 24, color=(30, 120, 200)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def student_client(client, telegram_id: int = 1001, name: str = "Dilnoza") -> TestClient:
    c = new_client(client)
    dev_login(c, telegram_id, name)
    onboard(c)
    return c


def publish_question(roles, rule_code: str, prompt: str = "Belgi savoli?", is_sign=True):
    """Author->review->publish a valid question; return (version_id, question_id)."""
    payload = valid_question_payload(rule_code, prompt)
    payload["is_sign_question"] = is_sign
    payload["topic"] = "road_signs"
    r = roles["author"].post("/api/admin/questions", json=payload)
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    assert roles["author"].post(f"/api/admin/versions/{vid}/submit-review").status_code == 200
    assert roles["reviewer"].post(f"/api/admin/versions/{vid}/review").status_code == 200
    assert roles["reviewer"].post(f"/api/admin/versions/{vid}/publish").status_code == 200
    return vid, question_id_for_version(vid)


def _publish_article(roles, version_id: str):
    a = roles["author"]
    r = roles["reviewer"]
    assert a.post(f"/api/admin/theory/article-versions/{version_id}/submit-review").status_code == 200
    assert r.post(f"/api/admin/theory/article-versions/{version_id}/review").status_code == 200
    assert r.post(f"/api/admin/theory/article-versions/{version_id}/publish").status_code == 200


def _publish_sign(roles, version_id: str):
    a = roles["author"]
    r = roles["reviewer"]
    assert a.post(f"/api/admin/theory/sign-versions/{version_id}/submit-review").status_code == 200
    assert r.post(f"/api/admin/theory/sign-versions/{version_id}/review").status_code == 200
    assert r.post(f"/api/admin/theory/sign-versions/{version_id}/publish").status_code == 200


def create_section(roles, slug="belgilar", title="Yo'l belgilari", topic="road_signs"):
    r = roles["author"].post(
        "/api/admin/theory/sections",
        json={"slug": slug, "title": title, "subtitle": "Bo'lim", "topic": topic, "position": 1},
    )
    assert r.status_code == 201, r.text
    section_id = r.json()["id"]
    assert roles["reviewer"].post(f"/api/admin/theory/sections/{section_id}/publish").status_code == 200
    return section_id


def create_article(roles, section_id, *, slug="kirish", rule_code=None, question_ids=None,
                   blocks=None, title="Belgilarga kirish"):
    r = roles["author"].post(
        "/api/admin/theory/articles",
        json={"section_id": section_id, "slug": slug, "kind": "lesson", "position": 1},
    )
    assert r.status_code == 201, r.text
    version_id = r.json()["id"]
    article_id = r.json()["article_id"]
    if blocks is None:
        blocks = [{"type": "text", "body": "Namuna matn."}]
        if rule_code:
            blocks.append({"type": "rule_callout", "body": "Qoida", "rule_code": rule_code})
    payload = {
        "title": title, "summary": "Xulosa", "ai_assisted": True, "blocks": blocks,
        "rule_codes": [rule_code] if rule_code else [],
        "question_ids": question_ids or [],
    }
    e = roles["author"].put(f"/api/admin/theory/articles/{article_id}", json=payload)
    assert e.status_code == 200, e.text
    version_id = e.json()["id"]
    _publish_article(roles, version_id)
    return {"article_id": article_id, "version_id": version_id, "slug": slug}


def create_sign(roles, *, code="DEMO-W1", family="warning", rule_code=None, question_ids=None,
                name="Ogohlantiruvchi belgi", media_id=None):
    r = roles["author"].post(
        "/api/admin/theory/signs",
        json={"official_code": code, "family": family, "media_id": media_id, "position": 1},
    )
    assert r.status_code == 201, r.text
    sign_id = r.json()["road_sign_id"]
    payload = {
        "name": name, "meaning": "Ma'no", "driver_action": "Harakat",
        "keywords": "stop parking piyoda", "ai_assisted": True,
        "rule_codes": [rule_code] if rule_code else [],
        "question_ids": question_ids or [], "media_id": media_id,
    }
    e = roles["author"].put(f"/api/admin/theory/signs/{sign_id}", json=payload)
    assert e.status_code == 200, e.text
    version_id = e.json()["id"]
    _publish_sign(roles, version_id)
    return {"sign_id": sign_id, "version_id": version_id, "code": code}
