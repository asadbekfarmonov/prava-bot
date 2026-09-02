"""Spec-18 (Theory production completion) acceptance tests — criteria #2 and #3.

Runs on sqlite via the shared ``client`` fixture. Seeds real content with the production
scripts (``seed_theory_production`` + ``update_sign_meanings``), plus topic questions and a
DEMO baseline, then asserts through the student theory reader service + a student TestClient:

  #2  >=4 gestures, >=5 lights, >=8 markings — all published, non-empty Uzbek meaning/action,
      NO 'DEMO' code; >=12 sections with no '(DEMO)' title; >=1 published lesson article per
      core section, each with >=1 linked question; sign meanings are full sentences.
  #3  Published-only student content, and an article-linked practice start returns a question
      payload with NO correct-answer leak (reusing the no-leak practice loop).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.domain.enums import AdminRole, Category, Language, Topic, VersionStatus
from app.domain.models import User
from app.scripts import (
    seed_invented_questions,
    seed_theory_production,
    update_sign_meanings,
)
from app.scripts.seed_theory_production import CORE_SECTIONS
from app.services import theory as theory_service
from app.services import theory_admin
from app.services.content_source import OptionDraft, QuestionDraft
from app.services.ingestion import publish_question
from app.storage.db import session_scope
from tests.theory_helper import student_client

_S4_SIGN_CODES = ["1.34", "3.16", "5.46", "2.3.1", "7.9"]  # real manifest codes across families


def _author(db) -> User:
    return db.scalar(select(User).where(User.telegram_id == "0"))


def _publish_sign(db, author, version):
    theory_admin.submit_sign_review(db, author, version.id)
    theory_admin.review_sign(db, author, version.id)
    theory_admin.publish_sign(db, author, version.id)


def _publish_marking(db, author, version):
    theory_admin.submit_marking_review(db, author, version.id)
    theory_admin.review_marking(db, author, version.id)
    theory_admin.publish_marking(db, author, version.id)


def _publish_gesture(db, author, version):
    theory_admin.submit_gesture_review(db, author, version.id)
    theory_admin.review_gesture(db, author, version.id)
    theory_admin.publish_gesture(db, author, version.id)


def _publish_light(db, author, version):
    theory_admin.submit_light_review(db, author, version.id)
    theory_admin.review_light(db, author, version.id)
    theory_admin.publish_light(db, author, version.id)


def _publish_article(db, author, version):
    theory_admin.submit_article_review(db, author, version.id)
    theory_admin.review_article(db, author, version.id)
    theory_admin.publish_article(db, author, version.id)


def _seed_demo_baseline(db, author) -> None:
    """A minimal, offline DEMO baseline to exercise S5 (slug/title normalise) + S7 (archive)."""
    # A demo section whose slug + title carry the DEMO marker (must be normalised to
    # 'yol-belgilari' with a clean title by the production seed).
    sec = theory_admin.create_section(
        db, author, slug="demo-yol-belgilari", title="Yo'l belgilari (DEMO)",
        subtitle="DEMO — placeholder", topic="road_signs", position=1,
    )
    theory_admin.publish_section(db, author, sec.id)
    av = theory_admin.create_article(
        db, author, section_id=sec.id, slug="demo-kirish", kind="lesson", position=1
    )
    av = theory_admin.edit_article(
        db, author, av.article_id,
        theory_admin.ArticleContentInput(
            title="Kirish (DEMO)", summary="DEMO", ai_assisted=True,
            blocks=[theory_admin.BlockInput(type="text", body="DEMO matn.")],
        ),
    )
    _publish_article(db, author, av)
    # DEMO catalogue entries (must be archived out of the published catalogues).
    mv = theory_admin.create_marking(db, author, group="horizontal", code="DEMO-1.1")
    mv = theory_admin.edit_marking(
        db, author, mv.road_marking_id,
        theory_admin.MarkingContentInput(name="DEMO chiziq", meaning="DEMO", ai_assisted=True),
    )
    _publish_marking(db, author, mv)
    gv = theory_admin.create_gesture(db, author, code="DEMO-G1")
    gv = theory_admin.edit_gesture(
        db, author, gv.gesture_id,
        theory_admin.GestureContentInput(name="DEMO ishora", ai_assisted=True),
    )
    _publish_gesture(db, author, gv)
    lv = theory_admin.create_light(db, author, kind="main")
    lv = theory_admin.edit_light(
        db, author, lv.light_id,
        theory_admin.LightContentInput(title="DEMO svetofor holati", meaning="DEMO",
                                       ai_assisted=True),
    )
    _publish_light(db, author, lv)


def _seed_all() -> None:
    """Full production content pipeline (idempotent), runnable offline on sqlite."""
    seed_invented_questions.run()  # author + 'YHQ' rule + topic MCQs
    with session_scope() as db:
        author = _author(db)
        # A published road_signs question so the road-signs lesson can link (S6).
        publish_question(
            db,
            QuestionDraft(
                category=Category.B, topic=Topic.ROAD_SIGNS,
                prompt="Ushbu belgi nimani bildiradi (namuna)?",
                short_explanation="Belgi namunasi.",
                options=[
                    OptionDraft(text="To'g'ri", is_correct=True, explanation="To'g'ri."),
                    OptionDraft(text="Noto'g'ri", is_correct=False, explanation="Noto'g'ri."),
                ],
                rule_code="YHQ", is_sign_question=True, difficulty=1, ai_assisted=True,
                language=Language.UZ, sources=[],
            ),
            author,
        )
        # A few real manifest-coded signs so S4 enrichment has something to verify.
        fam = {"1.34": "warning", "3.16": "prohibitory", "5.46": "information",
               "2.3.1": "priority", "7.9": "service"}
        for code in _S4_SIGN_CODES:
            v = theory_admin.create_sign(db, author, official_code=code, family=fam[code])
            v = theory_admin.edit_sign(
                db, author, v.road_sign_id,
                theory_admin.SignContentInput(name=code, meaning="x", ai_assisted=True),
            )
            _publish_sign(db, author, v)
        _seed_demo_baseline(db, author)

    seed_theory_production.run()
    update_sign_meanings.run()


# --------------------------------------------------------------------------- #
# Acceptance #2 — catalogues, sections, articles, links, sign meanings
# --------------------------------------------------------------------------- #
def test_acceptance_2_catalogues_sections_and_links(client):
    _seed_all()
    with session_scope() as db:
        gestures = theory_service.list_gestures(db)
        lights = theory_service.list_lights(db)
        markings = theory_service.list_markings(db)

        assert len(gestures) >= 4, gestures
        assert len(lights) >= 5, lights
        assert len(markings) >= 8, markings

        # Gestures: non-empty Uzbek content, no DEMO code.
        for g in gestures:
            assert g["code"] and "DEMO" not in g["code"].upper()
            d = theory_service.get_gesture(db, g["id"])
            assert d["name"].strip() and d["allowed"].strip() and d["forbidden"].strip()

        # Markings: non-empty meaning, no DEMO code.
        for m in markings:
            assert not (m["code"] and "DEMO" in m["code"].upper())
            d = theory_service.get_marking(db, m["id"])
            assert d["name"].strip() and d["meaning"].strip()

        # Lights: non-empty meaning/movement, no DEMO title.
        for light in lights:
            d = theory_service.get_light(db, light["id"])
            assert d["title"].strip() and "DEMO" not in d["title"].upper()
            assert d["meaning"].strip()

        # Sections: >=12, none with "(DEMO)" in the title; demo slug normalised away.
        sections = theory_service.list_sections(db)
        assert len(sections) >= 12, len(sections)
        slugs = {s["slug"] for s in sections}
        for s in sections:
            assert "(DEMO)" not in (s.get("title") or ""), s
        assert "demo-yol-belgilari" not in slugs
        assert "yol-belgilari" in slugs

        # Every core section has >=1 published lesson article, each with >=1 linked question.
        for spec in CORE_SECTIONS:
            detail = theory_service.get_section(db, spec["slug"])
            arts = detail["articles"]
            assert arts, f"no published article in {spec['slug']}"
            assert any(
                theory_service.get_article(db, a["slug"])["linked_question_count"] >= 1
                for a in arts
            ), f"no linked question in {spec['slug']}"

        # Sign meanings are full sentences (len > len(name)+1) with a driver action (S4).
        for code in _S4_SIGN_CODES:
            s = theory_service.get_sign(db, code)
            assert len(s["meaning"]) > len(s["name"]) + 1, (code, s["meaning"])
            assert s["driver_action"].strip(), code


def test_acceptance_2_no_demo_codes_remain_published(client):
    _seed_all()
    with session_scope() as db:
        # Archived DEMO catalogue entries must not surface in the published catalogues.
        assert all(
            not (m["code"] and "DEMO" in m["code"].upper())
            for m in theory_service.list_markings(db)
        )
        assert all(
            not (g["code"] and "DEMO" in g["code"].upper())
            for g in theory_service.list_gestures(db)
        )
        assert all(
            "DEMO" not in (theory_service.get_light(db, light["id"])["title"] or "").upper()
            for light in theory_service.list_lights(db)
        )
        # No published section/article title still carries "(DEMO)".
        for s in theory_service.list_sections(db):
            detail = theory_service.get_section(db, s["slug"])
            for a in detail["articles"]:
                assert "(DEMO)" not in (a["title"] or "")


# --------------------------------------------------------------------------- #
# Acceptance #3 — article-linked practice start has NO correct-answer leak
# --------------------------------------------------------------------------- #
def test_acceptance_3_theory_practice_start_no_answer_leak(client):
    _seed_all()
    with session_scope() as db:
        article = theory_service.get_article(db, "svetofor-signallari-asosi")
        article_id = article["id"]
        assert article["linked_question_count"] >= 1

    c = student_client(client)
    start = c.post(
        "/api/theory/practice/start",
        json={"target_type": "article", "target_id": article_id},
    )
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["source"] == "theory"
    assert body["questions_total"] >= 1
    for q in body["questions"]:
        assert q["options"]
        for opt in q["options"]:
            assert "is_correct" not in opt
            assert "explanation" not in opt
        assert "rule" not in q
        assert "short_explanation" not in q
        assert "correct_option_id" not in q
    # RAW-BYTES no-leak across the whole payload.
    for banned in ("is_correct", "explanation", "short_explanation", "correct_option_id"):
        assert banned not in start.text, banned


def test_acceptance_3_student_sees_published_only(client):
    _seed_all()
    c = student_client(client)
    # Archived DEMO article slug must 404 for students (published-only reads).
    assert c.get("/api/theory/articles/demo-kirish").status_code == 404
    # A real production lesson resolves.
    assert c.get("/api/theory/articles/svetofor-signallari-asosi").status_code == 200
