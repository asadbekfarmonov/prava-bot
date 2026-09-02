"""Theory / YHQ Handbook + catalogue tests (docs/spec/14, 15). Network-free (in-memory
MediaStorage fake). Covers navigation, catalogue filtering, global search, rule links,
Theory<->Practice (no answer leak), progress (viewed vs mastered), favorites (IDOR),
admin author/review/publish + immutable versioning, rule-supersede propagation,
non-admin 403, stored-XSS inertness, content-addressed media, multilingual-ready schema.
"""

from __future__ import annotations

from tests.admin_helper import build_admins, make_rule, new_client, dev_login, onboard
from tests.theory_helper import (
    create_article,
    create_section,
    create_sign,
    png_bytes,
    publish_question,
    student_client,
)


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #
def test_navigation_sections_section_article(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    section_id = create_section(roles)
    art = create_article(roles, section_id, rule_code=rule["code"])

    c = student_client(client)
    sections = c.get("/api/theory/sections").json()["sections"]
    assert any(s["slug"] == "belgilar" for s in sections)

    section = c.get("/api/theory/sections/belgilar").json()
    assert section["article_count"] == 1
    assert any(a["slug"] == "kirish" for a in section["articles"])

    article = c.get(f"/api/theory/articles/{art['slug']}").json()
    assert article["title"] == "Belgilarga kirish"
    assert len(article["blocks"]) >= 1
    # rule callout resolves the linked rule
    assert any(b["type"] == "rule_callout" and b.get("rule") for b in article["blocks"])
    assert article["rules"] and article["rules"][0]["code"] == rule["code"]


def test_draft_content_not_visible_to_students(client):
    roles = build_admins(client)
    # Create a section but do NOT publish it.
    r = roles["author"].post(
        "/api/admin/theory/sections",
        json={"slug": "yashirin", "title": "Yashirin", "position": 9},
    )
    assert r.status_code == 201
    c = student_client(client)
    assert c.get("/api/theory/sections/yashirin").status_code == 404
    assert all(s["slug"] != "yashirin" for s in c.get("/api/theory/sections").json()["sections"])


# --------------------------------------------------------------------------- #
# Sign catalogue + family filtering
# --------------------------------------------------------------------------- #
def test_sign_catalogue_family_filter(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    create_sign(roles, code="DEMO-W1", family="warning", rule_code=rule["code"])
    create_sign(roles, code="DEMO-P1", family="prohibitory", rule_code=rule["code"])

    c = student_client(client)
    all_signs = c.get("/api/theory/signs").json()["signs"]
    assert len(all_signs) == 2
    warn = c.get("/api/theory/signs?family=warning").json()["signs"]
    assert len(warn) == 1 and warn[0]["code"] == "DEMO-W1"

    detail = c.get("/api/theory/signs/DEMO-P1").json()
    assert detail["family"] == "prohibitory"
    assert detail["rules"][0]["code"] == rule["code"]


def test_markings_gestures_lights_list_detail(client):
    roles = build_admins(client)
    a, r = roles["author"], roles["reviewer"]
    # marking
    mv = a.post("/api/admin/theory/markings", json={"group": "horizontal", "code": "1.1"}).json()
    a.put(f"/api/admin/theory/markings/{mv['road_marking_id']}",
          json={"name": "Uzluksiz chiziq", "meaning": "M", "keywords": "chiziq"})
    ver = a.put(f"/api/admin/theory/markings/{mv['road_marking_id']}",
                json={"name": "Uzluksiz chiziq", "meaning": "M"}).json()["id"]
    a.post(f"/api/admin/theory/marking-versions/{ver}/submit-review")
    r.post(f"/api/admin/theory/marking-versions/{ver}/review")
    r.post(f"/api/admin/theory/marking-versions/{ver}/publish")
    # gesture
    gv = a.post("/api/admin/theory/gestures", json={"code": "G1"}).json()
    gver = a.put(f"/api/admin/theory/gestures/{gv['gesture_id']}",
                 json={"name": "Ishora", "position_desc": "P", "allowed": "A", "forbidden": "F"}).json()["id"]
    a.post(f"/api/admin/theory/gesture-versions/{gver}/submit-review")
    r.post(f"/api/admin/theory/gesture-versions/{gver}/review")
    r.post(f"/api/admin/theory/gesture-versions/{gver}/publish")
    # light
    lv = a.post("/api/admin/theory/lights", json={"kind": "main"}).json()
    lver = a.put(f"/api/admin/theory/lights/{lv['light_id']}",
                 json={"title": "Qizil", "meaning": "To'xta", "movement_permitted": "Yo'q"}).json()["id"]
    a.post(f"/api/admin/theory/light-versions/{lver}/submit-review")
    r.post(f"/api/admin/theory/light-versions/{lver}/review")
    r.post(f"/api/admin/theory/light-versions/{lver}/publish")

    c = student_client(client)
    markings = c.get("/api/theory/markings").json()["markings"]
    assert len(markings) == 1
    assert c.get(f"/api/theory/markings/{markings[0]['id']}").json()["name"] == "Uzluksiz chiziq"
    gestures = c.get("/api/theory/gestures").json()["gestures"]
    assert len(gestures) == 1
    assert c.get(f"/api/theory/gestures/{gestures[0]['id']}").json()["allowed"] == "A"
    lights = c.get("/api/theory/lights").json()["lights"]
    assert len(lights) == 1
    assert c.get(f"/api/theory/lights/{lights[0]['id']}").json()["meaning"] == "To'xta"


# --------------------------------------------------------------------------- #
# Global search (mixed content)
# --------------------------------------------------------------------------- #
def test_global_search_returns_mixed_content(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:6.13", text="Stop chizig'i oldida to'xtang")
    section_id = create_section(roles, slug="toxtash", title="Stop va to'xtash", topic="stopping_parking")
    create_article(roles, section_id, slug="stop-line", title="Stop chizig'i", rule_code=rule["code"])
    create_sign(roles, code="DEMO-STOP", family="prohibitory", name="Stop belgisi", rule_code=rule["code"])

    c = student_client(client)
    results = c.get("/api/theory/search?q=stop").json()["results"]
    types = {r["type"] for r in results}
    # Mixed: at least an article/section and a sign and a rule surface for 'stop'.
    assert "sign" in types
    assert "rule" in types
    assert ("article" in types) or ("section" in types)


# --------------------------------------------------------------------------- #
# Theory -> Practice (NO answer leak) + Practice -> Theory by-rule
# --------------------------------------------------------------------------- #
def test_theory_to_practice_no_answer_leak(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    _, qid = publish_question(roles, rule["code"])
    section_id = create_section(roles)
    art = create_article(roles, section_id, rule_code=rule["code"], question_ids=[qid])

    c = student_client(client)
    start = c.post("/api/theory/practice/start",
                   json={"target_type": "article", "target_id": art["article_id"]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["questions_total"] == 1
    q = body["questions"][0]
    # NO answer leak: options carry no correctness / explanation / rule.
    assert q["options"], q
    for opt in q["options"]:
        assert "is_correct" not in opt
        assert "explanation" not in opt
    assert "rule" not in q
    assert "short_explanation" not in q


def test_practice_to_theory_by_rule(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:13.9")
    section_id = create_section(roles)
    art = create_article(roles, section_id, slug="ustunlik", rule_code=rule["code"])
    create_sign(roles, code="DEMO-PR", family="priority", rule_code=rule["code"])

    c = student_client(client)
    res = c.get(f"/api/theory/by-rule/{rule['code']}").json()
    assert res["rule"]["code"] == rule["code"]
    assert any(a["id"] == art["article_id"] for a in res["articles"])
    assert len(res["signs"]) == 1


# --------------------------------------------------------------------------- #
# Progress: viewed vs mastered (mastery needs question performance, not views)
# --------------------------------------------------------------------------- #
def test_progress_viewed_is_not_mastery(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    _, qid = publish_question(roles, rule["code"])
    section_id = create_section(roles)
    art = create_article(roles, section_id, rule_code=rule["code"], question_ids=[qid])

    c = student_client(client)
    # Opening the article marks 'viewed' — NEVER mastery.
    article = c.get(f"/api/theory/articles/{art['slug']}").json()
    assert article["progress_state"] == "viewed"

    # Client cannot self-declare mastery: POST progress only marks viewed.
    prog = c.post("/api/theory/progress",
                  json={"target_type": "article", "target_id": art["article_id"],
                        "state": "mastered"}).json()
    assert prog["state"] == "viewed"


def test_progress_mastered_derived_from_performance(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    _, qid = publish_question(roles, rule["code"])
    section_id = create_section(roles)
    art = create_article(roles, section_id, rule_code=rule["code"], question_ids=[qid])

    c = student_client(client)
    start = c.post("/api/theory/practice/start",
                   json={"target_type": "article", "target_id": art["article_id"]}).json()
    session_id = start["session_id"]

    # Find the correct option by grading one answer, then answer correctly enough times.
    first = c.post("/api/practice/answers",
                   json={"practice_session_id": session_id, "question_id": qid,
                         "selected_option_id": start["questions"][0]["options"][0]["id"]}).json()
    correct_id = first["correct_option_id"]
    for _ in range(5):
        c.post("/api/practice/answers",
               json={"practice_session_id": session_id, "question_id": qid,
                     "selected_option_id": correct_id})

    article = c.get(f"/api/theory/articles/{art['slug']}").json()
    assert article["progress_state"] == "mastered", article["progress_state"]


# --------------------------------------------------------------------------- #
# Favorites: add / list / remove + IDOR-safe
# --------------------------------------------------------------------------- #
def test_favorites_add_list_remove_and_idor(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    create_sign(roles, code="DEMO-W1", family="warning", rule_code=rule["code"])

    alice = student_client(client, 2001, "Alice")
    bob = student_client(client, 2002, "Bob")

    add = alice.post("/api/theory/favorites",
                     json={"target_type": "sign", "target_id": "DEMO-W1"})
    assert add.status_code == 201
    fav_id = add.json()["id"]
    assert len(alice.get("/api/theory/favorites").json()["favorites"]) == 1
    # Bob does not see Alice's favorite.
    assert bob.get("/api/theory/favorites").json()["favorites"] == []
    # IDOR: Bob cannot delete Alice's favorite.
    assert bob.delete(f"/api/theory/favorites/{fav_id}").status_code == 404
    # Alice can.
    assert alice.delete(f"/api/theory/favorites/{fav_id}").status_code == 204
    assert alice.get("/api/theory/favorites").json()["favorites"] == []


# --------------------------------------------------------------------------- #
# Admin workflow + immutable versioning
# --------------------------------------------------------------------------- #
def test_editing_published_article_forks_new_immutable_version(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    section_id = create_section(roles)
    art = create_article(roles, section_id, rule_code=rule["code"])
    old_version_id = art["version_id"]

    # Editing the published article forks a NEW version (old one unchanged).
    e = roles["author"].put(
        f"/api/admin/theory/articles/{art['article_id']}",
        json={"title": "Yangilangan", "summary": "v2", "blocks": [{"type": "text", "body": "v2"}],
              "rule_codes": [rule["code"]], "question_ids": []},
    )
    assert e.status_code == 200
    new_version_id = e.json()["id"]
    assert new_version_id != old_version_id
    assert e.json()["version"] == 2
    assert e.json()["status"] == "draft"

    # Old version row is unchanged (still published) — verified in DB.
    from app.domain.models import TheoryArticleVersion, TheoryArticleTranslation
    from app.storage.db import session_scope
    with session_scope() as db:
        old = db.get(TheoryArticleVersion, old_version_id)
        assert old.status.value == "published"
        tr = db.query(TheoryArticleTranslation).filter_by(article_version_id=old_version_id).first()
        assert tr.title == "Belgilarga kirish"


def test_editing_published_sign_forks_new_immutable_version(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    sign = create_sign(roles, code="DEMO-M1", family="mandatory", rule_code=rule["code"])
    old_version_id = sign["version_id"]

    e = roles["author"].put(
        f"/api/admin/theory/signs/{sign['sign_id']}",
        json={"name": "Yangi nom", "meaning": "v2", "driver_action": "x", "rule_codes": [rule["code"]]},
    )
    assert e.status_code == 200
    assert e.json()["id"] != old_version_id
    assert e.json()["version"] == 2

    from app.domain.models import RoadSignVersion
    from app.storage.db import session_scope
    with session_scope() as db:
        assert db.get(RoadSignVersion, old_version_id).status.value == "published"


# --------------------------------------------------------------------------- #
# Rule supersede -> linked theory/sign versions -> needs_reverification
# --------------------------------------------------------------------------- #
def test_rule_supersede_flips_theory_and_sign_to_needs_reverification(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:10.1")
    section_id = create_section(roles)
    art = create_article(roles, section_id, rule_code=rule["code"])
    sign = create_sign(roles, code="DEMO-RV", family="warning", rule_code=rule["code"])

    resp = roles["admin"].post(f"/api/admin/rules/{rule['id']}/supersede",
                               json={"new_status": "superseded"})
    assert resp.status_code == 200, resp.text
    flipped = resp.json()["flipped_theory"]
    assert art["version_id"] in flipped["articles"]
    assert sign["version_id"] in flipped["signs"]

    from app.domain.models import RoadSignVersion, TheoryArticleVersion
    from app.storage.db import session_scope
    with session_scope() as db:
        assert db.get(TheoryArticleVersion, art["version_id"]).status.value == "needs_reverification"
        assert db.get(RoadSignVersion, sign["version_id"]).status.value == "needs_reverification"

    # It appears in the theory review queue.
    queue = roles["reviewer"].get("/api/admin/theory/review-queue").json()
    assert any(v["version_id"] == art["version_id"] for v in queue["articles"])
    assert any(v["version_id"] == sign["version_id"] for v in queue["signs"])


# --------------------------------------------------------------------------- #
# Non-admin blocked from /api/admin/theory/* (403)
# --------------------------------------------------------------------------- #
def test_non_admin_blocked_from_admin_theory(client):
    c = new_client(client)
    dev_login(c, 5555, "Student")
    onboard(c)
    assert c.post("/api/admin/theory/sections",
                  json={"slug": "x", "title": "x"}).status_code == 403
    assert c.get("/api/admin/theory/review-queue").status_code == 403


# --------------------------------------------------------------------------- #
# Stored-XSS payload renders inert (served as text, not HTML)
# --------------------------------------------------------------------------- #
def test_stored_xss_payload_served_as_inert_text(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    section_id = create_section(roles)
    payload = "<script>alert('xss')</script>"
    art = create_article(
        roles, section_id, slug="xss", title="XSS test", rule_code=rule["code"],
        blocks=[{"type": "text", "body": payload}],
    )
    c = student_client(client)
    article = c.get(f"/api/theory/articles/{art['slug']}").json()
    text_block = next(b for b in article["blocks"] if b["type"] == "text")
    # Returned verbatim as a JSON string (React renders text nodes -> inert). The API
    # never emits HTML; the raw payload is preserved as data, not executed markup.
    assert text_block["body"] == payload


# --------------------------------------------------------------------------- #
# Media access via content-addressed route
# --------------------------------------------------------------------------- #
def test_sign_media_content_addressed(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    up = roles["author"].post(
        "/api/admin/media", files={"file": ("s.png", png_bytes(), "image/png")}
    ).json()
    sign = create_sign(roles, code="DEMO-IMG", family="information", rule_code=rule["code"],
                       media_id=up["id"])

    c = student_client(client)
    detail = c.get(f"/api/theory/signs/{sign['code']}").json()
    assert detail["media_url"] == f"/api/media/{up['id']}/{up['content_hash']}"
    # Published sign media is publicly fetchable + immutably cacheable.
    resp = c.get(detail["media_url"])
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "public, max-age=31536000, immutable"


# --------------------------------------------------------------------------- #
# Multilingual-ready schema (uz now, ru additive)
# --------------------------------------------------------------------------- #
def test_multilingual_ready_ru_additive(client):
    roles = build_admins(client)
    section_id = create_section(roles, slug="ml", title="Belgilar")
    # Adding a ru translation is additive against the SAME base row (no core migration).
    r = roles["author"].put(
        f"/api/admin/theory/sections/{section_id}/translation",
        json={"language": "ru", "title": "Знаки", "subtitle": "раздел"},
    )
    assert r.status_code == 200
    from app.domain.models import TheorySectionTranslation
    from app.storage.db import session_scope
    with session_scope() as db:
        langs = {
            t.language.value
            for t in db.query(TheorySectionTranslation).filter_by(section_id=section_id).all()
        }
    assert langs == {"uz", "ru"}
    # Student (uz) still sees the uz title.
    c = student_client(client)
    assert c.get("/api/theory/sections/ml").json()["title"] == "Belgilar"


# --------------------------------------------------------------------------- #
# Demo seed: inserts clearly-marked DEMO content only (no unverified facts)
# --------------------------------------------------------------------------- #
def test_seed_theory_demo_inserts_published_demo_content(client):
    from app.scripts.seed_theory_demo import run

    result = run()
    assert result["sections"] == 3 and result["signs"] == 4

    c = student_client(client)
    sections = c.get("/api/theory/sections").json()["sections"]
    slugs = {s["slug"] for s in sections}
    assert {"demo-yol-belgilari", "demo-svetofor", "demo-birinchi-yordam"} <= slugs
    signs = c.get("/api/theory/signs").json()["signs"]
    # All demo signs use obviously-fake DEMO-* codes (never real YHQ numbers).
    assert signs and all(s["code"].startswith("DEMO-") for s in signs)
    # Re-running is idempotent (skips when sections already exist).
    assert run().get("skipped") is True
