"""Seed clearly-marked DEMO category-B questions WITH IMAGES through the REAL pipeline.

Usage:
    python -m app.scripts.seed_demo_with_images

Purpose
-------
Demo the image feature end-to-end in production: each question gets an image that is
stored via the real ``MediaStorage`` adapter (the Railway S3-compatible bucket in prod,
the in-memory fake locally) and served through the content-addressed media route. Every
question is a proper *published* ``QuestionVersion`` created through the same ingestion
publish path used by ``seed_demo.py``.

Content policy (identical to seed_demo / seed_theory_demo)
----------------------------------------------------------
- Every prompt is prefixed ``DEMO:`` and is obviously dummy content.
- Versions are ``ai_assisted=True`` and linked to an obviously-fake ``DEMO-YHQ-1`` rule.
- Images are original placeholders (picsum.photos random photos, or a locally generated
  Pillow placeholder). They are NEVER claimed to be official YHQ road-sign graphics; the
  ``uz`` alt-text explicitly says so.

Idempotent
----------
Re-running skips any question whose exact demo prompt already exists. A JSON summary of
created/skipped counts is logged and printed at the end.

Reused (no logic duplicated / no APIs invented):
- app/services/ingestion.py :: upsert_rule, publish_question
- app/services/media.py     :: ingest_upload  (the SAME validate + WebP re-encode +
                               content_hash + get_media_storage().put + QuestionMedia
                               creation used by the admin upload route)
- app/services/content_source.py :: QuestionDraft, OptionDraft, RuleDraft, SourceRefDraft
- app/scripts/seed_demo.py  :: seed-author convention (telegram_id "0")
- app/storage/db.py         :: session_scope
"""

from __future__ import annotations

import io
import json
import urllib.request

from sqlalchemy import select

from app.domain.enums import (
    Category,
    Language,
    SourceKind,
    Topic,
    VersionStatus,
    AdminRole,
)
from app.domain.models import QuestionVersion, QuestionVersionTranslation, User
from app.observability.logging import configure_logging, log_event
from app.services.content_source import OptionDraft, QuestionDraft, RuleDraft, SourceRefDraft
from app.services.ingestion import publish_question, upsert_rule
from app.services.media import ingest_upload
from app.storage.db import session_scope

SEED_AUTHOR_TELEGRAM_ID = "0"

_DEMO_RULE_CODE = "DEMO-YHQ-1"
_DEMO_RULE_TEXT = (
    "DEMO qoida matni — bu HAQIQIY YHQ bandi EMAS. Faqat rasm xususiyatini "
    "namoyish qilish uchun. Rasmiy manbadan tekshirilishi shart."
)
_DEMO_SOURCE_NOTE = (
    "Original DEMO content authored for prava-bot image-feature demo — "
    "not an official exam question; image is a placeholder, not an official sign."
)
_ALT_TEXT_UZ = "DEMO rasm — namuna tasvir, rasmiy YHQ belgisi EMAS."

_PICSUM_URL = "https://picsum.photos/seed/{slug}/640/400"
_FETCH_TIMEOUT_SECONDS = 8

# Verified real road-sign images (Wikimedia Commons, resolved by filename via
# Special:FilePath which renders a PNG for SVG sources). Copyright is not a concern
# for this deployment (owner directive); these are still presented as demo content.
import urllib.parse

_WIKI_FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width=640"
_SIGN_IMAGE_FILES = {
    "demo-sign-stop": "Vienna_Convention_road_sign_B2a.svg",
    "demo-sign-noentry": "Italian_traffic_signs_-_divieto_di_transito.svg",
    "demo-sign-pedestrian": "Italian_traffic_signs_-_attraversamento_pedonale.svg",
    "demo-sign-speed50": "Italian_traffic_signs_-_limite_di_velocità_50.svg",
    "demo-sign-yield": "Italian_traffic_signs_-_dare_precedenza.svg",
}


def _sign_url(slug: str) -> str | None:
    name = _SIGN_IMAGE_FILES.get(slug)
    if not name:
        return None
    return _WIKI_FILEPATH.format(name=urllib.parse.quote(name))


# --------------------------------------------------------------------------- #
# Image acquisition: real sign (Wikimedia) -> picsum -> offline Pillow fallback.
# --------------------------------------------------------------------------- #
def _fallback_placeholder(label: str, slug: str) -> bytes:
    """Deterministic colored PNG placeholder with the demo label (offline safe)."""
    from PIL import Image, ImageDraw

    # Deterministic background colour derived from the slug (stable across re-runs).
    h = abs(hash(slug))
    bg = (60 + h % 150, 60 + (h // 7) % 150, 60 + (h // 13) % 150)
    img = Image.new("RGB", (640, 400), bg)
    draw = ImageDraw.Draw(img)
    text = f"DEMO\n{label}"
    draw.multiline_text((24, 24), text, fill=(255, 255, 255))
    draw.multiline_text((24, 360), "namuna rasm — rasmiy belgi EMAS", fill=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _try_url(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "prava-bot-demo-seed/1.0"})
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_SECONDS) as resp:  # noqa: S310
            data = resp.read()
        return data or None
    except Exception as exc:  # noqa: BLE001 — any network/timeout error -> next source
        log_event("seed_demo_images_fetch_skip", url=url, error=str(exc))
        return None


def _fetch_image_bytes(slug: str, label: str) -> tuple[bytes, str]:
    """Return (raw_bytes, origin): real sign image -> picsum photo -> Pillow placeholder."""
    sign_url = _sign_url(slug)
    if sign_url:
        data = _try_url(sign_url)
        if data:
            return data, "wikimedia_sign"
    data = _try_url(_PICSUM_URL.format(slug=slug))
    if data:
        return data, "picsum"
    return _fallback_placeholder(label, slug), "fallback"


# --------------------------------------------------------------------------- #
# Author (same convention as seed_demo.py)
# --------------------------------------------------------------------------- #
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


def _demo_rule_draft() -> RuleDraft:
    return RuleDraft(
        code=_DEMO_RULE_CODE,
        text=_DEMO_RULE_TEXT,
        title="DEMO qoida (namuna)",
        source_url="",
        language=Language.UZ,
    )


def _demo_sources() -> list[SourceRefDraft]:
    return [SourceRefDraft(url="", note=_DEMO_SOURCE_NOTE, kind=SourceKind.OTHER)]


def _q(slug, topic, prompt, short, options, *, sign=False, difficulty=1):
    """Build a DEMO QuestionDraft (category B, uz, ai_assisted)."""
    return slug, QuestionDraft(
        category=Category.B,
        topic=topic,
        prompt=prompt,
        short_explanation=short,
        options=[OptionDraft(text=t, is_correct=c, explanation=e) for (t, c, e) in options],
        rule_code=_DEMO_RULE_CODE,
        is_sign_question=sign,
        difficulty=difficulty,
        ai_assisted=True,
        language=Language.UZ,
        sources=_demo_sources(),
    )


# 8 DEMO questions. Slugs in _SIGN_IMAGE_FILES get a real Wikimedia sign image and
# coherent options; the rest use a picsum photo. >=3 are is_sign_question=True.
_DEMO_QUESTIONS = [
    _q("demo-sign-stop", Topic.ROAD_SIGNS,
       "DEMO: Ushbu belgi (rasmda) haydovchidan nimani talab qiladi?",
       "DEMO namuna: 'STOP' belgisi — to'liq to'xtashni talab qiladi (namuna izoh).",
       [("To'xtash", True, "DEMO: 'STOP' belgisi to'liq to'xtashni bildiradi (namuna)."),
        ("Davom etish", False, "DEMO: noto'g'ri — belgi to'xtashni talab qiladi."),
        ("Tezlashish", False, "DEMO: noto'g'ri — belgi to'xtashni talab qiladi.")],
       sign=True, difficulty=1),
    _q("demo-sign-noentry", Topic.ROAD_SIGNS,
       "DEMO: Rasmdagi belgi nimani bildiradi?",
       "DEMO namuna: harakatlanish taqiqlangan (namuna izoh).",
       [("Harakatlanish taqiqlangan", True, "DEMO: bu belgi kirishni taqiqlaydi (namuna)."),
        ("Harakat ruxsat etilgan", False, "DEMO: noto'g'ri — bu taqiqlovchi belgi."),
        ("Faqat yuk mashinalari", False, "DEMO: noto'g'ri — bu taqiqlovchi belgi.")],
       sign=True, difficulty=1),
    _q("demo-sign-pedestrian", Topic.ROAD_SIGNS,
       "DEMO: Rasmdagi belgi nimani bildiradi?",
       "DEMO namuna: piyodalar o'tish joyi (namuna izoh).",
       [("Piyodalar o'tish joyi", True, "DEMO: belgi piyoda o'tish joyini bildiradi (namuna)."),
        ("Avtobus bekati", False, "DEMO: noto'g'ri variant (namuna)."),
        ("Bolalar", False, "DEMO: noto'g'ri variant (namuna).")],
       sign=True, difficulty=1),
    _q("demo-sign-speed50", Topic.SPEED_DISTANCE,
       "DEMO: Rasmdagi belgi bo'yicha ruxsat etilgan eng katta tezlik qancha (namuna)?",
       "DEMO namuna: '50' tezlik cheklovi belgisi (namuna izoh).",
       [("50 km/soat", True, "DEMO: belgi 50 km/soat cheklovini bildiradi (namuna)."),
        ("90 km/soat", False, "DEMO: noto'g'ri variant (namuna)."),
        ("Cheklov yo'q", False, "DEMO: noto'g'ri variant (namuna).")],
       sign=True, difficulty=1),
    _q("demo-sign-yield", Topic.INTERSECTIONS,
       "DEMO: Rasmdagi belgi haydovchidan nimani talab qiladi?",
       "DEMO namuna: 'yo'l bering' belgisi (namuna izoh).",
       [("Yo'l berish", True, "DEMO: belgi boshqa harakatga yo'l berishni bildiradi (namuna)."),
        ("Imtiyozga ega bo'lish", False, "DEMO: noto'g'ri variant (namuna)."),
        ("To'xtash shart", False, "DEMO: noto'g'ri — bu 'STOP' emas (namuna).")],
       sign=True, difficulty=2),
    _q("demo-signal-delta", Topic.SIGNALS,
       "DEMO: Namunaviy svetofor rasmida qaysi harakat shartli to'g'ri deb belgilangan?",
       "DEMO namuna — haqiqiy signal qoidasi emas.",
       [("DEMO: to'xtash", True, "DEMO: shartli to'g'ri (namuna)."),
        ("DEMO: davom etish", False, "DEMO: namuna uchun noto'g'ri variant."),
        ("DEMO: tezlashish", False, "DEMO: namuna uchun noto'g'ri variant.")],
       difficulty=1),
    _q("demo-marking-echo", Topic.ROAD_MARKINGS,
       "DEMO: Rasmda ko'rsatilgan namunaviy chiziq haqida shartli savol.",
       "DEMO namuna — haqiqiy belgilanish qoidasi emas.",
       [("DEMO: kesib o'tish mumkin emas", True, "DEMO: shartli to'g'ri (namuna)."),
        ("DEMO: kesib o'tish mumkin", False, "DEMO: namuna uchun noto'g'ri variant.")],
       difficulty=2),
    _q("demo-intersection-foxtrot", Topic.INTERSECTIONS,
       "DEMO: Namunaviy chorraha rasmida kim shartli imtiyozga ega deb belgilaymiz?",
       "DEMO namuna — haqiqiy imtiyoz qoidasi emas.",
       [("DEMO: bosh yo'ldagi", True, "DEMO: shartli to'g'ri (namuna)."),
        ("DEMO: ikkilamchi yo'ldagi", False, "DEMO: namuna uchun noto'g'ri variant."),
        ("DEMO: hech kim", False, "DEMO: namuna uchun noto'g'ri variant.")],
       difficulty=2),
]


def run() -> dict:
    configure_logging()
    created_questions = 0
    created_media = 0
    skipped = 0
    origins: dict[str, int] = {"picsum": 0, "fallback": 0}

    with session_scope() as db:
        author = ensure_seed_author(db)
        upsert_rule(db, _demo_rule_draft())

        # Existing demo prompts -> idempotency skip set.
        existing_prompts = set(
            db.scalars(
                select(QuestionVersionTranslation.prompt).where(
                    QuestionVersionTranslation.prompt.like("DEMO:%")
                )
            ).all()
        )

        for slug, draft in _DEMO_QUESTIONS:
            if draft.prompt in existing_prompts:
                skipped += 1
                continue

            raw, origin = _fetch_image_bytes(slug, draft.topic.value)
            # SAME pipeline the admin upload route uses: validate + re-encode to WebP +
            # content_hash + get_media_storage().put + QuestionMedia (+ uz alt-text).
            media = ingest_upload(
                db,
                raw=raw,
                filename=f"{slug}.img",
                author=author,
                alt_text_uz=_ALT_TEXT_UZ,
            )
            created_media += 1
            origins[origin] = origins.get(origin, 0) + 1

            question = publish_question(db, draft, author)
            version = db.get(QuestionVersion, question.current_version_id)
            version.media_id = media.id
            db.flush()
            created_questions += 1

    summary = {
        "questions_created": created_questions,
        "media_created": created_media,
        "skipped": skipped,
        "image_origins": origins,
        "total_defined": len(_DEMO_QUESTIONS),
    }
    log_event("seed_demo_with_images_completed", **summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
