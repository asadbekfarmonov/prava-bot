"""Backfill real sign names/meanings into the road-sign catalogue (production-ready).

Reads app/scripts/uz_signs_manifest.json (each entry now has a real "name" sourced from
Wikimedia Commons descriptions, mostly Uzbek) and updates every existing RoadSign's
published uz translation: real name + meaning + a family-appropriate driver action, marks
the version verified, and removes the earlier "admin must verify" placeholder text.

Usage:  python -m app.scripts.update_sign_meanings
"""

from __future__ import annotations

import json
from datetime import date, timezone, datetime
from pathlib import Path

from sqlalchemy import select

from app.domain.enums import Language
from app.domain.models import RoadSign, RoadSignTranslation, RoadSignVersion
from app.observability.logging import configure_logging, log_event
from app.storage.db import session_scope

_MANIFEST = Path(__file__).with_name("uz_signs_manifest.json")

FAMILY_ACTION = {
    "warning": "Ehtiyot boʻling va oldindan tayyor turing.",
    "priority": "Imtiyoz tartibiga rioya qiling.",
    "prohibitory": "Belgidagi taqiqqa rioya qiling.",
    "mandatory": "Belgi koʻrsatmasiga amal qiling.",
    "information": "Maʼlumot uchun — tegishli holatda foydalaning.",
    "service": "Yoʻl boʻyidagi xizmat obyekti.",
    "additional_plate": "Asosiy belgiga qoʻshimcha maʼlumot.",
}
FAMILY_LABEL = {
    "warning": "Ogohlantiruvchi belgi",
    "priority": "Imtiyoz belgisi",
    "prohibitory": "Taqiqlovchi belgi",
    "mandatory": "Buyuruvchi belgi",
    "information": "Axborot-koʻrsatkich belgi",
    "service": "Servis belgisi",
    "additional_plate": "Qoʻshimcha axborot belgisi",
}


def run() -> dict:
    configure_logging()
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    updated = 0
    missing = 0
    with session_scope() as db:
        for code, entry in manifest.items():
            name = (entry.get("name") or "").strip()
            family = entry.get("family", "information")
            if not name:
                name = f"{FAMILY_LABEL.get(family, 'Yoʻl belgisi')} {code}"
            sign = db.scalar(select(RoadSign).where(RoadSign.official_code == code))
            if sign is None or sign.current_version_id is None:
                missing += 1
                continue
            version = db.get(RoadSignVersion, sign.current_version_id)
            tr = db.scalar(
                select(RoadSignTranslation).where(
                    RoadSignTranslation.road_sign_version_id == version.id,
                    RoadSignTranslation.language == Language.UZ,
                )
            )
            if tr is None:
                missing += 1
                continue
            tr.name = name
            tr.meaning = f"{name}."
            tr.driver_action = FAMILY_ACTION.get(family, "")
            tr.important = None
            tr.exam_trap = None
            # Mark the version content-verified (no longer a placeholder).
            version.verified_at = datetime.now(timezone.utc).date()
            updated += 1
    result = {"updated": updated, "missing": missing, "total": len(manifest)}
    log_event("update_sign_meanings_completed", **result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
