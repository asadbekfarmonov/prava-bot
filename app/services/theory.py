"""Student-facing Theory / YHQ Handbook read + progress services (docs/spec/14, 15).

Hard rules:
- Students see PUBLISHED content only (sections/articles/catalog entries).
- Author text is returned as PLAIN TEXT (JSON strings); the frontend renders via React
  text nodes only (no HTML) — stored-XSS payloads render inert (docs/spec/09).
- NO answer leak: article practice_link blocks and Theory->Practice never expose
  is_correct / option correctness (reuses the no-leak practice payload).
- Per-user resources (progress/favorites) are scoped by the session user_id (IDOR-safe).
- 'mastered' is DERIVED server-side from linked-question performance, never set by client.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    Language,
    PracticeSource,
    RoadSignFamily,
    TheoryBlockType,
    TheoryProgressState,
    TheoryTargetType,
    VersionStatus,
)
from app.domain.enums import THEORY_PROGRESS_ORDER
from app.domain.exam_config import get_theory_config
from app.domain.models import (
    ControllerGesture,
    ControllerGestureTranslation,
    MockAnswer,
    PracticeAnswer,
    PracticeSession,
    Question,
    QuestionMedia,
    QuestionVersion,
    RoadMarking,
    RoadMarkingTranslation,
    RoadSign,
    RoadSignQuestionLink,
    RoadSignTranslation,
    RoadSignVersion,
    Rule,
    RuleTranslation,
    TheoryArticle,
    TheoryArticleQuestionLink,
    TheoryArticleRule,
    TheoryArticleTranslation,
    TheoryArticleVersion,
    TheoryContentBlock,
    TheoryContentBlockTranslation,
    TheoryFavorite,
    TheoryProgress,
    TheorySection,
    TheorySectionTranslation,
    TrafficLightState,
    TrafficLightStateTranslation,
    User,
)

_LANG = Language.UZ


# --------------------------------------------------------------------------- #
# Small resolvers
# --------------------------------------------------------------------------- #
def _media_url(db: Session, media_id: str | None) -> str | None:
    if not media_id:
        return None
    media = db.get(QuestionMedia, media_id)
    if media is None:
        return None
    return f"/api/media/{media.id}/{media.content_hash}"


def _theory_media_meta(db: Session, media_id: str | None) -> dict | None:
    """No-leak media presentation metadata for theory blocks/detail surfaces."""
    from app.services.media import media_meta

    return media_meta(db, media_id)


def _rule_out(db: Session, rule_id: str, rule_version: int | None = None) -> dict | None:
    rule = db.get(Rule, rule_id)
    if rule is None:
        return None
    tr = db.scalar(
        select(RuleTranslation).where(
            RuleTranslation.rule_id == rule.id, RuleTranslation.language == _LANG
        )
    )
    return {
        "code": rule.code,
        "title": tr.title if tr else None,
        "text": tr.text if tr else "",
        "source_url": rule.source_url,
        "status": rule.status.value,
        "rule_version": rule_version if rule_version is not None else rule.version,
    }


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #
def _section_translation(db: Session, section_id: str) -> TheorySectionTranslation | None:
    return db.scalar(
        select(TheorySectionTranslation).where(
            TheorySectionTranslation.section_id == section_id,
            TheorySectionTranslation.language == _LANG,
        )
    )


def _section_out(db: Session, section: TheorySection, *, user: User | None = None) -> dict:
    tr = _section_translation(db, section.id)
    published_articles = list(
        db.scalars(
            select(TheoryArticle).where(
                TheoryArticle.section_id == section.id,
                TheoryArticle.lifecycle_status == VersionStatus.PUBLISHED,
            )
        )
    )
    out = {
        "id": section.id,
        "slug": section.slug,
        "topic": section.topic.value if section.topic else None,
        "position": section.position,
        "icon_url": _media_url(db, section.icon_media_id),
        "title": tr.title if tr else "",
        "subtitle": tr.subtitle if tr else "",
        "article_count": len(published_articles),
    }
    if user is not None:
        viewed = _count_progress_in(db, user, TheoryTargetType.ARTICLE,
                                    [a.id for a in published_articles])
        out["progress"] = {"viewed": viewed, "total": len(published_articles)}
    return out


def list_sections(db: Session, *, user: User | None = None) -> list[dict]:
    sections = list(
        db.scalars(
            select(TheorySection)
            .where(TheorySection.status == VersionStatus.PUBLISHED)
            .order_by(TheorySection.position, TheorySection.slug)
        )
    )
    return [_section_out(db, s, user=user) for s in sections]


def get_section(db: Session, slug: str, *, user: User | None = None) -> dict:
    section = db.scalar(
        select(TheorySection).where(
            TheorySection.slug == slug, TheorySection.status == VersionStatus.PUBLISHED
        )
    )
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bo'lim topilmadi")
    out = _section_out(db, section, user=user)
    articles = list(
        db.scalars(
            select(TheoryArticle)
            .where(
                TheoryArticle.section_id == section.id,
                TheoryArticle.lifecycle_status == VersionStatus.PUBLISHED,
            )
            .order_by(TheoryArticle.position, TheoryArticle.slug)
        )
    )
    out["articles"] = [_article_card(db, a, user=user) for a in articles]
    return out


# --------------------------------------------------------------------------- #
# Articles
# --------------------------------------------------------------------------- #
def _article_translation(db: Session, article_version_id: str) -> TheoryArticleTranslation | None:
    return db.scalar(
        select(TheoryArticleTranslation).where(
            TheoryArticleTranslation.article_version_id == article_version_id,
            TheoryArticleTranslation.language == _LANG,
        )
    )


def _article_card(db: Session, article: TheoryArticle, *, user: User | None = None) -> dict:
    title = ""
    summary = ""
    if article.current_version_id:
        tr = _article_translation(db, article.current_version_id)
        if tr:
            title, summary = tr.title, tr.summary
    card = {
        "id": article.id,
        "slug": article.slug,
        "kind": article.kind.value,
        "position": article.position,
        "title": title,
        "summary": summary,
    }
    if user is not None:
        card["progress_state"] = _current_progress_state(
            db, user, TheoryTargetType.ARTICLE, article.id
        )
    return card


def _block_out(db: Session, block: TheoryContentBlock) -> dict:
    tr = db.scalar(
        select(TheoryContentBlockTranslation).where(
            TheoryContentBlockTranslation.block_id == block.id,
            TheoryContentBlockTranslation.language == _LANG,
        )
    )
    out: dict = {
        "id": block.id,
        "type": block.type.value,
        "position": block.position,
        "body": tr.body if tr else "",
        "data": block.data_json,
        "media_url": _media_url(db, block.media_id),
        # No-leak media metadata so the frontend QuestionMedia can pick <img> vs
        # <video> and build a fixed aspect-ratio box (never any answer data).
        "media": _theory_media_meta(db, block.media_id),
    }
    if block.type == TheoryBlockType.RULE_CALLOUT and block.rule_id:
        out["rule"] = _rule_out(db, block.rule_id)
    # practice_link: expose only that a linked question exists — NEVER its options/answer.
    if block.type == TheoryBlockType.PRACTICE_LINK and block.ref_question_id:
        out["ref_question_id"] = block.ref_question_id
    return out


def get_article(db: Session, slug: str, *, user: User | None = None) -> dict:
    article = db.scalar(
        select(TheoryArticle).where(
            TheoryArticle.slug == slug,
            TheoryArticle.lifecycle_status == VersionStatus.PUBLISHED,
        )
    )
    if article is None or article.current_version_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maqola topilmadi")
    version = db.get(TheoryArticleVersion, article.current_version_id)
    if version is None or version.status != VersionStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maqola topilmadi")

    tr = _article_translation(db, version.id)
    blocks = list(
        db.scalars(
            select(TheoryContentBlock)
            .where(TheoryContentBlock.article_version_id == version.id)
            .order_by(TheoryContentBlock.position)
        )
    )
    rule_links = list(
        db.scalars(
            select(TheoryArticleRule).where(TheoryArticleRule.article_version_id == version.id)
        )
    )
    linked_q = _article_linked_question_count(db, article.id)

    result = {
        "id": article.id,
        "slug": article.slug,
        "kind": article.kind.value,
        "section_id": article.section_id,
        "version": version.version,
        "hero_url": _media_url(db, version.hero_media_id),
        "title": tr.title if tr else "",
        "summary": tr.summary if tr else "",
        "blocks": [_block_out(db, b) for b in blocks],
        "rules": [_rule_out(db, link.rule_id, link.rule_version) for link in rule_links],
        "linked_question_count": linked_q,
    }
    if user is not None:
        # Opening the article marks 'viewed' (never mastery).
        mark_viewed(db, user, TheoryTargetType.ARTICLE, article.id)
        result["progress_state"] = _current_progress_state(
            db, user, TheoryTargetType.ARTICLE, article.id
        )
    return result


# --------------------------------------------------------------------------- #
# Catalogue: signs
# --------------------------------------------------------------------------- #
def _sign_translation(db: Session, version_id: str) -> RoadSignTranslation | None:
    return db.scalar(
        select(RoadSignTranslation).where(
            RoadSignTranslation.road_sign_version_id == version_id,
            RoadSignTranslation.language == _LANG,
        )
    )


def _sign_card(db: Session, sign: RoadSign) -> dict:
    name = ""
    if sign.current_version_id:
        tr = _sign_translation(db, sign.current_version_id)
        if tr:
            name = tr.name
    return {
        "id": sign.id,
        "code": sign.official_code,
        "family": sign.family.value,
        "name": name,
        "media_url": _media_url(db, sign.media_id),
    }


def list_signs(db: Session, *, family: str | None = None) -> list[dict]:
    stmt = select(RoadSign).where(RoadSign.lifecycle_status == VersionStatus.PUBLISHED)
    if family:
        try:
            fam = RoadSignFamily(family)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum belgi oilasi"
            ) from exc
        stmt = stmt.where(RoadSign.family == fam)
    stmt = stmt.order_by(RoadSign.position, RoadSign.official_code)
    return [_sign_card(db, s) for s in db.scalars(stmt)]


def get_sign(db: Session, code: str, *, user: User | None = None) -> dict:
    sign = db.scalar(
        select(RoadSign).where(
            RoadSign.official_code == code,
            RoadSign.lifecycle_status == VersionStatus.PUBLISHED,
        )
    )
    if sign is None or sign.current_version_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Belgi topilmadi")
    version = db.get(RoadSignVersion, sign.current_version_id)
    tr = _sign_translation(db, version.id)
    from app.domain.models import RoadSignRule

    rule_links = list(
        db.scalars(select(RoadSignRule).where(RoadSignRule.road_sign_version_id == version.id))
    )
    out = {
        "id": sign.id,
        "code": sign.official_code,
        "family": sign.family.value,
        "media_url": _media_url(db, version.media_id or sign.media_id),
        "name": tr.name if tr else "",
        "meaning": tr.meaning if tr else "",
        "driver_action": tr.driver_action if tr else "",
        "important": tr.important if tr else None,
        "exam_trap": tr.exam_trap if tr else None,
        "memory_tip": tr.memory_tip if tr else None,
        "rules": [_rule_out(db, link.rule_id, link.rule_version) for link in rule_links],
        "linked_question_count": _sign_linked_question_count(db, sign.id),
    }
    if user is not None:
        mark_viewed(db, user, TheoryTargetType.SIGN, sign.id)
        out["progress_state"] = _current_progress_state(
            db, user, TheoryTargetType.SIGN, sign.id
        )
    return out


# --------------------------------------------------------------------------- #
# Catalogue: markings / gestures / lights (list + detail)
# --------------------------------------------------------------------------- #
def list_markings(db: Session) -> list[dict]:
    rows = list(
        db.scalars(
            select(RoadMarking)
            .where(RoadMarking.lifecycle_status == VersionStatus.PUBLISHED)
            .order_by(RoadMarking.position)
        )
    )
    out = []
    for m in rows:
        name = ""
        if m.current_version_id:
            tr = db.scalar(
                select(RoadMarkingTranslation).where(
                    RoadMarkingTranslation.road_marking_version_id == m.current_version_id,
                    RoadMarkingTranslation.language == _LANG,
                )
            )
            name = tr.name if tr else ""
        out.append(
            {
                "id": m.id,
                "code": m.code,
                "group": m.marking_group.value,
                "name": name,
                "media_url": _media_url(db, m.media_id),
            }
        )
    return out


def get_marking(db: Session, marking_id: str) -> dict:
    m = db.scalar(
        select(RoadMarking).where(
            RoadMarking.id == marking_id,
            RoadMarking.lifecycle_status == VersionStatus.PUBLISHED,
        )
    )
    if m is None or m.current_version_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chiziq topilmadi")
    tr = db.scalar(
        select(RoadMarkingTranslation).where(
            RoadMarkingTranslation.road_marking_version_id == m.current_version_id,
            RoadMarkingTranslation.language == _LANG,
        )
    )
    from app.domain.models import RoadMarkingRule

    rule_links = list(
        db.scalars(
            select(RoadMarkingRule).where(
                RoadMarkingRule.road_marking_version_id == m.current_version_id
            )
        )
    )
    return {
        "id": m.id,
        "code": m.code,
        "group": m.marking_group.value,
        "media_url": _media_url(db, m.media_id),
        "name": tr.name if tr else "",
        "meaning": tr.meaning if tr else "",
        "can_cross": tr.can_cross if tr else None,
        "can_stop_park": tr.can_stop_park if tr else None,
        "conflict_rule": tr.conflict_rule if tr else None,
        "exam_trap": tr.exam_trap if tr else None,
        "memory_tip": tr.memory_tip if tr else None,
        "rules": [_rule_out(db, link.rule_id, link.rule_version) for link in rule_links],
    }


def list_gestures(db: Session) -> list[dict]:
    rows = list(
        db.scalars(
            select(ControllerGesture)
            .where(ControllerGesture.lifecycle_status == VersionStatus.PUBLISHED)
            .order_by(ControllerGesture.position)
        )
    )
    out = []
    for g in rows:
        name = ""
        if g.current_version_id:
            tr = db.scalar(
                select(ControllerGestureTranslation).where(
                    ControllerGestureTranslation.gesture_version_id == g.current_version_id,
                    ControllerGestureTranslation.language == _LANG,
                )
            )
            name = tr.name if tr else ""
        out.append(
            {
                "id": g.id,
                "code": g.code,
                "name": name,
                "media_url": _media_url(db, g.media_id),
                "animation_url": _media_url(db, g.animation_media_id),
            }
        )
    return out


def get_gesture(db: Session, gesture_id: str) -> dict:
    g = db.scalar(
        select(ControllerGesture).where(
            ControllerGesture.id == gesture_id,
            ControllerGesture.lifecycle_status == VersionStatus.PUBLISHED,
        )
    )
    if g is None or g.current_version_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ishora topilmadi")
    tr = db.scalar(
        select(ControllerGestureTranslation).where(
            ControllerGestureTranslation.gesture_version_id == g.current_version_id,
            ControllerGestureTranslation.language == _LANG,
        )
    )
    from app.domain.models import ControllerGestureRule

    rule_links = list(
        db.scalars(
            select(ControllerGestureRule).where(
                ControllerGestureRule.gesture_version_id == g.current_version_id
            )
        )
    )
    return {
        "id": g.id,
        "code": g.code,
        "media_url": _media_url(db, g.media_id),
        "animation_url": _media_url(db, g.animation_media_id),
        "name": tr.name if tr else "",
        "position_desc": tr.position_desc if tr else "",
        "allowed": tr.allowed if tr else "",
        "forbidden": tr.forbidden if tr else "",
        "memory_tip": tr.memory_tip if tr else None,
        "rules": [_rule_out(db, link.rule_id, link.rule_version) for link in rule_links],
    }


def list_lights(db: Session) -> list[dict]:
    rows = list(
        db.scalars(
            select(TrafficLightState)
            .where(TrafficLightState.lifecycle_status == VersionStatus.PUBLISHED)
            .order_by(TrafficLightState.position)
        )
    )
    out = []
    for light in rows:
        title = ""
        if light.current_version_id:
            tr = db.scalar(
                select(TrafficLightStateTranslation).where(
                    TrafficLightStateTranslation.light_version_id == light.current_version_id,
                    TrafficLightStateTranslation.language == _LANG,
                )
            )
            title = tr.title if tr else ""
        out.append(
            {
                "id": light.id,
                "kind": light.kind.value,
                "title": title,
                "media_url": _media_url(db, light.media_id),
            }
        )
    return out


def get_light(db: Session, light_id: str) -> dict:
    light = db.scalar(
        select(TrafficLightState).where(
            TrafficLightState.id == light_id,
            TrafficLightState.lifecycle_status == VersionStatus.PUBLISHED,
        )
    )
    if light is None or light.current_version_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal topilmadi")
    tr = db.scalar(
        select(TrafficLightStateTranslation).where(
            TrafficLightStateTranslation.light_version_id == light.current_version_id,
            TrafficLightStateTranslation.language == _LANG,
        )
    )
    from app.domain.models import TrafficLightStateRule

    rule_links = list(
        db.scalars(
            select(TrafficLightStateRule).where(
                TrafficLightStateRule.light_version_id == light.current_version_id
            )
        )
    )
    return {
        "id": light.id,
        "kind": light.kind.value,
        "media_url": _media_url(db, light.media_id),
        "title": tr.title if tr else "",
        "meaning": tr.meaning if tr else "",
        "movement_permitted": tr.movement_permitted if tr else None,
        "direction_permitted": tr.direction_permitted if tr else None,
        "exceptions": tr.exceptions if tr else None,
        "typical_exam_situation": tr.typical_exam_situation if tr else None,
        "rules": [_rule_out(db, link.rule_id, link.rule_version) for link in rule_links],
    }


# --------------------------------------------------------------------------- #
# Global search (mixed, published-only, normalized ILIKE token match)
# --------------------------------------------------------------------------- #
def search(db: Session, q: str, *, limit: int = 40) -> list[dict]:
    needle = (q or "").strip()
    if not needle:
        return []
    like = f"%{needle}%"
    limit = max(1, min(limit, 100))
    results: list[dict] = []

    # Sections
    for s in db.scalars(
        select(TheorySection)
        .join(TheorySectionTranslation, TheorySectionTranslation.section_id == TheorySection.id)
        .where(
            TheorySection.status == VersionStatus.PUBLISHED,
            TheorySectionTranslation.language == _LANG,
            or_(
                TheorySectionTranslation.title.ilike(like),
                TheorySectionTranslation.subtitle.ilike(like),
                TheorySection.slug.ilike(like),
            ),
        )
        .distinct()
        .limit(limit)
    ):
        tr = _section_translation(db, s.id)
        results.append(
            {"type": "section", "id": s.id, "slug": s.slug,
             "title": tr.title if tr else s.slug, "subtitle": tr.subtitle if tr else ""}
        )

    # Articles
    for a in db.scalars(
        select(TheoryArticle)
        .join(TheoryArticleTranslation,
              TheoryArticleTranslation.article_version_id == TheoryArticle.current_version_id)
        .where(
            TheoryArticle.lifecycle_status == VersionStatus.PUBLISHED,
            TheoryArticleTranslation.language == _LANG,
            or_(
                TheoryArticleTranslation.title.ilike(like),
                TheoryArticleTranslation.summary.ilike(like),
                TheoryArticle.slug.ilike(like),
            ),
        )
        .distinct()
        .limit(limit)
    ):
        tr = _article_translation(db, a.current_version_id) if a.current_version_id else None
        results.append(
            {"type": "article", "id": a.id, "slug": a.slug,
             "title": tr.title if tr else a.slug, "subtitle": tr.summary if tr else ""}
        )

    # Signs (code / name / keywords / meaning)
    for sign in db.scalars(
        select(RoadSign)
        .join(RoadSignTranslation,
              RoadSignTranslation.road_sign_version_id == RoadSign.current_version_id)
        .where(
            RoadSign.lifecycle_status == VersionStatus.PUBLISHED,
            RoadSignTranslation.language == _LANG,
            or_(
                RoadSign.official_code.ilike(like),
                RoadSignTranslation.name.ilike(like),
                RoadSignTranslation.keywords.ilike(like),
                RoadSignTranslation.meaning.ilike(like),
            ),
        )
        .distinct()
        .limit(limit)
    ):
        card = _sign_card(db, sign)
        results.append(
            {"type": "sign", "id": sign.id, "code": sign.official_code,
             "family": sign.family.value, "title": card["name"], "subtitle": sign.official_code}
        )

    # Markings
    for m in db.scalars(
        select(RoadMarking)
        .join(RoadMarkingTranslation,
              RoadMarkingTranslation.road_marking_version_id == RoadMarking.current_version_id)
        .where(
            RoadMarking.lifecycle_status == VersionStatus.PUBLISHED,
            RoadMarkingTranslation.language == _LANG,
            or_(
                RoadMarkingTranslation.name.ilike(like),
                RoadMarkingTranslation.keywords.ilike(like),
                RoadMarkingTranslation.meaning.ilike(like),
            ),
        )
        .distinct()
        .limit(limit)
    ):
        tr = db.scalar(
            select(RoadMarkingTranslation).where(
                RoadMarkingTranslation.road_marking_version_id == m.current_version_id,
                RoadMarkingTranslation.language == _LANG,
            )
        )
        results.append(
            {"type": "marking", "id": m.id, "title": tr.name if tr else "",
             "subtitle": m.marking_group.value}
        )

    # Gestures
    for g in db.scalars(
        select(ControllerGesture)
        .join(ControllerGestureTranslation,
              ControllerGestureTranslation.gesture_version_id == ControllerGesture.current_version_id)
        .where(
            ControllerGesture.lifecycle_status == VersionStatus.PUBLISHED,
            ControllerGestureTranslation.language == _LANG,
            or_(
                ControllerGestureTranslation.name.ilike(like),
                ControllerGestureTranslation.keywords.ilike(like),
                ControllerGestureTranslation.allowed.ilike(like),
            ),
        )
        .distinct()
        .limit(limit)
    ):
        tr = db.scalar(
            select(ControllerGestureTranslation).where(
                ControllerGestureTranslation.gesture_version_id == g.current_version_id,
                ControllerGestureTranslation.language == _LANG,
            )
        )
        results.append(
            {"type": "gesture", "id": g.id, "title": tr.name if tr else "", "subtitle": ""}
        )

    # Lights
    for light in db.scalars(
        select(TrafficLightState)
        .join(TrafficLightStateTranslation,
              TrafficLightStateTranslation.light_version_id == TrafficLightState.current_version_id)
        .where(
            TrafficLightState.lifecycle_status == VersionStatus.PUBLISHED,
            TrafficLightStateTranslation.language == _LANG,
            or_(
                TrafficLightStateTranslation.title.ilike(like),
                TrafficLightStateTranslation.keywords.ilike(like),
                TrafficLightStateTranslation.meaning.ilike(like),
            ),
        )
        .distinct()
        .limit(limit)
    ):
        tr = db.scalar(
            select(TrafficLightStateTranslation).where(
                TrafficLightStateTranslation.light_version_id == light.current_version_id,
                TrafficLightStateTranslation.language == _LANG,
            )
        )
        results.append(
            {"type": "light", "id": light.id, "title": tr.title if tr else "",
             "subtitle": light.kind.value}
        )

    # Rules (active only, matched on code/title/text)
    for rule in db.scalars(
        select(Rule)
        .outerjoin(RuleTranslation, RuleTranslation.rule_id == Rule.id)
        .where(
            or_(
                Rule.code.ilike(like),
                RuleTranslation.title.ilike(like),
                RuleTranslation.text.ilike(like),
            )
        )
        .distinct()
        .limit(limit)
    ):
        tr = db.scalar(
            select(RuleTranslation).where(
                RuleTranslation.rule_id == rule.id, RuleTranslation.language == _LANG
            )
        )
        results.append(
            {"type": "rule", "id": rule.id, "code": rule.code,
             "title": tr.title if tr else rule.code, "subtitle": rule.code}
        )

    return results[:limit]


# --------------------------------------------------------------------------- #
# Practice -> Theory: resolve articles / catalog entries linked to a Rule code
# --------------------------------------------------------------------------- #
def by_rule(db: Session, rule_code: str) -> dict:
    rule = db.scalar(select(Rule).where(Rule.code == rule_code))
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Qoida topilmadi")

    articles: list[dict] = []
    for link in db.scalars(
        select(TheoryArticleRule).where(TheoryArticleRule.rule_id == rule.id)
    ):
        version = db.get(TheoryArticleVersion, link.article_version_id)
        if version is None:
            continue
        article = db.get(TheoryArticle, version.article_id)
        if article is None or article.lifecycle_status != VersionStatus.PUBLISHED:
            continue
        if article.current_version_id != version.id:
            continue
        if not any(a["id"] == article.id for a in articles):
            articles.append(_article_card(db, article))

    signs: list[dict] = []
    from app.domain.models import RoadSignRule

    for link in db.scalars(select(RoadSignRule).where(RoadSignRule.rule_id == rule.id)):
        version = db.get(RoadSignVersion, link.road_sign_version_id)
        if version is None:
            continue
        sign = db.get(RoadSign, version.road_sign_id)
        if sign is None or sign.lifecycle_status != VersionStatus.PUBLISHED:
            continue
        if sign.current_version_id != version.id:
            continue
        if not any(s["id"] == sign.id for s in signs):
            signs.append(_sign_card(db, sign))

    return {"rule": _rule_out(db, rule.id), "articles": articles, "signs": signs}


# --------------------------------------------------------------------------- #
# Linked-question resolution + Theory -> Practice (no-leak)
# --------------------------------------------------------------------------- #
def _article_linked_question_ids(db: Session, article_id: str) -> list[str]:
    return list(
        db.scalars(
            select(TheoryArticleQuestionLink.question_id).where(
                TheoryArticleQuestionLink.article_id == article_id
            )
        )
    )


def _article_linked_question_count(db: Session, article_id: str) -> int:
    return len(_published_linked_question_ids(db, _article_linked_question_ids(db, article_id)))


def _sign_linked_question_ids(db: Session, sign_id: str) -> list[str]:
    return list(
        db.scalars(
            select(RoadSignQuestionLink.question_id).where(
                RoadSignQuestionLink.road_sign_id == sign_id
            )
        )
    )


def _sign_linked_question_count(db: Session, sign_id: str) -> int:
    return len(_published_linked_question_ids(db, _sign_linked_question_ids(db, sign_id)))


def _published_linked_question_ids(db: Session, question_ids: list[str]) -> list[str]:
    if not question_ids:
        return []
    rows = list(
        db.scalars(
            select(Question.id).where(
                Question.id.in_(question_ids),
                Question.current_version_id.is_not(None),
                Question.lifecycle_status == VersionStatus.PUBLISHED,
            )
        )
    )
    return rows


def start_practice(
    db: Session, user: User, target_type: TheoryTargetType, target_id_or_code: str
) -> dict:
    """Start a practice session over an article's / sign's linked published questions,
    reusing the no-leak practice payload. Returns session + no-leak question payloads."""
    from app.services import practice as practice_service

    if target_type == TheoryTargetType.ARTICLE:
        article = db.get(TheoryArticle, target_id_or_code)
        if article is None or article.lifecycle_status != VersionStatus.PUBLISHED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maqola topilmadi")
        qids = _published_linked_question_ids(db, _article_linked_question_ids(db, article.id))
        target_id = article.id
    elif target_type == TheoryTargetType.SIGN:
        sign = db.scalar(
            select(RoadSign).where(
                or_(RoadSign.id == target_id_or_code, RoadSign.official_code == target_id_or_code),
                RoadSign.lifecycle_status == VersionStatus.PUBLISHED,
            )
        )
        if sign is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Belgi topilmadi")
        qids = _published_linked_question_ids(db, _sign_linked_question_ids(db, sign.id))
        target_id = sign.id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mashq faqat maqola yoki belgi uchun mavjud",
        )

    if not qids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bu mavzu bo'yicha savol topilmadi"
        )

    session = PracticeSession(
        user_id=user.id,
        category=user.profile.category if user.profile else None,  # type: ignore[arg-type]
        topic=None,
        source=PracticeSource.THEORY,
    )
    if session.category is None:
        from app.domain.enums import Category

        session.category = Category.B
    db.add(session)
    db.commit()
    db.refresh(session)

    questions = []
    for qid in qids:
        question = db.get(Question, qid)
        if question is None or question.current_version_id is None:
            continue
        version = db.get(QuestionVersion, question.current_version_id)
        if version is None:
            continue
        # Reuse the no-leak payload (prompt + option ids/text/position ONLY).
        questions.append(practice_service._payload_for_version(db, version))

    return {
        "session_id": session.id,
        "source": PracticeSource.THEORY.value,
        "target_type": target_type.value,
        "target_id": target_id,
        "questions_total": len(questions),
        "questions": questions,
    }


# --------------------------------------------------------------------------- #
# Progress (viewed set on open; practised/mastered DERIVED from performance)
# --------------------------------------------------------------------------- #
def _get_progress(
    db: Session, user: User, target_type: TheoryTargetType, target_id: str
) -> TheoryProgress | None:
    return db.scalar(
        select(TheoryProgress).where(
            TheoryProgress.user_id == user.id,
            TheoryProgress.target_type == target_type,
            TheoryProgress.target_id == target_id,
        )
    )


def _linked_qids_for_target(
    db: Session, target_type: TheoryTargetType, target_id: str
) -> list[str]:
    if target_type == TheoryTargetType.ARTICLE:
        return _article_linked_question_ids(db, target_id)
    if target_type == TheoryTargetType.SIGN:
        return _sign_linked_question_ids(db, target_id)
    return []


def _derive_state(
    db: Session, user: User, target_type: TheoryTargetType, target_id: str
) -> TheoryProgressState | None:
    """Derive practised/mastered from linked-question performance (never page views)."""
    qids = _linked_qids_for_target(db, target_type, target_id)
    if not qids:
        return None
    cfg = get_theory_config()
    # Answers (practice + mock) over the current+historical versions of the linked questions.
    version_ids = list(
        db.scalars(select(QuestionVersion.id).where(QuestionVersion.question_id.in_(qids)))
    )
    if not version_ids:
        return None

    practice_rows = list(
        db.scalars(
            select(PracticeAnswer)
            .join(PracticeSession, PracticeSession.id == PracticeAnswer.practice_session_id)
            .where(
                PracticeSession.user_id == user.id,
                PracticeAnswer.question_version_id.in_(version_ids),
            )
            .order_by(PracticeAnswer.attempted_at.desc())
        )
    )
    from app.domain.models import MockAttempt

    mock_rows = list(
        db.scalars(
            select(MockAnswer)
            .join(MockAttempt, MockAttempt.id == MockAnswer.mock_attempt_id)
            .where(
                MockAttempt.user_id == user.id,
                MockAnswer.question_version_id.in_(version_ids),
                MockAnswer.is_correct.is_not(None),
            )
        )
    )

    results: list[bool] = [bool(r.is_correct) for r in practice_rows]
    results += [bool(r.is_correct) for r in mock_rows]
    answered = len(results)
    if answered < cfg.practised_min_answers:
        return None

    recent = results[: cfg.mastery_recent_window]
    if answered >= cfg.mastered_min_answers and recent:
        accuracy = sum(1 for r in recent if r) / len(recent)
        if accuracy >= cfg.mastered_accuracy:
            return TheoryProgressState.MASTERED
    return TheoryProgressState.PRACTISED


def _current_progress_state(
    db: Session, user: User, target_type: TheoryTargetType, target_id: str
) -> str:
    """Effective state = max(stored 'viewed', derived practised/mastered)."""
    stored = _get_progress(db, user, target_type, target_id)
    stored_state = stored.state if stored else None
    derived = _derive_state(db, user, target_type, target_id)

    best = stored_state
    for candidate in (derived,):
        if candidate is None:
            continue
        if best is None or THEORY_PROGRESS_ORDER[candidate] > THEORY_PROGRESS_ORDER[best]:
            best = candidate

    # Persist an upgrade so section rollups + repeat reads are cheap (never downgrade).
    if best is not None and (stored is None or THEORY_PROGRESS_ORDER[best] > THEORY_PROGRESS_ORDER[stored.state]):
        _upsert_progress(db, user, target_type, target_id, best)

    return best.value if best else "none"


def _upsert_progress(
    db: Session,
    user: User,
    target_type: TheoryTargetType,
    target_id: str,
    state: TheoryProgressState,
) -> TheoryProgress:
    row = _get_progress(db, user, target_type, target_id)
    if row is None:
        row = TheoryProgress(
            user_id=user.id, target_type=target_type, target_id=target_id, state=state
        )
        db.add(row)
    else:
        # Never downgrade an achieved state.
        if THEORY_PROGRESS_ORDER[state] > THEORY_PROGRESS_ORDER[row.state]:
            row.state = state
    db.commit()
    db.refresh(row)
    return row


def mark_viewed(
    db: Session, user: User, target_type: TheoryTargetType, target_id: str
) -> TheoryProgress:
    """Mark a target 'viewed' (opening a page). NEVER sets mastery."""
    return _upsert_progress(db, user, target_type, target_id, TheoryProgressState.VIEWED)


def mark_progress(db: Session, user: User, target_type_raw: str, target_id: str) -> dict:
    """Client entry point: mark viewed. 'mastered' is derived server-side (client can
    never set it). Returns the effective state after any server-side derivation."""
    try:
        target_type = TheoryTargetType(target_type_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum nishon turi"
        ) from exc
    mark_viewed(db, user, target_type, target_id)
    return {
        "target_type": target_type.value,
        "target_id": target_id,
        "state": _current_progress_state(db, user, target_type, target_id),
    }


def _count_progress_in(
    db: Session, user: User, target_type: TheoryTargetType, target_ids: list[str]
) -> int:
    if not target_ids:
        return 0
    return int(
        db.scalar(
            select(func.count()).select_from(TheoryProgress).where(
                TheoryProgress.user_id == user.id,
                TheoryProgress.target_type == target_type,
                TheoryProgress.target_id.in_(target_ids),
            )
        )
        or 0
    )


# --------------------------------------------------------------------------- #
# Favorites (IDOR-safe: always scoped by session user_id)
# --------------------------------------------------------------------------- #
def list_favorites(db: Session, user: User) -> list[dict]:
    rows = list(
        db.scalars(
            select(TheoryFavorite)
            .where(TheoryFavorite.user_id == user.id)
            .order_by(TheoryFavorite.created_at.desc())
        )
    )
    return [
        {
            "id": r.id,
            "target_type": r.target_type.value,
            "target_id": r.target_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def add_favorite(db: Session, user: User, target_type_raw: str, target_id: str) -> dict:
    try:
        target_type = TheoryTargetType(target_type_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum nishon turi"
        ) from exc
    existing = db.scalar(
        select(TheoryFavorite).where(
            TheoryFavorite.user_id == user.id,
            TheoryFavorite.target_type == target_type,
            TheoryFavorite.target_id == target_id,
        )
    )
    if existing is None:
        existing = TheoryFavorite(
            user_id=user.id, target_type=target_type, target_id=target_id
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)
    return {"id": existing.id, "target_type": target_type.value, "target_id": target_id}


def remove_favorite(db: Session, user: User, favorite_id: str) -> None:
    row = db.get(TheoryFavorite, favorite_id)
    # IDOR-safe: a favorite owned by another user is treated as not found.
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topilmadi")
    db.delete(row)
    db.commit()
