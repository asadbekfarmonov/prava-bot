"""Clean up demo content and build real sign-recognition practice questions.

1. Rename the placeholder Theory sections (drop the "(DEMO)" labels).
2. Archive all demo practice questions (prompt starts with "DEMO:") so they no longer
   appear in practice / mock (kept in DB, not hard-deleted, to preserve any attempt FKs).
3. Create one REAL sign-recognition question per published RoadSign, reusing the sign's
   real image: "Ushbu yo'l belgisi qaysi turkumga kiradi?" with the 7 sign families as
   options (correct = the sign's family). Family is derivable from the sign's shape/colour,
   so this is a legitimate, verifiable recognition question (no invented legal meanings).

Usage:  python -m app.scripts.seed_sign_questions
Idempotent: skips signs that already have a generated question (by media reuse).
"""

from __future__ import annotations

import json
import random

from sqlalchemy import select

from app.domain.enums import AdminRole, Category, Language, Topic, VersionStatus
from app.domain.models import (
    Question,
    QuestionVersion,
    QuestionVersionTranslation,
    RoadSign,
    RoadSignVersion,
    TheorySection,
    TheorySectionTranslation,
    User,
)
from app.observability.logging import configure_logging, log_event
from app.services import authoring
from app.services.content_source import OptionDraft, QuestionDraft
from app.services.ingestion import publish_question
from app.storage.db import session_scope

SEED_AUTHOR_TELEGRAM_ID = "0"
_RULE_CODE = "YHQ:BELGILAR"

FAMILY_UZ = {
    "warning": "Ogohlantiruvchi belgilar",
    "priority": "Imtiyoz belgilari",
    "prohibitory": "Taqiqlovchi belgilar",
    "mandatory": "Buyuruvchi belgilar",
    "information": "Axborot-ko'rsatkich belgilar",
    "service": "Servis belgilari",
    "additional_plate": "Qo'shimcha axborot belgilari",
}
_ALL_FAMILIES = list(FAMILY_UZ.keys())

_SECTION_RENAMES = {
    "demo-yol-belgilari": ("Yo'l belgilari", "Belgilar turkumlari va tasvirlari"),
    "demo-svetofor": ("Svetofor signallari", "Chiroq va regulirovshchik signallari"),
    "demo-birinchi-yordam": (
        "Birinchi yordam",
        "Favqulodda vaziyatlar — tibbiy jihatdan tekshirilishi kerak",
    ),
}

_QPROMPT = "Ushbu yo'l belgisi qaysi turkumga kiradi?"


def ensure_seed_author(db) -> User:
    author = db.scalar(select(User).where(User.telegram_id == SEED_AUTHOR_TELEGRAM_ID))
    if author is None:
        author = User(
            telegram_id=SEED_AUTHOR_TELEGRAM_ID, first_name="Seed", last_name="Author",
            admin_role=AdminRole.CONTENT_AUTHOR,
        )
        db.add(author)
        db.flush()
    return author


def _rename_sections(db) -> int:
    n = 0
    for slug, (title, subtitle) in _SECTION_RENAMES.items():
        sec = db.scalar(select(TheorySection).where(TheorySection.slug == slug))
        if sec is None:
            continue
        for tr in db.scalars(
            select(TheorySectionTranslation).where(
                TheorySectionTranslation.section_id == sec.id,
                TheorySectionTranslation.language == Language.UZ,
            )
        ):
            tr.title = title
            tr.subtitle = subtitle
            n += 1
    return n


def _archive_demo_questions(db, author) -> int:
    # Distinct question ids whose (any) translation prompt starts with 'DEMO:'.
    version_ids = db.scalars(
        select(QuestionVersionTranslation.question_version_id).where(
            QuestionVersionTranslation.prompt.like("DEMO:%")
        )
    )
    q_ids = set()
    for vid in version_ids:
        v = db.get(QuestionVersion, vid)
        if v is not None:
            q_ids.add(v.question_id)
    archived = 0
    for qid in q_ids:
        q = db.get(Question, qid)
        if q is None or q.lifecycle_status == VersionStatus.ARCHIVED:
            continue
        try:
            authoring.archive_question(db, author, qid)
            archived += 1
        except Exception as exc:  # noqa: BLE001
            log_event("archive_demo_question_error", question_id=qid, error=str(exc))
    return archived


def _sign_media_ids_in_use(db) -> set[str]:
    """media_ids already referenced by a non-archived question version (idempotency)."""
    used = set()
    for v in db.scalars(
        select(QuestionVersion).where(QuestionVersion.media_id.is_not(None))
    ):
        q = db.get(Question, v.question_id)
        if q is not None and q.lifecycle_status != VersionStatus.ARCHIVED:
            used.add(v.media_id)
    return used


def _make_options(correct_family: str, rng: random.Random) -> list[OptionDraft]:
    distractors = [f for f in _ALL_FAMILIES if f != correct_family]
    rng.shuffle(distractors)
    chosen = [correct_family] + distractors[:3]
    rng.shuffle(chosen)
    opts = []
    for fam in chosen:
        is_correct = fam == correct_family
        expl = (
            f"To'g'ri — bu belgi '{FAMILY_UZ[correct_family]}' turkumiga kiradi."
            if is_correct
            else f"Noto'g'ri — bu belgi '{FAMILY_UZ[correct_family]}' turkumiga kiradi."
        )
        opts.append(OptionDraft(text=FAMILY_UZ[fam], is_correct=is_correct, explanation=expl))
    return opts


def run() -> dict:
    configure_logging()
    renamed = 0
    archived = 0
    created = 0
    skipped = 0
    with session_scope() as db:
        author = ensure_seed_author(db)
        renamed = _rename_sections(db)
        archived = _archive_demo_questions(db, author)

        used_media = _sign_media_ids_in_use(db)
        # Published signs -> real recognition questions reusing the sign image.
        signs = list(db.scalars(select(RoadSign).where(RoadSign.current_version_id.is_not(None))))
        for sign in signs:
            v = db.get(RoadSignVersion, sign.current_version_id)
            if v is None or v.media_id is None:
                continue
            if v.media_id in used_media:
                skipped += 1
                continue
            rng = random.Random(sign.official_code)  # deterministic option order
            family = sign.family.value
            draft = QuestionDraft(
                category=Category.B,
                topic=Topic.ROAD_SIGNS,
                prompt=_QPROMPT,
                short_explanation=(
                    f"Belgi shakli va rangi turkumini ko'rsatadi: "
                    f"{FAMILY_UZ[family]}."
                ),
                options=_make_options(family, rng),
                rule_code=_RULE_CODE,
                is_sign_question=True,
                difficulty=1,
                ai_assisted=True,
                language=Language.UZ,
                sources=[],
            )
            try:
                q = publish_question(db, draft, author)
                qv = db.get(QuestionVersion, q.current_version_id)
                qv.media_id = v.media_id
                db.flush()
                used_media.add(v.media_id)
                created += 1
            except Exception as exc:  # noqa: BLE001
                log_event("sign_question_create_error", code=sign.official_code, error=str(exc))
    result = {"sections_renamed": renamed, "demo_questions_archived": archived,
              "sign_questions_created": created, "skipped": skipped}
    log_event("seed_sign_questions_completed", **result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
