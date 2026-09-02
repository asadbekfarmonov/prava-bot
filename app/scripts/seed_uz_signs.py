"""Replace demo road signs with the real Uzbekistan sign set sourced from Wikimedia Commons.

- Deletes existing RoadSign catalogue entries (the earlier DEMO signs).
- Loads every sign in app/scripts/uz_signs_manifest.json (code -> {file, family}),
  fetching the real image from Wikimedia Commons (Special:FilePath renders SVG->PNG),
  storing it through the real media pipeline (WebP, content-addressed), and publishing a
  RoadSign per code with the correct family (from the official code prefix).

Honesty / verification policy: images are real Uzbek sign diagrams from Wikimedia Commons
(CC-licensed). Sign NAMES/MEANINGS are NOT hard-coded as verified YHQ text — each meaning
field states it must be verified by an admin against the official YHQ source. Codes and
families come from the Commons filenames + standard Uzbek numbering, which is structural,
not invented.

Usage:  python -m app.scripts.seed_uz_signs
Idempotent: skips codes already present; safe to re-run.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from sqlalchemy import delete, select

from app.domain.enums import AdminRole
from app.domain.models import (
    RoadSign,
    RoadSignRule,
    RoadSignTranslation,
    RoadSignVersion,
    User,
)
from app.observability.logging import configure_logging, log_event
from app.services import rules_admin, theory_admin
from app.storage.db import session_scope

SEED_AUTHOR_TELEGRAM_ID = "0"
_MANIFEST = Path(__file__).with_name("uz_signs_manifest.json")
_RULE_CODE = "YHQ:BELGILAR"
_UA = {"User-Agent": "prava-bot-seed/1.0 (contact: dev)"}
_FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width=480"

FAMILY_UZ = {
    "warning": "Ogohlantiruvchi belgi",
    "priority": "Imtiyoz belgisi",
    "prohibitory": "Taqiqlovchi belgi",
    "mandatory": "Buyuruvchi belgi",
    "information": "Axborot-ko'rsatkich belgi",
    "service": "Servis belgisi",
    "additional_plate": "Qo'shimcha axborot belgisi",
}
_MEANING_NOTE = (
    "Rasm — Wikimedia Commons'dan olingan haqiqiy O'zbekiston yo'l belgisi tasviri. "
    "Belgining aniq ma'nosi rasmiy YHQ manbasidan admin tomonidan tekshirilishi shart."
)


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


def _ensure_rule(db, author):
    from app.domain.models import Rule
    existing = db.scalar(select(Rule).where(Rule.code == _RULE_CODE))
    if existing is not None:
        return existing
    return rules_admin.create_rule(
        db, author, code=_RULE_CODE,
        text="Yo'l belgilari bo'limi (namuna). Aniq bandlar rasmiy YHQ'dan tekshirilishi shart.",
        title="Yo'l belgilari", source_url="https://commons.wikimedia.org/",
    )


def _fetch_png(filename: str, tries: int = 6) -> bytes | None:
    url = _FILEPATH.format(name=urllib.parse.quote(filename))
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=40) as resp:  # noqa: S310
                data = resp.read()
            return data or None
        except urllib.error.HTTPError as exc:  # 429/5xx -> backoff
            if exc.code in (429, 500, 502, 503):
                time.sleep(4 * (i + 1))
                continue
            log_event("uz_signs_fetch_http_error", file=filename, code=exc.code)
            return None
        except Exception as exc:  # noqa: BLE001
            log_event("uz_signs_fetch_error", file=filename, error=str(exc))
            time.sleep(2 * (i + 1))
    return None


def _delete_existing_signs(db) -> int:
    """Remove all RoadSign catalogue entries (demo) + their child rows, FK-safe."""
    version_ids = list(db.scalars(select(RoadSignVersion.id)))
    n = len(list(db.scalars(select(RoadSign.id))))
    if version_ids:
        db.execute(delete(RoadSignRule).where(RoadSignRule.road_sign_version_id.in_(version_ids)))
        db.execute(delete(RoadSignTranslation).where(RoadSignTranslation.road_sign_version_id.in_(version_ids)))
    # Detach current_version_id before deleting versions to avoid FK issues.
    for s in db.scalars(select(RoadSign)):
        s.current_version_id = None
    db.flush()
    db.execute(delete(RoadSignVersion))
    db.execute(delete(RoadSign))
    db.flush()
    return n


def run() -> dict:
    configure_logging()
    from app.services.media import ingest_upload

    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    created = 0
    skipped = 0
    failed = 0
    with session_scope() as db:
        author = ensure_seed_author(db)
        _ensure_rule(db, author)
        removed = _delete_existing_signs(db)

        for code in sorted(manifest):
            entry = manifest[code]
            family = entry["family"]
            raw = _fetch_png(entry["file"])
            if not raw:
                failed += 1
                continue
            try:
                media = ingest_upload(
                    db, raw=raw, filename=f"uzsign-{code}.img", author=author,
                    alt_text_uz=f"{FAMILY_UZ.get(family, 'Yo\u2019l belgisi')} {code}",
                )
                v = theory_admin.create_sign(
                    db, author, official_code=code, family=family, media_id=media.id
                )
                theory_admin.edit_sign(
                    db, author, v.road_sign_id,
                    theory_admin.SignContentInput(
                        name=f"{FAMILY_UZ.get(family, 'Yo\u2019l belgisi')} {code}",
                        meaning=_MEANING_NOTE,
                        driver_action="Rasmiy YHQ manbasidan tekshirilishi kerak.",
                        keywords=f"{code} {family} yo'l belgisi",
                        media_id=media.id, ai_assisted=True, rule_codes=[_RULE_CODE],
                    ),
                )
                theory_admin.submit_sign_review(db, author, v.id)
                theory_admin.review_sign(db, author, v.id)
                theory_admin.publish_sign(db, author, v.id)
                created += 1
            except Exception as exc:  # noqa: BLE001
                log_event("uz_signs_create_error", code=code, error=str(exc))
                failed += 1
            time.sleep(0.25)

    result = {"removed_existing": removed, "created": created, "failed": failed,
              "skipped": skipped, "manifest_total": len(manifest)}
    log_event("seed_uz_signs_completed", **result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
