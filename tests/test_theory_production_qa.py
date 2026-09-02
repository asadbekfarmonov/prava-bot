"""QA-added spec-18 coverage (tester stage).

Fills two gaps left by tests/test_theory_production.py:

  * IDEMPOTENCY / prod-safety (spec-18 implementation notes: "safe to run on the live prod DB;
    upsert/skip existing; never duplicate"): a second run of ``seed_theory_production`` must
    create nothing and must not duplicate any published catalogue/section/article.
  * FIRST-AID CONTENT POLICY (spec-18, binding): the first-aid section must ship legal,
    non-medical obligations plus an explicit "medically-reviewed-pending" note, and must NOT
    contain fabricated medical procedure (no invented dosages / step-by-step clinical actions).
"""

from __future__ import annotations

import re

from app.scripts import seed_theory_production
from app.services import theory as theory_service
from app.storage.db import session_scope
from tests.test_theory_production import _seed_all


def _catalogue_snapshot(db) -> dict:
    return {
        "gestures": sorted(g["code"] for g in theory_service.list_gestures(db)),
        "lights": sorted(light["id"] for light in theory_service.list_lights(db)),
        "markings": sorted(m["code"] for m in theory_service.list_markings(db)),
        "sections": sorted(s["slug"] for s in theory_service.list_sections(db)),
    }


def test_seed_is_idempotent_no_duplicates(client):
    _seed_all()
    with session_scope() as db:
        before = _catalogue_snapshot(db)

    # Second run of the production seed must be a no-op on creation.
    result = seed_theory_production.run()
    assert result["gestures_created"] == 0, result
    assert result["lights_created"] == 0, result
    assert result["markings_created"] == 0, result
    assert result["articles_created"] == 0, result
    # Re-running must not re-archive anything (already archived once).
    assert result["demo_archived"] == {
        "articles": 0, "markings": 0, "gestures": 0, "lights": 0
    }, result

    with session_scope() as db:
        after = _catalogue_snapshot(db)
    # No duplicate codes/slugs introduced, counts identical.
    assert before == after, (before, after)
    # And no duplicate published gesture/marking codes at all.
    assert len(before["gestures"]) == len(set(before["gestures"]))
    assert len(before["markings"]) == len(set(before["markings"]))
    assert len(before["sections"]) == len(set(before["sections"]))


def test_first_aid_content_policy_compliant(client):
    _seed_all()
    with session_scope() as db:
        art = theory_service.get_article(db, "birinchi-yordam-qonuniy")
        text = "\n".join(b["body"] for b in art["blocks"]).lower()

    # (1) Explicit, honest "medically-reviewed-pending" note is present (not a generic DEMO string).
    assert "ko'rikdan o'tkazilmoqda" in text or "ko\u2018rikdan o\u2018tkazilmoqda" in text, text
    assert "demo" not in text

    # (2) Legal, non-medical obligations are present (call emergency services, don't leave scene).
    assert "103" in text  # ambulance
    assert "tark etma" in text or "joyini tark" in text

    # (3) NO fabricated medical procedure: no invented dosages, no clinical step instructions.
    #     Guard against numeric drug dosages (e.g. "500 mg", "2 ml") and named clinical drugs.
    assert not re.search(r"\d+\s?(mg|ml|gramm|kub)", text), "fabricated dosage detected"
    for banned in ("kordiamin", "adrenalin", "jgut", "zharqin", "ukol", "in'ektsiya"):
        assert banned not in text, f"fabricated medical procedure keyword: {banned}"
