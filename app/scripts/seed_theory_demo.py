"""Seed a SMALL set of clearly-marked DEMO / original Theory content (docs/spec/14, 15).

CRITICAL (verification policy): this inserts ONLY placeholder demo content — it does NOT
hard-code real/unverified YHQ sign numbers, speed limits, controller gestures, or
first-aid facts. Every item is ``ai_assisted`` demo, uses obviously-fake ``DEMO-*`` codes,
and its text states it must be replaced by admin-authored + verified content. First-aid is
a single placeholder article noting content requires medical review.

Usage:
    python -m app.scripts.seed_theory_demo

Idempotent-ish: skips if any theory sections already exist.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.domain.enums import AdminRole
from app.domain.models import TheorySection, User
from app.observability.logging import configure_logging, log_event
from app.services import theory_admin
from app.storage.db import session_scope

SEED_AUTHOR_TELEGRAM_ID = "0"

_DEMO_NOTE = "DEMO — original placeholder. Rasmiy YHQ manbasidan tekshirilishi shart."


def ensure_seed_author(db) -> User:
    author = db.scalar(select(User).where(User.telegram_id == SEED_AUTHOR_TELEGRAM_ID))
    if author is None:
        author = User(
            telegram_id=SEED_AUTHOR_TELEGRAM_ID,
            first_name="Seed",
            last_name="Author",
            admin_role=AdminRole.CONTENT_AUTHOR,
        )
        db.add(author)
        db.flush()
    return author


def _publish_article(db, author, version):
    theory_admin.submit_article_review(db, author, version.id)
    theory_admin.review_article(db, author, version.id)
    theory_admin.publish_article(db, author, version.id)


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


def _ensure_demo_rule(db, author):
    from app.services import rules_admin

    from app.domain.models import Rule

    existing = db.scalar(select(Rule).where(Rule.code == "YHQ-DEMO:1"))
    if existing is not None:
        return existing
    return rules_admin.create_rule(
        db, author, code="YHQ-DEMO:1",
        text="DEMO qoida matni — bu haqiqiy YHQ bandi EMAS. Tekshirilishi shart.",
        title="DEMO qoida",
        source_url="",
    )


def run() -> dict:
    configure_logging()
    with session_scope() as db:
        if db.scalar(select(func.count(TheorySection.id))):
            log_event("seed_theory_demo_skipped", reason="sections_exist")
            return {"skipped": True}

        author = ensure_seed_author(db)
        _ensure_demo_rule(db, author)

        # --- Sections ---
        signs_section = theory_admin.create_section(
            db, author, slug="demo-yol-belgilari",
            title="Yo'l belgilari (DEMO)", subtitle=_DEMO_NOTE, topic="road_signs", position=1,
        )
        theory_admin.publish_section(db, author, signs_section.id)

        lights_section = theory_admin.create_section(
            db, author, slug="demo-svetofor",
            title="Svetofor signallari (DEMO)", subtitle=_DEMO_NOTE, topic="signals", position=2,
        )
        theory_admin.publish_section(db, author, lights_section.id)

        first_aid_section = theory_admin.create_section(
            db, author, slug="demo-birinchi-yordam",
            title="Birinchi yordam (DEMO)", subtitle=_DEMO_NOTE,
            topic="emergencies_first_aid", position=3,
        )
        theory_admin.publish_section(db, author, first_aid_section.id)

        # --- Demo lesson article (rule -> diagram -> example -> mistake -> practice) ---
        lesson_v = theory_admin.create_article(
            db, author, section_id=signs_section.id, slug="demo-belgilarga-kirish",
            kind="lesson", position=1,
        )
        theory_admin.edit_article(
            db, author, lesson_v.article_id,
            theory_admin.ArticleContentInput(
                title="Yo'l belgilariga kirish (DEMO)",
                summary=_DEMO_NOTE,
                ai_assisted=True,
                blocks=[
                    theory_admin.BlockInput(type="text", body="DEMO: bu namunaviy dars matni."),
                    theory_admin.BlockInput(
                        type="rule_callout", body="DEMO qoidaga havola.", rule_code="YHQ-DEMO:1"
                    ),
                    theory_admin.BlockInput(type="warning", body="DEMO ogohlantirish bloki."),
                    theory_admin.BlockInput(type="memory_tip", body="DEMO eslab qolish maslahati."),
                    theory_admin.BlockInput(
                        type="table", body="",
                        data={"headers": ["Ustun A", "Ustun B"], "rows": [["1", "2"]]},
                    ),
                ],
                rule_codes=["YHQ-DEMO:1"],
            ),
        )
        _publish_article(db, author, lesson_v)

        # --- First-aid placeholder (must be medically reviewed) ---
        fa_v = theory_admin.create_article(
            db, author, section_id=first_aid_section.id, slug="demo-birinchi-yordam-kirish",
            kind="reference", position=1,
        )
        theory_admin.edit_article(
            db, author, fa_v.article_id,
            theory_admin.ArticleContentInput(
                title="Birinchi yordam (DEMO placeholder)",
                summary="DIQQAT: bu joy tibbiy mutaxassis tomonidan tekshirilgan kontent bilan "
                        "to'ldirilishi shart. Hozircha hech qanday tibbiy fakt keltirilmagan.",
                ai_assisted=True,
                blocks=[
                    theory_admin.BlockInput(
                        type="warning",
                        body="Bu bo'lim tibbiy jihatdan tekshirilmagan — namuna sifatida.",
                    ),
                ],
            ),
        )
        _publish_article(db, author, fa_v)

        # --- Demo signs across families ---
        sign_specs = [
            ("DEMO-W1", "warning", "DEMO ogohlantiruvchi belgi"),
            ("DEMO-P1", "prohibitory", "DEMO taqiqlovchi belgi"),
            ("DEMO-M1", "mandatory", "DEMO buyuruvchi belgi"),
            ("DEMO-PR1", "priority", "DEMO imtiyoz belgisi"),
        ]
        sign_ids = []
        for code, family, name in sign_specs:
            v = theory_admin.create_sign(db, author, official_code=code, family=family)
            theory_admin.edit_sign(
                db, author, v.road_sign_id,
                theory_admin.SignContentInput(
                    name=name, meaning=f"{_DEMO_NOTE}", driver_action="DEMO: haydovchi harakati.",
                    keywords="demo namuna belgi", ai_assisted=True, rule_codes=["YHQ-DEMO:1"],
                ),
            )
            _publish_sign(db, author, v)
            sign_ids.append(v.road_sign_id)

        # --- Demo marking / gesture / light ---
        mv = theory_admin.create_marking(db, author, group="horizontal", code="DEMO-1.1")
        theory_admin.edit_marking(
            db, author, mv.road_marking_id,
            theory_admin.MarkingContentInput(
                name="DEMO chiziq", meaning=_DEMO_NOTE, can_cross="DEMO", keywords="demo chiziq",
                ai_assisted=True,
            ),
        )
        _publish_marking(db, author, mv)

        gv = theory_admin.create_gesture(db, author, code="DEMO-G1")
        theory_admin.edit_gesture(
            db, author, gv.gesture_id,
            theory_admin.GestureContentInput(
                name="DEMO ishora", position_desc="DEMO holat", allowed="DEMO", forbidden="DEMO",
                keywords="demo ishora regulirovshchik", ai_assisted=True,
            ),
        )
        _publish_gesture(db, author, gv)

        lv = theory_admin.create_light(db, author, kind="main")
        theory_admin.edit_light(
            db, author, lv.light_id,
            theory_admin.LightContentInput(
                title="DEMO svetofor holati", meaning=_DEMO_NOTE, movement_permitted="DEMO",
                keywords="demo svetofor signal", ai_assisted=True,
            ),
        )
        _publish_light(db, author, lv)

        result = {
            "sections": 3, "articles": 2, "signs": len(sign_ids),
            "markings": 1, "gestures": 1, "lights": 1,
        }
        log_event("seed_theory_demo_completed", **result)
        return result


if __name__ == "__main__":
    print(run())
