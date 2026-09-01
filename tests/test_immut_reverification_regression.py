"""REGRESSION (QA, adversarial) — immutability of an EVER-PUBLISHED version.

docs/spec/02-domain-model.md (immutability): "once a QuestionVersion is `published`
or referenced by any attempt, it must never be mutated. Editing published content
creates a new QuestionVersion."
docs/spec/08-admin.md (lifecycle): published -> needs_reverification (on rule change)
-> back to review.

BUG: app/services/authoring.py includes VersionStatus.NEEDS_REVERIFICATION in
_EDITABLE_STATUSES, and is_version_locked() only locks by status
PUBLISHED/SUPERSEDED/ARCHIVED or attempt-reference. So a version that WAS published,
then flipped to needs_reverification by a rule supersede, and that has no attempts yet,
is treated as an editable draft and MUTATED IN PLACE — destroying published content and
leaving Question.current_version_id pointing at a mutated draft.

This test asserts the SPEC-CORRECT behavior (edit must fork a new version; the
ever-published row must stay immutable). It will pass once is_version_locked() also
locks any version with published_at is not None.
"""
from __future__ import annotations

from tests.admin_helper import build_admins, make_rule, question_id_for_version, valid_question_payload


def _publish(roles, rule_code, prompt="Regr savol?"):
    r = roles["author"].post("/api/admin/questions", json=valid_question_payload(rule_code, prompt))
    vid = r.json()["id"]
    roles["author"].post(f"/api/admin/versions/{vid}/submit-review")
    roles["reviewer"].post(f"/api/admin/versions/{vid}/review")
    assert roles["reviewer"].post(f"/api/admin/versions/{vid}/publish").status_code == 200
    return vid


def test_editing_needs_reverification_published_version_forks_new_version(client):
    roles = build_admins(client)
    rule = make_rule(roles["admin"], code="YHQ:55.5", text="Asl qoida")
    v1 = _publish(roles, rule["code"], prompt="ASL PUBLISHED MATN")  # no attempts
    qid = question_id_for_version(v1)

    assert roles["admin"].post(
        f"/api/admin/rules/{rule['id']}/supersede", json={"new_status": "superseded"}
    ).status_code == 200

    from app.domain.models import Question, QuestionVersion, QuestionVersionTranslation
    from app.storage.db import session_scope

    with session_scope() as db:
        assert db.get(QuestionVersion, v1).status.value == "needs_reverification"

    r = roles["author"].put(
        f"/api/admin/questions/{qid}",
        json=valid_question_payload(rule["code"], prompt="TAHRIRLANGAN MATN"),
    )
    assert r.status_code == 200, r.text
    new_vid = r.json()["id"]

    # A new version must be forked; the ever-published row must be untouched.
    assert new_vid != v1, "edit mutated/reused the published version row (immutability violation)"
    with session_scope() as db:
        v1_tr = db.query(QuestionVersionTranslation).filter_by(question_version_id=v1).one()
        assert v1_tr.prompt == "ASL PUBLISHED MATN", "published content was overwritten in place"
        v1_status = db.get(QuestionVersion, v1).status.value
        assert v1_status != "draft", f"a published version was downgraded to {v1_status}"
        # current_version_id must never point at a draft.
        q = db.get(Question, qid)
        if q.current_version_id is not None:
            assert db.get(QuestionVersion, q.current_version_id).status.value != "draft"
