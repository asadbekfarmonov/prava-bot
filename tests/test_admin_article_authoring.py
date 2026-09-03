"""Admin section + article (block editor) authoring via the API (docs/spec/19 phase 2).

Mirrors the new admin.tsx SectionsManager/ArticlesManager flow:
create section -> publish; create article -> edit content with blocks
(text + rule_callout + table) -> submit -> review -> publish; then the student
reader shows the published article while drafts never leak.
"""

from __future__ import annotations

from tests.admin_helper import build_admins, make_rule
from tests.theory_helper import student_client


def test_admin_can_author_section_and_article_with_blocks(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code="YHQ:20.1")

    # --- Section: create (author) then publish (reviewer/admin) ---
    s = roles["author"].post(
        "/api/admin/theory/sections",
        json={"slug": "tezlik", "title": "Tezlik", "subtitle": "", "topic": "speed_distance", "position": 1},
    )
    assert s.status_code == 201, s.text
    sec_id = s.json()["id"]
    assert roles["admin"].post(f"/api/admin/theory/sections/{sec_id}/publish").status_code == 200

    # --- Article: create container ---
    a = roles["author"].post(
        "/api/admin/theory/articles",
        json={"section_id": sec_id, "slug": "tezlik-asoslari", "kind": "lesson", "position": 1},
    )
    assert a.status_code == 201, a.text
    art_id = a.json()["article_id"]

    # --- Content: author blocks (text + rule_callout + table with data) ---
    e = roles["author"].put(
        f"/api/admin/theory/articles/{art_id}",
        json={
            "title": "Tezlik asoslari",
            "summary": "Qisqacha",
            "ai_assisted": True,
            "blocks": [
                {"type": "text", "body": "Tezlikni yo'l sharoitiga moslang."},
                {"type": "rule_callout", "body": "Qoidaga rioya qiling.", "rule_code": "YHQ:20.1"},
                {"type": "table", "body": "", "data": {"headers": ["A", "B"], "rows": [["1", "2"]]}},
            ],
            "rule_codes": ["YHQ:20.1"],
            "question_ids": [],
        },
    )
    assert e.status_code == 200, e.text
    vid = e.json()["id"]

    # --- Lifecycle: submit -> review -> publish ---
    assert roles["author"].post(f"/api/admin/theory/article-versions/{vid}/submit-review").status_code == 200
    assert roles["admin"].post(f"/api/admin/theory/article-versions/{vid}/review").status_code == 200
    assert roles["admin"].post(f"/api/admin/theory/article-versions/{vid}/publish").status_code == 200

    # --- Admin list shows it published ---
    arts = roles["admin"].get("/api/admin/theory/articles").json()["articles"]
    assert any(x["slug"] == "tezlik-asoslari" and x["lifecycle_status"] == "published" for x in arts), arts

    # --- Student reader shows the published article ---
    student = student_client(client, telegram_id=1001, name="Dilnoza")
    ga = student.get("/api/theory/articles/tezlik-asoslari")
    assert ga.status_code == 200, ga.text


def test_student_cannot_see_unpublished_article(client):
    roles = build_admins(client)
    s = roles["author"].post(
        "/api/admin/theory/sections",
        json={"slug": "manevr", "title": "Manevr", "subtitle": "", "position": 2},
    )
    assert s.status_code == 201, s.text
    sec_id = s.json()["id"]
    assert roles["admin"].post(f"/api/admin/theory/sections/{sec_id}/publish").status_code == 200
    a = roles["author"].post(
        "/api/admin/theory/articles",
        json={"section_id": sec_id, "slug": "draft-maqola", "kind": "lesson", "position": 1},
    )
    assert a.status_code == 201, a.text
    art_id = a.json()["article_id"]
    # author content but DO NOT publish
    e = roles["author"].put(
        f"/api/admin/theory/articles/{art_id}",
        json={"title": "Qoralama", "summary": "", "ai_assisted": True,
              "blocks": [{"type": "text", "body": "matn"}], "rule_codes": [], "question_ids": []},
    )
    assert e.status_code == 200, e.text

    # Admin list (drafts) sees it; student reader 404/absent.
    arts = roles["admin"].get("/api/admin/theory/articles").json()["articles"]
    assert any(x["slug"] == "draft-maqola" for x in arts), arts
    student = student_client(client, telegram_id=1002, name="Talaba")
    assert student.get("/api/theory/articles/draft-maqola").status_code == 404
