"""QA adversarial gap tests for the Theory / YHQ Handbook (docs/spec/14, 15, 09).

These extend tests/test_theory.py with cases the base suite did not cover:
- AuthZ: role-too-low (content_author) cannot publish (403), on top of non-admin 403.
- Published-only visibility of global search AND Practice->Theory by-rule (draft excluded).
- current_version_id repoints ONLY on publish (edit forks a hidden draft; students keep old).
- Stored-XSS inert in a catalogue TRANSLATION field (sign meaning), not just article text.
- Mass-assignment: extra client fields (admin_role/state/is_correct) are ignored.
- practice_link content block exposes only ref_question_id — never options/correctness.
- Invalid sign family filter -> 400 (input validation).
"""

from __future__ import annotations

from tests.admin_helper import build_admins, make_rule, new_client, dev_login, onboard
from tests.theory_helper import (
    create_article,
    create_section,
    create_sign,
    publish_question,
    student_client,
)


# --------------------------------------------------------------------------- #
# AuthZ: role too low cannot publish (author < reviewer)
# --------------------------------------------------------------------------- #
def test_author_role_too_low_cannot_publish_article_or_sign(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    section_id = create_section(roles)

    # Author creates + edits an article draft (allowed) ...
    r = roles["author"].post(
        "/api/admin/theory/articles",
        json={"section_id": section_id, "slug": "lowrole", "kind": "lesson", "position": 1},
    )
    assert r.status_code == 201, r.text
    article_id = r.json()["article_id"]
    e = roles["author"].put(
        f"/api/admin/theory/articles/{article_id}",
        json={"title": "T", "summary": "s", "blocks": [{"type": "text", "body": "b"}],
              "rule_codes": [rule["code"]], "question_ids": []},
    )
    version_id = e.json()["id"]
    roles["author"].post(f"/api/admin/theory/article-versions/{version_id}/submit-review")
    roles["reviewer"].post(f"/api/admin/theory/article-versions/{version_id}/review")

    # ... but the AUTHOR (role too low) cannot PUBLISH -> 403.
    assert roles["author"].post(
        f"/api/admin/theory/article-versions/{version_id}/publish"
    ).status_code == 403
    # Reviewer/verify endpoints are also gated to reviewer.
    assert roles["author"].get("/api/admin/theory/review-queue").status_code == 403

    # Same for signs: author cannot publish a sign version.
    sv = roles["author"].post(
        "/api/admin/theory/signs",
        json={"official_code": "DEMO-LOW", "family": "warning", "position": 1},
    ).json()
    sver = roles["author"].put(
        f"/api/admin/theory/signs/{sv['road_sign_id']}",
        json={"name": "n", "meaning": "m", "driver_action": "d", "rule_codes": [rule["code"]]},
    ).json()["id"]
    roles["author"].post(f"/api/admin/theory/sign-versions/{sver}/submit-review")
    roles["reviewer"].post(f"/api/admin/theory/sign-versions/{sver}/review")
    assert roles["author"].post(
        f"/api/admin/theory/sign-versions/{sver}/publish"
    ).status_code == 403


# --------------------------------------------------------------------------- #
# Published-only visibility: global search excludes DRAFT content
# --------------------------------------------------------------------------- #
def test_search_excludes_unpublished_content(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    section_id = create_section(roles)

    # Draft article (never published) with a unique searchable title.
    r = roles["author"].post(
        "/api/admin/theory/articles",
        json={"section_id": section_id, "slug": "hidden-art", "kind": "lesson", "position": 5},
    )
    aid = r.json()["article_id"]
    roles["author"].put(
        f"/api/admin/theory/articles/{aid}",
        json={"title": "ZZUNIQTITLE", "summary": "secret", "blocks": [{"type": "text", "body": "x"}],
              "rule_codes": [rule["code"]], "question_ids": []},
    )
    # Draft sign (never published) with a unique keyword.
    sv = roles["author"].post(
        "/api/admin/theory/signs",
        json={"official_code": "DEMO-HID", "family": "warning", "position": 5},
    ).json()
    roles["author"].put(
        f"/api/admin/theory/signs/{sv['road_sign_id']}",
        json={"name": "ZZUNIQSIGN", "meaning": "m", "driver_action": "d",
              "keywords": "zzuniqkw", "rule_codes": [rule["code"]]},
    )

    c = student_client(client)
    assert c.get("/api/theory/search?q=ZZUNIQTITLE").json()["results"] == []
    assert c.get("/api/theory/search?q=ZZUNIQSIGN").json()["results"] == []
    assert c.get("/api/theory/search?q=zzuniqkw").json()["results"] == []


# --------------------------------------------------------------------------- #
# Published-only visibility: Practice->Theory by-rule excludes DRAFT articles
# --------------------------------------------------------------------------- #
def test_by_rule_excludes_unpublished_article(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:77.7")
    section_id = create_section(roles)

    # A draft article linked to the rule (edit creates a TheoryArticleRule) but NOT published.
    r = roles["author"].post(
        "/api/admin/theory/articles",
        json={"section_id": section_id, "slug": "draft-by-rule", "kind": "lesson", "position": 3},
    )
    aid = r.json()["article_id"]
    roles["author"].put(
        f"/api/admin/theory/articles/{aid}",
        json={"title": "Draft", "summary": "s", "blocks": [{"type": "text", "body": "x"}],
              "rule_codes": [rule["code"]], "question_ids": []},
    )

    c = student_client(client)
    res = c.get(f"/api/theory/by-rule/{rule['code']}").json()
    assert res["rule"]["code"] == rule["code"]
    # The unpublished article must NOT be resolved to a student.
    assert all(a["id"] != aid for a in res["articles"])
    assert res["articles"] == []


# --------------------------------------------------------------------------- #
# current_version_id repoints ONLY on publish (edit forks a hidden draft)
# --------------------------------------------------------------------------- #
def test_current_version_repoints_only_on_publish(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    section_id = create_section(roles)
    art = create_article(roles, section_id, rule_code=rule["code"], title="V1 sarlavha")
    article_id = art["article_id"]
    v1 = art["version_id"]

    from app.domain.models import TheoryArticle
    from app.storage.db import session_scope
    with session_scope() as db:
        assert db.get(TheoryArticle, article_id).current_version_id == v1

    # Editing forks v2 as DRAFT; current_version_id must still point to v1.
    e = roles["author"].put(
        f"/api/admin/theory/articles/{article_id}",
        json={"title": "V2 sarlavha", "summary": "v2", "blocks": [{"type": "text", "body": "v2"}],
              "rule_codes": [rule["code"]], "question_ids": []},
    )
    v2 = e.json()["id"]
    assert v2 != v1

    c = student_client(client)
    # Student still sees the OLD published title until v2 is published.
    assert c.get(f"/api/theory/articles/{art['slug']}").json()["title"] == "V1 sarlavha"
    with session_scope() as db:
        assert db.get(TheoryArticle, article_id).current_version_id == v1

    # Publish v2 -> current_version_id repoints; student now sees v2.
    roles["author"].post(f"/api/admin/theory/article-versions/{v2}/submit-review")
    roles["reviewer"].post(f"/api/admin/theory/article-versions/{v2}/review")
    roles["reviewer"].post(f"/api/admin/theory/article-versions/{v2}/publish")
    with session_scope() as db:
        assert db.get(TheoryArticle, article_id).current_version_id == v2
    assert c.get(f"/api/theory/articles/{art['slug']}").json()["title"] == "V2 sarlavha"


# --------------------------------------------------------------------------- #
# Stored-XSS inert in a catalogue TRANSLATION field (sign meaning/name)
# --------------------------------------------------------------------------- #
def test_stored_xss_inert_in_sign_translation_fields(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    payload = "<img src=x onerror=alert(1)><script>steal()</script>"
    sign = create_sign(
        roles, code="DEMO-XSS", family="prohibitory", rule_code=rule["code"], name=payload,
    )
    c = student_client(client)
    detail = c.get(f"/api/theory/signs/{sign['code']}").json()
    # Served verbatim as JSON string data (React text node -> inert). API emits no HTML.
    assert detail["name"] == payload


# --------------------------------------------------------------------------- #
# Mass-assignment: extra client-supplied fields are ignored (allowlist schema)
# --------------------------------------------------------------------------- #
def test_mass_assignment_extra_fields_ignored(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    create_sign(roles, code="DEMO-MA", family="warning", rule_code=rule["code"])

    c = student_client(client)
    # Favorite body carries hostile extra fields; they must be ignored, not honoured.
    add = c.post(
        "/api/theory/favorites",
        json={"target_type": "sign", "target_id": "DEMO-MA",
              "admin_role": "superadmin", "user_id": "99999", "id": "attacker-id"},
    )
    assert add.status_code == 201
    body = add.json()
    assert body["id"] != "attacker-id"        # server-generated id, not client id
    assert body["target_id"] == "DEMO-MA"

    # Progress body tries to smuggle state=mastered -> server marks 'viewed' only.
    prog = c.post(
        "/api/theory/progress",
        json={"target_type": "sign", "target_id": "DEMO-MA", "state": "mastered",
              "admin_role": "superadmin"},
    ).json()
    assert prog["state"] == "viewed"


# --------------------------------------------------------------------------- #
# practice_link content block exposes only ref_question_id (no answer leak)
# --------------------------------------------------------------------------- #
def test_practice_link_block_exposes_no_answer(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    _, qid = publish_question(roles, rule["code"])
    section_id = create_section(roles)
    art = create_article(
        roles, section_id, slug="plink", rule_code=rule["code"], question_ids=[qid],
        blocks=[
            {"type": "text", "body": "intro"},
            {"type": "practice_link", "body": "Mashq qilish", "ref_question_id": qid},
        ],
    )
    c = student_client(client)
    article = c.get(f"/api/theory/articles/{art['slug']}").json()
    pblock = next(b for b in article["blocks"] if b["type"] == "practice_link")
    assert pblock["ref_question_id"] == qid
    # The embedded question must NOT leak options / correctness / explanation.
    assert "options" not in pblock
    assert "is_correct" not in pblock
    assert "correct_option_id" not in pblock
    assert "explanation" not in pblock


# --------------------------------------------------------------------------- #
# Input validation: invalid sign family filter -> 400
# --------------------------------------------------------------------------- #
def test_invalid_sign_family_filter_rejected(client):
    c = student_client(client)
    assert c.get("/api/theory/signs?family=not_a_family").status_code == 400
