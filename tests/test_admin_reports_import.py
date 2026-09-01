"""Content reports (create + admin resolve), bulk import (never auto-publish invalid),
and the dashboard overview."""

from __future__ import annotations

import json

from tests.admin_helper import build_admins, dev_login, make_rule, new_client, onboard


def _a_version_id() -> str:
    from app.domain.models import QuestionVersion
    from app.storage.db import session_scope

    with session_scope() as db:
        return db.query(QuestionVersion).first().id


def test_content_report_create_and_admin_resolve(client):
    from tests.seed_helper import seed_demo_bank

    seed_demo_bank()
    roles = build_admins(client)
    vid = _a_version_id()

    student = new_client(client)
    dev_login(student, 1001, "Student")
    onboard(student)

    r = student.post("/api/reports", json={"question_version_id": vid, "reason": "wrong_answer", "note": "Xato"})
    assert r.status_code == 201, r.text
    report_id = r.json()["id"]

    queue = roles["reviewer"].get("/api/admin/reports").json()["reports"]
    assert any(rep["id"] == report_id and rep["question_version_id"] == vid for rep in queue)

    resolved = roles["reviewer"].post(f"/api/admin/reports/{report_id}/resolve", json={"action": "resolve", "note": "Tuzatildi"})
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    open_only = roles["reviewer"].get("/api/admin/reports", params={"status": "open"}).json()["reports"]
    assert all(rep["id"] != report_id for rep in open_only)


def test_report_rejects_invalid_reason(client):
    from tests.seed_helper import seed_demo_bank

    seed_demo_bank()
    build_admins(client)
    vid = _a_version_id()
    student = new_client(client)
    dev_login(student, 1001, "Student")
    onboard(student)
    r = student.post("/api/reports", json={"question_version_id": vid, "reason": "not_a_reason"})
    assert r.status_code == 422


def test_bulk_import_previews_validates_and_never_auto_publishes(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code="YHQ:2.1", text="Hujjatlar")

    rows = [
        {  # valid
            "external_id": "ext-1",
            "category": "B",
            "topic": "general_rules",
            "prompt": "Import savol?",
            "short_explanation": "Eslab qoling.",
            "rule_codes": ["YHQ:2.1"],
            "options": [
                {"text": "A", "explanation": "to'g'ri", "is_correct": True},
                {"text": "B", "explanation": "noto'g'ri", "is_correct": False},
            ],
        },
        {  # invalid: no correct option + missing rule
            "external_id": "ext-2",
            "category": "B",
            "topic": "general_rules",
            "prompt": "Yomon qator?",
            "short_explanation": "x",
            "rule_codes": ["YHQ:404"],
            "options": [
                {"text": "A", "explanation": "e", "is_correct": False},
                {"text": "B", "explanation": "e", "is_correct": False},
            ],
        },
    ]
    content = json.dumps(rows)

    # Preview: validates, does not commit.
    preview = roles["admin"].post("/api/admin/import", json={"format": "json", "content": content, "commit": False})
    assert preview.status_code == 200, preview.text
    pj = preview.json()
    assert pj["total_rows"] == 2 and pj["valid_rows"] == 1 and pj["rejected_rows"] == 1
    assert pj["committed"] is False
    assert pj["created_version_ids"] == []
    assert pj["rows"][1]["valid"] is False and pj["rows"][1]["errors"]

    # Commit: valid row lands as DRAFT (never auto-published); invalid rejected.
    commit = roles["admin"].post("/api/admin/import", json={"format": "json", "content": content, "commit": True}).json()
    assert commit["valid_rows"] == 1 and len(commit["created_version_ids"]) == 1

    from app.domain.models import Question, QuestionVersion
    from app.storage.db import session_scope

    created_vid = commit["created_version_ids"][0]
    with session_scope() as db:
        v = db.get(QuestionVersion, created_vid)
        assert v.status.value == "draft"  # NOT published
        q = db.get(Question, v.question_id)
        assert q.lifecycle_status.value == "draft"
        assert q.current_version_id is None  # nothing published


def test_bulk_import_csv(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code="YHQ:2.1", text="Hujjatlar")
    csv_content = (
        "category,topic,prompt,short_explanation,rule_code,correct_index,"
        "option1,explanation1,option2,explanation2\n"
        "B,general_rules,CSV savol?,Eslab qoling,YHQ:2.1,1,A,to'g'ri,B,noto'g'ri\n"
    )
    r = roles["admin"].post("/api/admin/import", json={"format": "csv", "content": csv_content, "commit": True})
    assert r.status_code == 200, r.text
    assert r.json()["valid_rows"] == 1


def test_overview_counts(client):
    from tests.seed_helper import seed_demo_bank

    n = seed_demo_bank()
    roles = build_admins(client)
    ov = roles["reviewer"].get("/api/admin/overview").json()
    assert ov["counts"]["published"] == n
    assert "topic_coverage" in ov
    assert ov["media_storage"]["object_count"] == 0
    assert "open_reports" in ov
