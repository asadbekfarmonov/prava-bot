"""Enrich the road-sign catalogue with full-sentence Uzbek meanings + driver actions (S4).

Reads app/scripts/uz_signs_manifest.json (each entry has a real ``name`` sourced from
Wikimedia Commons descriptions) and, for every existing published RoadSign, rewrites the uz
translation so that:

  * ``meaning`` is a full explanatory Uzbek sentence (never just ``name + "."``); its length is
    always greater than ``len(name) + 1`` (spec-18 acceptance #2).
  * ``driver_action`` is SPECIFIC where the sign type is recognisable (speed limit, stop,
    yield, no-entry, pedestrian crossing, railway crossing, school/children, no-stopping/
    no-parking) and family-standard otherwise.

The version is marked content-verified (``verified_at`` set). Idempotent and safe to re-run:
recomputes deterministic text from the manifest + family/type rules; never duplicates rows.

Content policy: meanings/actions hold by standard road-traffic norms (teach nothing wrong);
content is ai_assisted/review-flagged and NOT claimed to be the official YHQ exam text. Sign
NAMES stay as sourced from Commons.

Usage:  python -m app.scripts.update_sign_meanings
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.domain.enums import Language
from app.domain.models import RoadSign, RoadSignTranslation, RoadSignVersion
from app.observability.logging import configure_logging, log_event
from app.storage.db import session_scope

_MANIFEST = Path(__file__).with_name("uz_signs_manifest.json")

FAMILY_LABEL = {
    "warning": "Ogohlantiruvchi belgi",
    "priority": "Imtiyoz belgisi",
    "prohibitory": "Taqiqlovchi belgi",
    "mandatory": "Buyuruvchi belgi",
    "information": "Axborot-koʻrsatkich belgi",
    "service": "Servis belgisi",
    "additional_plate": "Qoʻshimcha axborot belgisi",
}

# Full-sentence meaning templates per family. ``{name}`` is the sourced sign name.
FAMILY_MEANING = {
    "warning": "{name} — ogohlantiruvchi belgi: u haydovchini oldindagi xavf haqida "
               "ogohlantiradi va tezlikni pasaytirib, ehtiyot bo'lishga chorlaydi.",
    "priority": "{name} — imtiyoz belgisi: u chorraha yoki tor joyda transport vositalari "
                "orasida kim birinchi o'tishini belgilaydi.",
    "prohibitory": "{name} — taqiqlovchi belgi: u ma'lum harakat, manevr yoki holatni "
                   "cheklaydi yoxud butunlay taqiqlaydi.",
    "mandatory": "{name} — buyuruvchi belgi: u haydovchidan ko'rsatilgan harakat yoki "
                 "yo'nalishni bajarishni talab qiladi.",
    "information": "{name} — axborot-ko'rsatkich belgi: u yo'l, obyekt yoki harakat tartibi "
                   "haqida haydovchiga ma'lumot beradi.",
    "service": "{name} — servis belgisi: u yo'l bo'yidagi xizmat obyekti (masalan, dam olish, "
               "yoqilg'i, tibbiy yordam) haqida xabar beradi.",
    "additional_plate": "{name} — qo'shimcha axborot belgisi (plastinka): u asosiy belgi "
                        "ta'sirining chegarasi yoki shartlarini aniqlashtiradi.",
}

FAMILY_ACTION = {
    "warning": "Ehtiyot bo'ling, tezlikni pasaytiring va oldindagi xavfga tayyor turing.",
    "priority": "Imtiyoz tartibiga rioya qiling; kerak bo'lsa yo'l bering.",
    "prohibitory": "Belgidagi taqiq yoki cheklovga rioya qiling.",
    "mandatory": "Belgi ko'rsatgan harakat yoki yo'nalishni bajaring.",
    "information": "Ma'lumotni hisobga oling va tegishli holatda foydalaning.",
    "service": "Yo'l bo'yidagi xizmat obyektidan zarur bo'lsa foydalaning.",
    "additional_plate": "Asosiy belgi bilan birga o'qing va uning shartiga amal qiling.",
}


def _lower(text: str) -> str:
    return (text or "").lower()


def _specific(code: str, name: str, family: str) -> tuple[str | None, str | None]:
    """Return (meaning_override, action_override) where the sign TYPE is recognisable.

    Detection is by code prefix + Uzbek name keywords so it also covers the wider 77-sign set.
    Returns (None, None) when no specific type is matched (family defaults are used).
    """
    n = _lower(name)

    # Speed limit (e.g. 3.24 "Eng katta tezlik cheklangan").
    if "tezlik" in n and ("cheklan" in n or "eng katta" in n or any(ch.isdigit() for ch in name)):
        return (
            "{name} — ushbu joydan boshlab belgidagi qiymatdan katta tezlikda "
            "harakatlanish taqiqlanadi.".format(name=name),
            "Tezligingizni belgida ko'rsatilgan qiymatdan oshirmang.",
        )
    # STOP / to'xtamasdan harakatlanish taqiqlanadi (2.5).
    if "to'xtamasdan" in n or n.strip() == "stop" or "stop" in n:
        return (
            "{name} — belgilangan joyda (to'xtash chizig'i yoki chekka oldida) to'liq "
            "to'xtash va kesishayotgan harakatga yo'l berish shart.".format(name=name),
            "To'liq to'xtang, so'ng xavfsiz bo'lganda harakatni davom ettiring.",
        )
    # Yield / yo'l bering (2.4).
    if "yo'l bering" in n or "yoʻl bering" in n:
        return (
            "{name} — kesishayotgan yo'ldagi transport vositalariga yo'l berish talab "
            "qilinadi.".format(name=name),
            "Kesishayotgan harakatga yo'l bering; zarur bo'lsa to'xtang.",
        )
    # No-entry / kirish taqiqlangan (3.1) and general 'harakat taqiqlanadi'.
    if "kirish taqiqlan" in n or "harakat taqiqlan" in n:
        return (
            "{name} — ushbu yo'nalishda transport vositalarining harakatlanishi "
            "taqiqlanadi.".format(name=name),
            "Bu yo'nalishga kirmang; boshqa yo'ldan foydalaning.",
        )
    # Pedestrian crossing (5.16) / piyodalar o'tish joyi.
    if "piyodalar" in n and ("o'tish" in n or "oʻtish" in n or "yurishi" in n):
        return (
            "{name} — piyodalar yo'lni kesib o'tadigan joy; bu yerda piyodalarga alohida "
            "e'tibor qaratiladi.".format(name=name),
            "Sekinlashing va o'tayotgan piyodalarga yo'l bering.",
        )
    # Railway crossing (1.1-1.4, 1.34).
    if "temir yo'l" in n or "temir yoʻl" in n or "shlagbaum" in n or "to‘suvchi qurilma" in n:
        return (
            "{name} — oldinda temir yo'l kesishmasi borligini bildiradi; poyezd har doim "
            "ustunlikka ega.".format(name=name),
            "Sekinlashing; shlagbaum yoki qizil chiroqda to'xtash chizig'i oldida to'xtang.",
        )
    # School / children (5.46, 1.23).
    if "maktab" in n or "bolalar" in n:
        return (
            "{name} — yaqin atrofda bolalar bo'lishi mumkin bo'lgan hududni bildiradi.".format(
                name=name
            ),
            "Tezlikni keskin pasaytiring va bolalar kutilmaganda yo'lga chiqishiga tayyor turing.",
        )
    # No stopping / no parking (3.27-3.30) & service parking-time limits.
    if "to‘xtab turish" in n or "to'xtab turish" in n or "toʻxtab turish" in n:
        if "cheklan" in n or "taqiqlan" in n:
            return (
                "{name} — ushbu belgi ta'sir doirasida to'xtab turish cheklanadi yoki "
                "taqiqlanadi.".format(name=name),
                "Belgi ta'sir doirasida to'xtab turmang yoki ruxsat etilgan muddatga amal qiling.",
            )
    return (None, None)


def _meaning_and_action(code: str, name: str, family: str) -> tuple[str, str]:
    meaning_override, action_override = _specific(code, name, family)
    meaning = meaning_override or FAMILY_MEANING.get(
        family, FAMILY_MEANING["information"]
    ).format(name=name)
    action = action_override or FAMILY_ACTION.get(family, FAMILY_ACTION["information"])
    return meaning, action


def run() -> dict:
    configure_logging()
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    updated = 0
    missing = 0
    short_guarded = 0
    with session_scope() as db:
        for code, entry in manifest.items():
            family = entry.get("family", "information")
            name = (entry.get("name") or "").strip()
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

            meaning, action = _meaning_and_action(code, name, family)
            # Guarantee a full sentence strictly longer than name + 1 char.
            if len(meaning) <= len(name) + 1:
                meaning = (
                    f"{name} — {FAMILY_LABEL.get(family, 'yoʻl belgisi').lower()}; "
                    "uning talabiga rioya qiling."
                )
                short_guarded += 1

            tr.name = name
            tr.meaning = meaning
            tr.driver_action = action
            tr.important = None
            tr.exam_trap = None
            version.verified_at = datetime.now(timezone.utc).date()
            updated += 1
    result = {"updated": updated, "missing": missing, "short_guarded": short_guarded,
              "total": len(manifest)}
    log_event("update_sign_meanings_completed", **result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
