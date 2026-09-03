"""Phase 7 (docs/spec/20) training-assessment backend gate tests.

Proves: manual pins correct QuestionVersions; random selects unique eligible questions;
insufficient pool blocks publish; later question/assessment edits don't change old attempts;
official ExamConfig untouched; non-admins blocked; active attempt never leaks answer keys.
"""

from __future__ import annotations

from sqlalchemy import select

from app.domain.models import AnswerOption, Assessment, Question, QuestionVersion
from app.storage.db import session_scope
from tests.admin_helper import (
    build_admins,
    make_rule,
    new_client,
    question_id_for_version,
    valid_question_payload,
)
from tests.theory_helper import student_client

RULE = "YHQ:70.1"


def _pub_q(roles, prompt, topic="general_rules", difficulty=1):
    payload = valid_question_payload(RULE, prompt)
    payload["topic"] = topic
    payload["difficulty"] = difficulty
    payload["is_sign_question"] = False
    r = roles["author"].post("/api/admin/questions", json=payload)
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    assert roles["author"].post(f"/api/admin/versions/{vid}/submit-review").status_code == 200
    assert roles["reviewer"].post(f"/api/admin/versions/{vid}/review").status_code == 200
    assert roles["reviewer"].post(f"/api/admin/versions/{vid}/publish").status_code == 200
    return question_id_for_version(vid), vid


def _current_version_id(question_id: str) -> str:
    with session_scope() as db:
        return db.get(Question, question_id).current_version_id


def _correct_option_id(version_id: str) -> str:
    with session_scope() as db:
        opt = db.scalar(select(AnswerOption).where(
            AnswerOption.question_version_id == version_id, AnswerOption.is_correct.is_(True)
        ))
        return opt.id


def _create_manual(roles, q_ids, *, pass_correct=1, reveal="each_answer"):
    c = roles["author"].post("/api/admin/assessments", json={"type": "custom_test", "title": "Qo'lda test"})
    assert c.status_code == 201, c.text
    aid = c.json()["id"]
    u = roles["author"].put(f"/api/admin/assessments/{aid}", json={
        "selection_mode": "manual", "question_ids": q_ids, "question_count": len(q_ids),
        "pass_correct": pass_correct, "show_explanations_after": reveal,
    })
    assert u.status_code == 200, u.text
    return aid, u.json()["slug"]


# --------------------------------------------------------------------------- #
def test_manual_assessment_pins_current_published_versions_in_order(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code=RULE)
    q1, v1 = _pub_q(roles, "Savol 1?")
    q2, v2 = _pub_q(roles, "Savol 2?")
    aid, slug = _create_manual(roles, [q1, q2])
    assert roles["reviewer"].post(f"/api/admin/assessments/{aid}/publish").status_code == 200

    student = student_client(client, telegram_id=2101, name="A")
    start = student.post(f"/api/assessments/{slug}/attempts")
    assert start.status_code == 201, start.text
    qs = start.json()["questions"]
    assert [q["question_version_id"] for q in qs] == [v1, v2]
    # no answer-key leak in the live payload
    for q in qs:
        for opt in q["options"]:
            assert "is_correct" not in opt


def test_random_assessment_selects_unique_eligible(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code=RULE)
    pool = [_pub_q(roles, f"R{i}?", topic="general_rules", difficulty=1)[0] for i in range(5)]
    eligible_versions = {_current_version_id(qid) for qid in pool}
    c = roles["author"].post("/api/admin/assessments", json={"type": "custom_test", "title": "Random test"})
    aid = c.json()["id"]
    roles["author"].put(f"/api/admin/assessments/{aid}", json={
        "selection_mode": "random_filter", "topic_filters": ["general_rules"], "question_count": 3,
    })
    ec = roles["author"].get(f"/api/admin/assessments/{aid}/eligible-count").json()
    assert ec["eligible_count"] >= 5
    assert roles["reviewer"].post(f"/api/admin/assessments/{aid}/publish").status_code == 200
    slug = roles["author"].get(f"/api/admin/assessments/{aid}").json()["slug"]

    student = student_client(client, telegram_id=2102, name="B")
    qs = student.post(f"/api/assessments/{slug}/attempts").json()["questions"]
    vids = [q["question_version_id"] for q in qs]
    assert len(vids) == 3
    assert len(set(vids)) == 3
    assert set(vids).issubset(eligible_versions)


def test_insufficient_pool_blocks_publish(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code=RULE)
    _pub_q(roles, "Only one?")
    c = roles["author"].post("/api/admin/assessments", json={"type": "custom_test", "title": "Katta test"})
    aid = c.json()["id"]
    roles["author"].put(f"/api/admin/assessments/{aid}", json={
        "selection_mode": "random_filter", "topic_filters": ["general_rules"], "question_count": 50,
    })
    pub = roles["reviewer"].post(f"/api/admin/assessments/{aid}/publish")
    assert pub.status_code == 422
    assert "savol" in pub.json()["detail"].lower()


def test_later_question_edit_does_not_change_old_attempt(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code=RULE)
    q1, v1 = _pub_q(roles, "Barqaror savol?")
    q2, v2 = _pub_q(roles, "Ikkinchi?")
    aid, slug = _create_manual(roles, [q1, q2])
    assert roles["reviewer"].post(f"/api/admin/assessments/{aid}/publish").status_code == 200
    student = student_client(client, telegram_id=2103, name="C")
    attempt = student.post(f"/api/assessments/{slug}/attempts").json()
    pinned_before = [q["question_version_id"] for q in attempt["questions"]]

    # Edit q1 -> new published version.
    edit_payload = valid_question_payload(RULE, "Barqaror savol (tahrirlangan)?")
    e = roles["author"].put(f"/api/admin/questions/{q1}", json=edit_payload)
    assert e.status_code == 200, e.text
    new_vid = e.json()["id"]
    assert roles["author"].post(f"/api/admin/versions/{new_vid}/submit-review").status_code == 200
    assert roles["reviewer"].post(f"/api/admin/versions/{new_vid}/review").status_code == 200
    assert roles["reviewer"].post(f"/api/admin/versions/{new_vid}/publish").status_code == 200
    assert _current_version_id(q1) == new_vid and new_vid != v1

    after = student.get(f"/api/assessment-attempts/{attempt['id']}").json()
    assert [q["question_version_id"] for q in after["questions"]] == pinned_before
    assert v1 in pinned_before  # old attempt still pins the ORIGINAL version


def test_later_assessment_edit_does_not_change_old_attempt(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code=RULE)
    q1, v1 = _pub_q(roles, "Q1?")
    q2, v2 = _pub_q(roles, "Q2?")
    aid, slug = _create_manual(roles, [q1, q2])
    assert roles["reviewer"].post(f"/api/admin/assessments/{aid}/publish").status_code == 200
    student = student_client(client, telegram_id=2104, name="D")
    attempt = student.post(f"/api/assessments/{slug}/attempts").json()
    with session_scope() as db:
        a = db.scalar(select(Assessment).where(Assessment.slug == slug))
        v_before = a.current_version_id

    # Edit the assessment (forks a new draft version) + republish.
    roles["author"].put(f"/api/admin/assessments/{aid}", json={"title": "Yangi sarlavha", "question_ids": [q2], "question_count": 1})
    assert roles["reviewer"].post(f"/api/admin/assessments/{aid}/publish").status_code == 200
    with session_scope() as db:
        a = db.scalar(select(Assessment).where(Assessment.slug == slug))
        assert a.current_version_id != v_before  # a new version is now current

    after = student.get(f"/api/assessment-attempts/{attempt['id']}").json()
    assert [q["question_version_id"] for q in after["questions"]] == [v1, v2]  # old attempt unchanged


def test_exam_config_untouched_by_assessments():
    import app.services.assessments as m
    src = open(m.__file__, encoding="utf-8").read()
    assert "ExamConfig" not in src
    assert "MockTemplate" not in src
    assert "MockAttempt" not in src


def test_non_admin_cannot_use_admin_assessment_endpoints(client):
    anon = new_client(client)
    assert anon.get("/api/admin/assessments").status_code == 401
    student = student_client(client, telegram_id=2105, name="E")
    assert student.get("/api/admin/assessments").status_code == 403
    assert student.post("/api/admin/assessments", json={"type": "custom_test", "title": "x"}).status_code == 403


def test_active_attempt_does_not_leak_answer_keys(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code=RULE)
    q1, v1 = _pub_q(roles, "Leak1?")
    q2, v2 = _pub_q(roles, "Leak2?")
    aid, slug = _create_manual(roles, [q1, q2], pass_correct=2, reveal="completion")
    assert roles["reviewer"].post(f"/api/admin/assessments/{aid}/publish").status_code == 200
    student = student_client(client, telegram_id=2106, name="F")
    attempt = student.post(f"/api/assessments/{slug}/attempts").json()
    # live GET: no correctness anywhere
    live = student.get(f"/api/assessment-attempts/{attempt['id']}").json()
    for q in live["questions"]:
        assert q.get("is_correct") is None
        for opt in q["options"]:
            assert "is_correct" not in opt
    # completion-reveal: answering does NOT return correctness
    ans = student.post(f"/api/assessment-attempts/{attempt['id']}/answers",
                       json={"question_version_id": v1, "selected_option_id": _correct_option_id(v1)})
    assert ans.status_code == 200
    assert ans.json()["is_correct"] is None

    # submit -> now correctness revealed; grading correct
    student.post(f"/api/assessment-attempts/{attempt['id']}/answers",
                 json={"question_version_id": v2, "selected_option_id": _correct_option_id(v2)})
    done = student.post(f"/api/assessment-attempts/{attempt['id']}/submit").json()
    assert done["correct_count"] == 2
    assert done["passed"] is True
