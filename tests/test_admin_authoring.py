"""Immutable-version authoring, review lifecycle, rule catalog + propagation, QA."""

from __future__ import annotations

from tests.admin_helper import (
    build_admins,
    dev_login,
    make_rule,
    new_client,
    onboard,
    question_id_for_version,
    valid_question_payload,
)


def _publish(roles, rule_code, prompt="Test savol?"):
    """Create a valid question (save = live -> immediately PUBLISHED); return version id."""
    r = roles["author"].post("/api/admin/questions", json=valid_question_payload(rule_code, prompt))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "published", body
    return body["id"]


def test_full_publish_lifecycle(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    _publish(roles, rule["code"])


def test_create_live_blocked_by_minimal_floor(client):
    """save = live: a question that violates the minimal quality floor (two correct
    options + empty prompt/media) is rejected at CREATE with 422 — no draft persists.
    A question WITHOUT explanations/rule (encouraged but optional) succeeds."""
    roles = build_admins(client)
    make_rule(roles["admin"], code="YHQ:70.9")
    # Blocked: two correct AND no prompt/media.
    bad = {
        "category": "B",
        "topic": "general_rules",
        "prompt": "",
        "short_explanation": "",
        "options": [
            {"text": "a", "explanation": "", "is_correct": True},
            {"text": "b", "explanation": "", "is_correct": True},
        ],
        "rule_codes": [],
    }
    resp = roles["author"].post("/api/admin/questions", json=bad)
    assert resp.status_code == 422, resp.text
    assert "errors" in resp.json()["detail"]

    # Blocked: fewer than 2 options.
    too_few = {
        "category": "B", "topic": "general_rules", "prompt": "Savol?",
        "short_explanation": "", "rule_codes": [],
        "options": [{"text": "a", "explanation": "", "is_correct": True}],
    }
    assert roles["author"].post("/api/admin/questions", json=too_few).status_code == 422

    # Succeeds (published) with NO explanation and NO rule — only the floor matters.
    ok = {
        "category": "B", "topic": "general_rules", "prompt": "To'g'ri savol?",
        "short_explanation": "", "rule_codes": [],
        "options": [
            {"text": "a", "explanation": "", "is_correct": True},
            {"text": "b", "explanation": "", "is_correct": False},
        ],
    }
    r = roles["author"].post("/api/admin/questions", json=ok)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "published"


def test_editing_published_creates_new_version_without_mutating_old(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    v1 = _publish(roles, rule["code"], prompt="Asl savol?")
    qid = question_id_for_version(v1)

    # Edit the PUBLISHED question -> must create a NEW draft version, not mutate v1.
    payload = valid_question_payload(rule["code"], prompt="Tahrirlangan savol?")
    r = roles["author"].put(f"/api/admin/questions/{qid}", json=payload)
    assert r.status_code == 200, r.text
    v2 = r.json()["id"]
    assert v2 != v1
    assert r.json()["version"] == 2

    # v1 is retained and unchanged (immutable): still resolves to the original prompt.
    from app.domain.models import Question, QuestionVersion, QuestionVersionTranslation
    from app.storage.db import session_scope

    with session_scope() as db:
        old = db.get(QuestionVersion, v1)
        assert old is not None
        tr = db.query(QuestionVersionTranslation).filter_by(question_version_id=v1).one()
        assert tr.prompt == "Asl savol?"  # unchanged
        # Publish v2 and confirm the container repoints, v1 becomes superseded.

    roles["author"].post(f"/api/admin/versions/{v2}/submit-review")
    roles["reviewer"].post(f"/api/admin/versions/{v2}/review")
    assert roles["reviewer"].post(f"/api/admin/versions/{v2}/publish").status_code == 200

    with session_scope() as db:
        q = db.get(Question, qid)
        assert q.current_version_id == v2
        old = db.get(QuestionVersion, v1)
        assert old.status.value == "superseded"
        tr = db.query(QuestionVersionTranslation).filter_by(question_version_id=v1).one()
        assert tr.prompt == "Asl savol?"  # STILL unchanged after v2 published


def test_completed_mock_still_renders_pinned_old_version_after_edit(client):
    from tests.seed_helper import seed_demo_bank

    seed_demo_bank()  # 20+ published questions
    roles = build_admins(client)

    student = new_client(client)
    dev_login(student, 1001, "Student")
    onboard(student)

    start = student.post("/api/mock/attempts")
    assert start.status_code == 200, start.text
    attempt_id = start.json()["id"]
    questions = start.json()["questions"]
    # Answer everything and submit.
    for q in questions:
        student.post(
            f"/api/mock/attempts/{attempt_id}/answers",
            json={"question_version_id": q["question_version_id"], "selected_option_id": q["options"][0]["id"]},
        )
    assert student.post(f"/api/mock/attempts/{attempt_id}/submit").status_code == 200

    review_before = student.get(f"/api/mock/attempts/{attempt_id}/review").json()
    item = review_before["items"][0]
    pinned_vid = item["question_version_id"]
    prompt_before = item["prompt"]
    option_ids_before = [o["id"] for o in item["options"]]

    # Admin edits that (published + mock-referenced) question -> new version.
    qid = question_id_for_version(pinned_vid)
    payload = valid_question_payload("YHQ:2.1", prompt="BUTUNLAY YANGI MATN")
    r = roles["author"].put(f"/api/admin/questions/{qid}", json=payload)
    assert r.status_code == 200, r.text
    v2 = r.json()["id"]
    assert v2 != pinned_vid
    roles["author"].post(f"/api/admin/versions/{v2}/submit-review")
    roles["reviewer"].post(f"/api/admin/versions/{v2}/review")
    assert roles["reviewer"].post(f"/api/admin/versions/{v2}/publish").status_code == 200

    # The historical mock STILL renders the pinned old version unchanged.
    review_after = student.get(f"/api/mock/attempts/{attempt_id}/review").json()
    item_after = next(i for i in review_after["items"] if i["question_version_id"] == pinned_vid)
    assert item_after["prompt"] == prompt_before
    assert [o["id"] for o in item_after["options"]] == option_ids_before
    assert item_after["prompt"] != "BUTUNLAY YANGI MATN"


def test_rule_search(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code="YHQ:13.9", text="Chorrahada bosh yo'l imtiyozga ega")
    make_rule(roles["admin"], code="YHQ:2.1", text="Haydovchi hujjatlarni olib yurishi shart")

    by_code = roles["author"].get("/api/admin/rules", params={"q": "13.9"}).json()["rules"]
    assert any(r["code"] == "YHQ:13.9" for r in by_code)
    by_text = roles["author"].get("/api/admin/rules", params={"q": "chorraha"}).json()["rules"]
    assert any(r["code"] == "YHQ:13.9" for r in by_text)


def test_superseding_rule_flips_linked_versions_to_needs_reverification(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:7.7", text="Asl qoida")
    vid = _publish(roles, rule["code"])

    resp = roles["admin"].post(f"/api/admin/rules/{rule['id']}/supersede", json={"new_status": "superseded"})
    assert resp.status_code == 200, resp.text
    assert vid in resp.json()["flipped_version_ids"]

    from app.domain.models import QuestionVersion
    from app.storage.db import session_scope

    with session_scope() as db:
        v = db.get(QuestionVersion, vid)
        assert v.status.value == "needs_reverification"


def test_qa_checklist_flags_optional_hints_and_exam_preview_has_no_leak(client):
    """A question published via save=live WITHOUT the (now-optional) explanations/rule
    is live, but the QA panel still surfaces those as non-blocking quality hints. The
    exam-preview never leaks answers/explanations/rules (integrity preserved)."""
    roles = build_admins(client)
    # Valid floor (prompt + one correct) but no explanations, no short, no rule.
    minimal = {
        "category": "B",
        "topic": "general_rules",
        "prompt": "Savol bormi?",
        "short_explanation": "",
        "options": [
            {"text": "a", "explanation": "", "is_correct": True},
            {"text": "b", "explanation": "", "is_correct": False},
        ],
        "rule_codes": [],
    }
    r = roles["author"].post("/api/admin/questions", json=minimal)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "published"
    vid = r.json()["id"]
    qid = question_id_for_version(vid)

    qa = roles["reviewer"].get(f"/api/admin/questions/{qid}/qa").json()
    checks = {c["key"]: c["passed"] for c in qa["checklist"]}
    # Blocking-floor checks pass:
    assert checks["exactly_one_correct"] is True
    assert checks["option_count_2_5"] is True
    # Encouraged-but-optional hints are flagged (non-blocking):
    assert checks["current_rule_linked"] is False
    assert checks["explanation_per_option"] is False
    assert checks["short_explanation_present"] is False
    assert checks["correct_answer_reasoning"] is False

    # exam-preview must not leak answers/explanations/rules.
    exam = qa["exam_preview"]
    assert "rules" not in exam and "short_explanation" not in exam
    for opt in exam["options"]:
        assert set(opt.keys()) == {"id", "position", "text"}
        assert "is_correct" not in opt and "explanation" not in opt
    # practice-preview DOES reveal them.
    prac = qa["practice_preview"]
    assert "rules" in prac
    assert all("is_correct" in o for o in prac["options"])


def test_duplicate_detection_hint(client):
    from tests.seed_helper import seed_demo_bank

    seed_demo_bank()
    roles = build_admins(client)
    # Use a seeded prompt to trigger an exact/near duplicate hint.
    payload = {
        "prompt": "Haydovchi yo'lda qanday hujjatlarni olib yurishi shart?",
        "option_texts": [
            "Faqat pasport",
            "Haydovchilik guvohnomasi va transport hujjatlari",
            "Hech qanday hujjat shart emas",
        ],
    }
    hits = roles["author"].post("/api/admin/duplicates/check", json=payload).json()["duplicates"]
    assert len(hits) >= 1
    assert hits[0]["exact_match"] is True


def test_question_list_search_and_filter(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"])
    _publish(roles, rule["code"], prompt="Chorrahada kim o'tadi?")
    _publish(roles, rule["code"], prompt="Svetofor qizil rangi?")

    listing = roles["author"].get("/api/admin/questions").json()
    assert listing["total"] >= 2

    # Text search.
    found = roles["author"].get("/api/admin/questions", params={"q": "Svetofor"}).json()["items"]
    assert any("Svetofor" in it["prompt"] for it in found)
    assert all("Chorraha" not in it["prompt"] for it in found)

    # Status filter.
    published = roles["author"].get("/api/admin/questions", params={"status": "published"}).json()["items"]
    assert all(it["lifecycle_status"] == "published" for it in published)

    # has_media filter (none have media).
    with_media = roles["author"].get("/api/admin/questions", params={"has_media": "true"}).json()["items"]
    assert with_media == []


def test_created_question_is_immediately_eligible_in_practice_pool(client):
    """save = live: a question created via POST /api/admin/questions is PUBLISHED at
    once (has current_version_id) and is immediately served in the practice pool — no
    submit/review/publish steps required."""
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:71.1")
    r = roles["author"].post(
        "/api/admin/questions",
        json=valid_question_payload(rule["code"], prompt="Yangi jonli savol?"),
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "published"
    vid = r.json()["id"]
    qid = question_id_for_version(vid)

    from app.domain.models import Question
    from app.storage.db import session_scope

    with session_scope() as db:
        assert db.get(Question, qid).current_version_id == vid  # live immediately

    student = new_client(client)
    dev_login(student, 1001, "Student")
    onboard(student)
    student.post("/api/practice/sessions", json={"topic": "general_rules"})
    q = student.get("/api/practice/questions/next", params={"topic": "general_rules"}).json()
    assert q["question_version_id"] == vid  # the freshly-created live question is served
