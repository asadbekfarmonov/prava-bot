"""Admin Theory studio API (docs/spec/14, 15). EVERY endpoint is role-gated server-side
via ``require_role`` (hiding frontend routes is not a control); every mutation is audited
in the service layer. Authors create/edit drafts; reviewers review/publish/verify.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.admin_deps import require_role
from app.api.deps import DbSession
from app.api.theory_schemas import (
    ArticleContentIn,
    ArticleCreateIn,
    GestureContentIn,
    GestureCreateIn,
    LightContentIn,
    LightCreateIn,
    MarkingContentIn,
    MarkingCreateIn,
    SectionCreateIn,
    SectionTranslationIn,
    SignContentIn,
    SignCreateIn,
)
from app.domain.enums import AdminRole
from app.domain.models import User
from app.services import theory as theory_service
from app.services import theory_admin

router = APIRouter(prefix="/api/admin/theory")

AuthorUser = Annotated[User, Depends(require_role(AdminRole.CONTENT_AUTHOR))]
ReviewerUser = Annotated[User, Depends(require_role(AdminRole.CONTENT_REVIEWER))]


def _version_out(v) -> dict:
    return {
        "id": v.id,
        "version": v.version,
        "status": v.status.value,
        "authored_by_user_id": v.authored_by_user_id,
        "reviewed_by_user_id": v.reviewed_by_user_id,
        "approved_by_user_id": v.approved_by_user_id,
        "verified_at": v.verified_at.isoformat() if v.verified_at else None,
    }


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #
@router.post("/sections", status_code=status.HTTP_201_CREATED)
def create_section(payload: SectionCreateIn, user: AuthorUser, db: DbSession) -> dict:
    s = theory_admin.create_section(
        db, user, slug=payload.slug, title=payload.title, subtitle=payload.subtitle,
        topic=payload.topic, position=payload.position, icon_media_id=payload.icon_media_id,
    )
    return {"id": s.id, "slug": s.slug, "status": s.status.value}


@router.put("/sections/{section_id}/translation")
def translate_section(section_id: str, payload: SectionTranslationIn, user: AuthorUser, db: DbSession) -> dict:
    s = theory_admin.set_section_translation(
        db, user, section_id, language=payload.language, title=payload.title, subtitle=payload.subtitle
    )
    return {"id": s.id, "status": s.status.value}


@router.post("/sections/{section_id}/publish")
def publish_section(section_id: str, user: ReviewerUser, db: DbSession) -> dict:
    s = theory_admin.publish_section(db, user, section_id)
    return {"id": s.id, "status": s.status.value}


# --------------------------------------------------------------------------- #
# Articles
# --------------------------------------------------------------------------- #
@router.post("/articles", status_code=status.HTTP_201_CREATED)
def create_article(payload: ArticleCreateIn, user: AuthorUser, db: DbSession) -> dict:
    v = theory_admin.create_article(
        db, user, section_id=payload.section_id, slug=payload.slug,
        kind=payload.kind, position=payload.position,
    )
    return {"article_id": v.article_id, **_version_out(v)}


@router.put("/articles/{article_id}")
def edit_article(article_id: str, payload: ArticleContentIn, user: AuthorUser, db: DbSession) -> dict:
    data = theory_admin.ArticleContentInput(
        title=payload.title, summary=payload.summary, hero_media_id=payload.hero_media_id,
        ai_assisted=payload.ai_assisted,
        blocks=[
            theory_admin.BlockInput(
                type=b.type, body=b.body, media_id=b.media_id, rule_code=b.rule_code,
                ref_question_id=b.ref_question_id, data=b.data,
            )
            for b in payload.blocks
        ],
        rule_codes=list(payload.rule_codes),
        question_ids=list(payload.question_ids),
    )
    v = theory_admin.edit_article(db, user, article_id, data)
    return {"article_id": v.article_id, **_version_out(v)}


@router.post("/article-versions/{version_id}/submit-review")
def submit_article(version_id: str, user: AuthorUser, db: DbSession) -> dict:
    return _version_out(theory_admin.submit_article_review(db, user, version_id))


@router.post("/article-versions/{version_id}/review")
def review_article(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.review_article(db, user, version_id))


@router.post("/article-versions/{version_id}/publish")
def publish_article(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.publish_article(db, user, version_id))


# --------------------------------------------------------------------------- #
# Signs
# --------------------------------------------------------------------------- #
@router.post("/signs", status_code=status.HTTP_201_CREATED)
def create_sign(payload: SignCreateIn, user: AuthorUser, db: DbSession) -> dict:
    v = theory_admin.create_sign(
        db, user, official_code=payload.official_code, family=payload.family,
        media_id=payload.media_id, position=payload.position,
    )
    return {"road_sign_id": v.road_sign_id, **_version_out(v)}


@router.put("/signs/{sign_id}")
def edit_sign(sign_id: str, payload: SignContentIn, user: AuthorUser, db: DbSession) -> dict:
    data = theory_admin.SignContentInput(
        name=payload.name, meaning=payload.meaning, driver_action=payload.driver_action,
        important=payload.important, exam_trap=payload.exam_trap, memory_tip=payload.memory_tip,
        keywords=payload.keywords, media_id=payload.media_id, ai_assisted=payload.ai_assisted,
        rule_codes=list(payload.rule_codes), question_ids=list(payload.question_ids),
    )
    v = theory_admin.edit_sign(db, user, sign_id, data)
    return {"road_sign_id": v.road_sign_id, **_version_out(v)}


@router.post("/sign-versions/{version_id}/submit-review")
def submit_sign(version_id: str, user: AuthorUser, db: DbSession) -> dict:
    return _version_out(theory_admin.submit_sign_review(db, user, version_id))


@router.post("/sign-versions/{version_id}/review")
def review_sign(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.review_sign(db, user, version_id))


@router.post("/sign-versions/{version_id}/publish")
def publish_sign(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.publish_sign(db, user, version_id))


# --------------------------------------------------------------------------- #
# Markings
# --------------------------------------------------------------------------- #
@router.post("/markings", status_code=status.HTTP_201_CREATED)
def create_marking(payload: MarkingCreateIn, user: AuthorUser, db: DbSession) -> dict:
    v = theory_admin.create_marking(
        db, user, group=payload.group, code=payload.code,
        media_id=payload.media_id, position=payload.position,
    )
    return {"road_marking_id": v.road_marking_id, **_version_out(v)}


@router.put("/markings/{marking_id}")
def edit_marking(marking_id: str, payload: MarkingContentIn, user: AuthorUser, db: DbSession) -> dict:
    data = theory_admin.MarkingContentInput(
        name=payload.name, meaning=payload.meaning, can_cross=payload.can_cross,
        can_stop_park=payload.can_stop_park, conflict_rule=payload.conflict_rule,
        exam_trap=payload.exam_trap, memory_tip=payload.memory_tip, keywords=payload.keywords,
        media_id=payload.media_id, ai_assisted=payload.ai_assisted, rule_codes=list(payload.rule_codes),
    )
    v = theory_admin.edit_marking(db, user, marking_id, data)
    return {"road_marking_id": v.road_marking_id, **_version_out(v)}


@router.post("/marking-versions/{version_id}/submit-review")
def submit_marking(version_id: str, user: AuthorUser, db: DbSession) -> dict:
    return _version_out(theory_admin.submit_marking_review(db, user, version_id))


@router.post("/marking-versions/{version_id}/review")
def review_marking(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.review_marking(db, user, version_id))


@router.post("/marking-versions/{version_id}/publish")
def publish_marking(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.publish_marking(db, user, version_id))


# --------------------------------------------------------------------------- #
# Gestures
# --------------------------------------------------------------------------- #
@router.post("/gestures", status_code=status.HTTP_201_CREATED)
def create_gesture(payload: GestureCreateIn, user: AuthorUser, db: DbSession) -> dict:
    v = theory_admin.create_gesture(
        db, user, code=payload.code, media_id=payload.media_id,
        animation_media_id=payload.animation_media_id, position=payload.position,
    )
    return {"gesture_id": v.gesture_id, **_version_out(v)}


@router.put("/gestures/{gesture_id}")
def edit_gesture(gesture_id: str, payload: GestureContentIn, user: AuthorUser, db: DbSession) -> dict:
    data = theory_admin.GestureContentInput(
        name=payload.name, position_desc=payload.position_desc, allowed=payload.allowed,
        forbidden=payload.forbidden, memory_tip=payload.memory_tip, keywords=payload.keywords,
        media_id=payload.media_id, animation_media_id=payload.animation_media_id,
        ai_assisted=payload.ai_assisted, rule_codes=list(payload.rule_codes),
    )
    v = theory_admin.edit_gesture(db, user, gesture_id, data)
    return {"gesture_id": v.gesture_id, **_version_out(v)}


@router.post("/gesture-versions/{version_id}/submit-review")
def submit_gesture(version_id: str, user: AuthorUser, db: DbSession) -> dict:
    return _version_out(theory_admin.submit_gesture_review(db, user, version_id))


@router.post("/gesture-versions/{version_id}/review")
def review_gesture(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.review_gesture(db, user, version_id))


@router.post("/gesture-versions/{version_id}/publish")
def publish_gesture(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.publish_gesture(db, user, version_id))


# --------------------------------------------------------------------------- #
# Traffic lights
# --------------------------------------------------------------------------- #
@router.post("/lights", status_code=status.HTTP_201_CREATED)
def create_light(payload: LightCreateIn, user: AuthorUser, db: DbSession) -> dict:
    v = theory_admin.create_light(
        db, user, kind=payload.kind, media_id=payload.media_id, position=payload.position
    )
    return {"light_id": v.light_id, **_version_out(v)}


@router.put("/lights/{light_id}")
def edit_light(light_id: str, payload: LightContentIn, user: AuthorUser, db: DbSession) -> dict:
    data = theory_admin.LightContentInput(
        title=payload.title, meaning=payload.meaning, movement_permitted=payload.movement_permitted,
        direction_permitted=payload.direction_permitted, exceptions=payload.exceptions,
        typical_exam_situation=payload.typical_exam_situation, keywords=payload.keywords,
        media_id=payload.media_id, ai_assisted=payload.ai_assisted, rule_codes=list(payload.rule_codes),
    )
    v = theory_admin.edit_light(db, user, light_id, data)
    return {"light_id": v.light_id, **_version_out(v)}


@router.post("/light-versions/{version_id}/submit-review")
def submit_light(version_id: str, user: AuthorUser, db: DbSession) -> dict:
    return _version_out(theory_admin.submit_light_review(db, user, version_id))


@router.post("/light-versions/{version_id}/review")
def review_light(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.review_light(db, user, version_id))


@router.post("/light-versions/{version_id}/publish")
def publish_light(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.publish_light(db, user, version_id))


# --------------------------------------------------------------------------- #
# Verify + review queue
# --------------------------------------------------------------------------- #
@router.post("/verify/{entity}/{version_id}")
def set_verified(entity: str, version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(theory_admin.set_verified(db, user, entity, version_id))


@router.get("/review-queue")
def review_queue(user: ReviewerUser, db: DbSession) -> dict:
    return theory_admin.review_queue(db)


# --------------------------------------------------------------------------- #
# Admin list endpoints (Gap 2, docs/spec/19): browse drafts + non-published
# content for editing. AuthorUser-gated; students keep /api/theory/* which is
# published-only and never exposes include_unpublished (security invariant).
# --------------------------------------------------------------------------- #
@router.get("/sections")
def admin_list_sections(
    user: AuthorUser, db: DbSession, include_unpublished: bool = Query(default=True)
) -> dict:
    return {"sections": theory_service.list_sections(db, include_unpublished=include_unpublished)}


@router.get("/articles")
def admin_list_articles(
    user: AuthorUser,
    db: DbSession,
    section_id: str | None = Query(default=None),
    include_unpublished: bool = Query(default=True),
) -> dict:
    return {
        "articles": theory_service.list_articles(
            db, section_id=section_id, include_unpublished=include_unpublished
        )
    }


@router.get("/signs")
def admin_list_signs(
    user: AuthorUser,
    db: DbSession,
    family: str | None = Query(default=None),
    include_unpublished: bool = Query(default=True),
) -> dict:
    return {
        "signs": theory_service.list_signs(
            db, family=family, include_unpublished=include_unpublished
        )
    }


@router.get("/markings")
def admin_list_markings(
    user: AuthorUser, db: DbSession, include_unpublished: bool = Query(default=True)
) -> dict:
    return {"markings": theory_service.list_markings(db, include_unpublished=include_unpublished)}


@router.get("/gestures")
def admin_list_gestures(
    user: AuthorUser, db: DbSession, include_unpublished: bool = Query(default=True)
) -> dict:
    return {"gestures": theory_service.list_gestures(db, include_unpublished=include_unpublished)}


@router.get("/lights")
def admin_list_lights(
    user: AuthorUser, db: DbSession, include_unpublished: bool = Query(default=True)
) -> dict:
    return {"lights": theory_service.list_lights(db, include_unpublished=include_unpublished)}
