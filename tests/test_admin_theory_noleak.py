"""Adversarial no-answer-leak guard for the docs/spec/19 admin Theory surfaces.

The admin Theory list endpoints + review-queue expose catalogue/version metadata and
link questions only by id (question_ids). They must NEVER embed a linked question's
options / correctness. This locks the invariant against a future regression that starts
inlining questions into a theory card or preview.
"""

from __future__ import annotations

from tests.admin_helper import build_admins, make_rule
from tests.theory_helper import create_sign, publish_question, student_client


def _assert_no_leak(blob: str, ctx: str):
    lowered = blob.lower()
    # correctness markers must never appear in a theory surface payload
    assert "is_correct" not in lowered, (ctx, "is_correct leaked")
    assert "correct_option_id" not in lowered, (ctx, "correct_option_id leaked")
    # the correct option's authored text/explanation must not be embedded
    assert "chunki to'g'ri" not in lowered, (ctx, "correct explanation leaked")


def test_admin_theory_surfaces_never_embed_question_answers(client):
    roles = build_admins(client)
    make_rule(roles["admin"], code="YHQ:31.1")
    # A published question whose correct option text is "To'g'ri" / expl "Chunki to'g'ri."
    _vid, qid = publish_question(roles, "YHQ:31.1", prompt="Belgi savoli?")
    # Publish a sign that LINKS that question.
    sign = create_sign(roles, code="NL-W1", rule_code="YHQ:31.1", question_ids=[qid],
                       name="Ulangan belgi")

    # Admin list (incl. drafts) — no options, no correctness anywhere.
    r = roles["admin"].get("/api/admin/theory/signs")
    assert r.status_code == 200, r.text
    _assert_no_leak(r.text, "admin sign list")
    # the linked sign is present (sanity: we're scanning a payload that references the q)
    assert any(s["code"] == sign["code"] for s in r.json()["signs"])

    # Review queue payload (reviewer-gated) — version metadata only.
    rq = roles["reviewer"].get("/api/admin/theory/review-queue")
    assert rq.status_code == 200, rq.text
    _assert_no_leak(rq.text, "review-queue")

    # Student sign detail embeds only linked_question_count, never options.
    s = student_client(client, telegram_id=2222, name="Talaba")
    det = s.get(f"/api/theory/signs/{sign['code']}")
    assert det.status_code == 200, det.text
    body = det.json()
    assert "linked_question_count" in body
    assert "options" not in body
    _assert_no_leak(det.text, "student sign detail")


def test_admin_list_flag_false_excludes_drafts_all_entities(client):
    """include_unpublished=false must exclude drafts for markings/gestures/lights too
    (parity with the signs case already covered)."""
    from tests.test_admin_theory_list import _draft_gesture, _draft_light, _draft_marking

    roles = build_admins(client)
    m = _draft_marking(roles, code="NLF-M")
    g = _draft_gesture(roles, code="NLF-G")
    light = _draft_light(roles, title="NLF svetofor")

    mr = roles["admin"].get("/api/admin/theory/markings?include_unpublished=false").json()["markings"]
    assert m["code"] not in [x["code"] for x in mr], mr
    gr = roles["admin"].get("/api/admin/theory/gestures?include_unpublished=false").json()["gestures"]
    assert g["code"] not in [x["code"] for x in gr], gr
    lr = roles["admin"].get("/api/admin/theory/lights?include_unpublished=false").json()["lights"]
    assert light["title"] not in [x["title"] for x in lr], lr
