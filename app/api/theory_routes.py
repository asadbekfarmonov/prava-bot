"""Student-facing Theory / YHQ Handbook API (docs/spec/14, 15).

Published content only; per-user resources (progress/favorites) are IDOR-safe (scoped
by the session user_id); NO answer leak anywhere questions are embedded.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CompletedOnboardingUser, CurrentUser, DbSession
from app.api.theory_schemas import (
    FavoriteIn,
    ProgressIn,
    TheoryPracticeStartIn,
    TheoryReportIn,
)
from app.domain.enums import TheoryTargetType
from app.services import theory as theory_service

router = APIRouter(prefix="/api/theory")


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #
@router.get("/sections")
def list_sections(user: CurrentUser, db: DbSession) -> dict:
    return {"sections": theory_service.list_sections(db, user=user)}


@router.get("/sections/{slug}")
def get_section(slug: str, user: CurrentUser, db: DbSession) -> dict:
    return theory_service.get_section(db, slug, user=user)


@router.get("/articles/{slug}")
def get_article(slug: str, user: CurrentUser, db: DbSession) -> dict:
    return theory_service.get_article(db, slug, user=user)


@router.get("/search")
def search(user: CurrentUser, db: DbSession, q: str = Query(default="")) -> dict:
    return {"results": theory_service.search(db, q)}


# --------------------------------------------------------------------------- #
# Catalogues
# --------------------------------------------------------------------------- #
@router.get("/signs")
def list_signs(user: CurrentUser, db: DbSession, family: str | None = Query(default=None)) -> dict:
    return {"signs": theory_service.list_signs(db, family=family)}


@router.get("/signs/{code}")
def get_sign(code: str, user: CurrentUser, db: DbSession) -> dict:
    return theory_service.get_sign(db, code, user=user)


@router.get("/markings")
def list_markings(user: CurrentUser, db: DbSession) -> dict:
    return {"markings": theory_service.list_markings(db)}


@router.get("/markings/{marking_id}")
def get_marking(marking_id: str, user: CurrentUser, db: DbSession) -> dict:
    return theory_service.get_marking(db, marking_id)


@router.get("/gestures")
def list_gestures(user: CurrentUser, db: DbSession) -> dict:
    return {"gestures": theory_service.list_gestures(db)}


@router.get("/gestures/{gesture_id}")
def get_gesture(gesture_id: str, user: CurrentUser, db: DbSession) -> dict:
    return theory_service.get_gesture(db, gesture_id)


@router.get("/lights")
def list_lights(user: CurrentUser, db: DbSession) -> dict:
    return {"lights": theory_service.list_lights(db)}


@router.get("/lights/{light_id}")
def get_light(light_id: str, user: CurrentUser, db: DbSession) -> dict:
    return theory_service.get_light(db, light_id)


# --------------------------------------------------------------------------- #
# Practice <-> Theory
# --------------------------------------------------------------------------- #
@router.post("/practice/start")
def start_practice(payload: TheoryPracticeStartIn, user: CompletedOnboardingUser, db: DbSession) -> dict:
    return theory_service.start_practice(
        db, user, TheoryTargetType(payload.target_type), payload.target_id
    )


@router.get("/by-rule/{rule_code:path}")
def by_rule(rule_code: str, user: CurrentUser, db: DbSession) -> dict:
    return theory_service.by_rule(db, rule_code)


# --------------------------------------------------------------------------- #
# Progress (viewed only from client; mastered derived server-side)
# --------------------------------------------------------------------------- #
@router.post("/progress")
def mark_progress(payload: ProgressIn, user: CurrentUser, db: DbSession) -> dict:
    return theory_service.mark_progress(db, user, payload.target_type, payload.target_id)


# --------------------------------------------------------------------------- #
# Favorites (IDOR-safe)
# --------------------------------------------------------------------------- #
@router.get("/favorites")
def list_favorites(user: CurrentUser, db: DbSession) -> dict:
    return {"favorites": theory_service.list_favorites(db, user)}


@router.post("/favorites", status_code=status.HTTP_201_CREATED)
def add_favorite(payload: FavoriteIn, user: CurrentUser, db: DbSession) -> dict:
    return theory_service.add_favorite(db, user, payload.target_type, payload.target_id)


@router.delete("/favorites/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(favorite_id: str, user: CurrentUser, db: DbSession) -> Response:
    theory_service.remove_favorite(db, user, favorite_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Content reports (theory target) — reuses the ContentReport queue
# --------------------------------------------------------------------------- #
@router.post("/reports", status_code=status.HTTP_201_CREATED)
def create_theory_report(payload: TheoryReportIn, user: CurrentUser, db: DbSession) -> dict:
    from app.services import reports as reports_service

    report = reports_service.create_theory_report(
        db, user, target_type=payload.target_type, target_id=payload.target_id,
        reason=payload.reason, note=payload.note,
    )
    return {"id": report.id, "status": report.status.value}
