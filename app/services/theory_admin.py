"""Admin Theory studio (docs/spec/14, 15): CRUD + immutable versioning + review/publish
for sections, articles (with content blocks), and the sign/marking/gesture/light catalogs.

Mirrors the question authoring pattern (app/services/authoring.py):
- editing a PUBLISHED/used entity FORKS a new immutable version (published_at => locked);
- publishing repoints ``current_version_id`` and supersedes the prior published version;
- lifecycle: draft -> needs_review -> reviewed -> published (+ needs_reverification);
- every mutation is audited via ``record_audit``; role-gating is enforced at the API layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    Language,
    RoadMarkingGroup,
    RoadSignFamily,
    TheoryArticleKind,
    TheoryBlockType,
    TrafficLightKind,
    VersionStatus,
)
from app.domain.models import (
    ControllerGesture,
    ControllerGestureRule,
    ControllerGestureTranslation,
    ControllerGestureVersion,
    Question,
    Rule,
    RoadMarking,
    RoadMarkingRule,
    RoadMarkingTranslation,
    RoadMarkingVersion,
    RoadSign,
    RoadSignQuestionLink,
    RoadSignRule,
    RoadSignTranslation,
    RoadSignVersion,
    TheoryArticle,
    TheoryArticleQuestionLink,
    TheoryArticleRule,
    TheoryArticleTranslation,
    TheoryArticleVersion,
    TheoryContentBlock,
    TheoryContentBlockTranslation,
    TheorySection,
    TheorySectionTranslation,
    TrafficLightState,
    TrafficLightStateRule,
    TrafficLightStateTranslation,
    TrafficLightStateVersion,
    User,
)
from app.services.audit import record_audit

_LANG = Language.UZ
_EDITABLE = {
    VersionStatus.DRAFT,
    VersionStatus.NEEDS_REVIEW,
    VersionStatus.REVIEWED,
    VersionStatus.NEEDS_REVERIFICATION,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TheoryAuthoringError(ValueError):
    pass


def _version_locked(version) -> bool:
    if version.status in (
        VersionStatus.PUBLISHED,
        VersionStatus.SUPERSEDED,
        VersionStatus.ARCHIVED,
    ):
        return True
    return version.published_at is not None


def _resolve_rule(db: Session, code: str) -> Rule:
    rule = db.scalar(select(Rule).where(Rule.code == code))
    if rule is None:
        raise TheoryAuthoringError(f"Qoida topilmadi: {code}")
    return rule


# --------------------------------------------------------------------------- #
# Sections (visibility-level status; no immutable version needed)
# --------------------------------------------------------------------------- #
def create_section(
    db: Session,
    actor: User,
    *,
    slug: str,
    title: str,
    subtitle: str = "",
    topic: str | None = None,
    position: int = 0,
    icon_media_id: str | None = None,
) -> TheorySection:
    if db.scalar(select(TheorySection).where(TheorySection.slug == slug)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu slug band")
    from app.domain.enums import Topic

    topic_enum = None
    if topic:
        try:
            topic_enum = Topic(topic)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum mavzu") from exc
    section = TheorySection(
        slug=slug,
        topic=topic_enum,
        position=position,
        icon_media_id=icon_media_id,
        status=VersionStatus.DRAFT,
    )
    db.add(section)
    db.flush()
    db.add(
        TheorySectionTranslation(
            section_id=section.id, language=_LANG, title=title, subtitle=subtitle
        )
    )
    record_audit(db, actor, "theory.section.create", "theory_section", section.id)
    db.commit()
    db.refresh(section)
    return section


def set_section_translation(
    db: Session, actor: User, section_id: str, *, language: str, title: str, subtitle: str = ""
) -> TheorySection:
    """Additive translation write (uz now, ru later) — same base row."""
    section = db.get(TheorySection, section_id)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bo'lim topilmadi")
    try:
        lang = Language(language)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum til") from exc
    tr = db.scalar(
        select(TheorySectionTranslation).where(
            TheorySectionTranslation.section_id == section_id,
            TheorySectionTranslation.language == lang,
        )
    )
    if tr is None:
        db.add(
            TheorySectionTranslation(
                section_id=section_id, language=lang, title=title, subtitle=subtitle
            )
        )
    else:
        tr.title = title
        tr.subtitle = subtitle
    record_audit(db, actor, "theory.section.translate", "theory_section", section_id)
    db.commit()
    db.refresh(section)
    return section


def publish_section(db: Session, actor: User, section_id: str) -> TheorySection:
    section = db.get(TheorySection, section_id)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bo'lim topilmadi")
    section.status = VersionStatus.PUBLISHED
    record_audit(db, actor, "theory.section.publish", "theory_section", section.id)
    db.commit()
    db.refresh(section)
    return section


# --------------------------------------------------------------------------- #
# Articles (immutable versions + structured blocks)
# --------------------------------------------------------------------------- #
@dataclass
class BlockInput:
    type: str
    body: str = ""
    media_id: str | None = None
    rule_code: str | None = None
    ref_question_id: str | None = None
    data: dict | None = None


@dataclass
class ArticleContentInput:
    title: str
    summary: str = ""
    hero_media_id: str | None = None
    ai_assisted: bool = False
    blocks: list[BlockInput] = field(default_factory=list)
    rule_codes: list[str] = field(default_factory=list)
    question_ids: list[str] = field(default_factory=list)


def create_article(
    db: Session,
    actor: User,
    *,
    section_id: str,
    slug: str,
    kind: str = "lesson",
    position: int = 0,
) -> TheoryArticleVersion:
    section = db.get(TheorySection, section_id)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bo'lim topilmadi")
    try:
        kind_enum = TheoryArticleKind(kind)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum tur") from exc
    if db.scalar(
        select(TheoryArticle).where(
            TheoryArticle.section_id == section_id, TheoryArticle.slug == slug
        )
    ) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu slug band")

    article = TheoryArticle(
        section_id=section_id,
        slug=slug,
        kind=kind_enum,
        position=position,
        lifecycle_status=VersionStatus.DRAFT,
    )
    db.add(article)
    db.flush()
    version = TheoryArticleVersion(
        article_id=article.id, version=1, status=VersionStatus.DRAFT,
        authored_by_user_id=actor.id,
    )
    db.add(version)
    db.flush()
    db.add(TheoryArticleTranslation(article_version_id=version.id, language=_LANG, title=slug))
    record_audit(db, actor, "theory.article.create", "theory_article_version", version.id, version=1)
    db.commit()
    db.refresh(version)
    return version


def _apply_article_content(
    db: Session, version: TheoryArticleVersion, data: ArticleContentInput
) -> None:
    # Clear existing content of this (editable) version.
    for tr in list(version.translations):
        db.delete(tr)
    for block in list(version.blocks):
        for btr in list(block.translations):
            db.delete(btr)
        db.delete(block)
    for link in list(version.rule_links):
        db.delete(link)
    db.flush()

    version.hero_media_id = data.hero_media_id
    version.ai_assisted = data.ai_assisted
    db.add(
        TheoryArticleTranslation(
            article_version_id=version.id, language=_LANG,
            title=data.title, summary=data.summary,
        )
    )
    for position, blk in enumerate(data.blocks, start=1):
        try:
            btype = TheoryBlockType(blk.type)
        except ValueError as exc:
            raise TheoryAuthoringError(f"Noma'lum blok turi: {blk.type}") from exc
        rule_id = None
        if blk.rule_code:
            rule_id = _resolve_rule(db, blk.rule_code).id
        block = TheoryContentBlock(
            article_version_id=version.id,
            position=position,
            type=btype,
            media_id=blk.media_id,
            rule_id=rule_id,
            ref_question_id=blk.ref_question_id,
            data_json=blk.data,
        )
        db.add(block)
        db.flush()
        db.add(
            TheoryContentBlockTranslation(
                block_id=block.id, language=_LANG, body=blk.body or ""
            )
        )
    for code in dict.fromkeys(data.rule_codes):
        rule = _resolve_rule(db, code)
        db.add(
            TheoryArticleRule(
                article_version_id=version.id, rule_id=rule.id, rule_version=rule.version
            )
        )
    db.flush()


def _sync_article_question_links(db: Session, article: TheoryArticle, question_ids: list[str]) -> None:
    existing = {
        link.question_id: link
        for link in db.scalars(
            select(TheoryArticleQuestionLink).where(
                TheoryArticleQuestionLink.article_id == article.id
            )
        )
    }
    wanted = set(dict.fromkeys(question_ids))
    for qid in wanted - set(existing):
        if db.get(Question, qid) is None:
            raise TheoryAuthoringError(f"Savol topilmadi: {qid}")
        db.add(TheoryArticleQuestionLink(article_id=article.id, question_id=qid))
    for qid, link in existing.items():
        if qid not in wanted:
            db.delete(link)
    db.flush()


def _next_version_number(db: Session, model, fk_attr, container_id: str) -> int:
    current = db.scalar(
        select(func.max(model.version)).where(getattr(model, fk_attr) == container_id)
    )
    return (current or 0) + 1


def edit_article(
    db: Session, actor: User, article_id: str, data: ArticleContentInput
) -> TheoryArticleVersion:
    article = db.get(TheoryArticle, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maqola topilmadi")

    working = db.scalar(
        select(TheoryArticleVersion)
        .where(
            TheoryArticleVersion.article_id == article.id,
            TheoryArticleVersion.status.in_(_EDITABLE),
        )
        .order_by(TheoryArticleVersion.version.desc())
    )
    try:
        if working is not None and not _version_locked(working):
            _apply_article_content(db, working, data)
            if working.status != VersionStatus.DRAFT:
                working.status = VersionStatus.DRAFT
            version = working
            action = "theory.article.edit"
        else:
            version = TheoryArticleVersion(
                article_id=article.id,
                version=_next_version_number(
                    db, TheoryArticleVersion, "article_id", article.id
                ),
                status=VersionStatus.DRAFT,
                authored_by_user_id=actor.id,
            )
            db.add(version)
            db.flush()
            _apply_article_content(db, version, data)
            action = "theory.article.edit_new_version"
        _sync_article_question_links(db, article, data.question_ids)
    except TheoryAuthoringError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    record_audit(db, actor, action, "theory_article_version", version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


# --------------------------------------------------------------------------- #
# Generic version lifecycle (articles + catalogs share it)
# --------------------------------------------------------------------------- #
def _get_or_404(db: Session, model, obj_id: str, label: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=label)
    return obj


def _submit_for_review(db: Session, actor: User, version, container, entity: str):
    if version.status not in (VersionStatus.DRAFT, VersionStatus.NEEDS_REVERIFICATION):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Faqat qoralamani yuborish mumkin")
    version.status = VersionStatus.NEEDS_REVIEW
    container.lifecycle_status = VersionStatus.NEEDS_REVIEW
    record_audit(db, actor, f"{entity}.submit_review", entity, version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


def _mark_reviewed(db: Session, actor: User, version, container, entity: str):
    if version.status != VersionStatus.NEEDS_REVIEW:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Faqat ko'rikdagi versiyani tasdiqlash mumkin")
    version.status = VersionStatus.REVIEWED
    version.reviewed_by_user_id = actor.id
    container.lifecycle_status = VersionStatus.REVIEWED
    record_audit(db, actor, f"{entity}.review", entity, version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


def _publish(db: Session, actor: User, version, container, model_version, fk_attr, entity: str):
    if version.status not in (VersionStatus.REVIEWED, VersionStatus.NEEDS_REVIEW):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nashrdan oldin ko'rik kerak")
    # Supersede the prior published version (retained for history).
    prior = db.scalar(
        select(model_version).where(
            getattr(model_version, fk_attr) == getattr(version, fk_attr),
            model_version.status == VersionStatus.PUBLISHED,
            model_version.id != version.id,
        )
    )
    if prior is not None:
        prior.status = VersionStatus.SUPERSEDED
    now = _now()
    version.status = VersionStatus.PUBLISHED
    version.approved_by_user_id = actor.id
    if version.reviewed_by_user_id is None:
        version.reviewed_by_user_id = actor.id
    version.published_at = now
    version.verified_at = now
    container.current_version_id = version.id
    container.lifecycle_status = VersionStatus.PUBLISHED
    record_audit(db, actor, f"{entity}.publish", entity, version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


def _set_verified(db: Session, actor: User, version, entity: str):
    version.verified_at = _now()
    record_audit(db, actor, f"{entity}.verify", entity, version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


# Article lifecycle wrappers
def submit_article_review(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, TheoryArticleVersion, version_id, "Versiya topilmadi")
    return _submit_for_review(db, actor, v, v.article, "theory_article_version")


def review_article(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, TheoryArticleVersion, version_id, "Versiya topilmadi")
    return _mark_reviewed(db, actor, v, v.article, "theory_article_version")


def publish_article(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, TheoryArticleVersion, version_id, "Versiya topilmadi")
    return _publish(db, actor, v, v.article, TheoryArticleVersion, "article_id", "theory_article_version")


# --------------------------------------------------------------------------- #
# Road signs (immutable versions)
# --------------------------------------------------------------------------- #
@dataclass
class SignContentInput:
    name: str
    meaning: str = ""
    driver_action: str = ""
    important: str | None = None
    exam_trap: str | None = None
    memory_tip: str | None = None
    keywords: str | None = None
    media_id: str | None = None
    ai_assisted: bool = False
    rule_codes: list[str] = field(default_factory=list)
    question_ids: list[str] = field(default_factory=list)


def create_sign(
    db: Session, actor: User, *, official_code: str, family: str,
    media_id: str | None = None, position: int = 0,
) -> RoadSignVersion:
    try:
        fam = RoadSignFamily(family)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum oila") from exc
    sign = RoadSign(
        official_code=official_code, family=fam, media_id=media_id,
        position=position, lifecycle_status=VersionStatus.DRAFT,
    )
    db.add(sign)
    db.flush()
    version = RoadSignVersion(
        road_sign_id=sign.id, version=1, status=VersionStatus.DRAFT,
        media_id=media_id, authored_by_user_id=actor.id,
    )
    db.add(version)
    db.flush()
    db.add(RoadSignTranslation(road_sign_version_id=version.id, language=_LANG, name=official_code))
    record_audit(db, actor, "road_sign.create", "road_sign_version", version.id, version=1)
    db.commit()
    db.refresh(version)
    return version


def _apply_sign_content(db: Session, version: RoadSignVersion, data: SignContentInput) -> None:
    for tr in list(version.translations):
        db.delete(tr)
    for link in list(version.rule_links):
        db.delete(link)
    db.flush()
    version.media_id = data.media_id
    version.ai_assisted = data.ai_assisted
    db.add(
        RoadSignTranslation(
            road_sign_version_id=version.id, language=_LANG,
            name=data.name, meaning=data.meaning, driver_action=data.driver_action,
            important=data.important, exam_trap=data.exam_trap,
            memory_tip=data.memory_tip, keywords=data.keywords,
        )
    )
    for code in dict.fromkeys(data.rule_codes):
        rule = _resolve_rule(db, code)
        db.add(
            RoadSignRule(
                road_sign_version_id=version.id, rule_id=rule.id, rule_version=rule.version
            )
        )
    db.flush()


def _sync_sign_question_links(db: Session, sign: RoadSign, question_ids: list[str]) -> None:
    existing = {
        link.question_id: link
        for link in db.scalars(
            select(RoadSignQuestionLink).where(RoadSignQuestionLink.road_sign_id == sign.id)
        )
    }
    wanted = set(dict.fromkeys(question_ids))
    for qid in wanted - set(existing):
        if db.get(Question, qid) is None:
            raise TheoryAuthoringError(f"Savol topilmadi: {qid}")
        db.add(RoadSignQuestionLink(road_sign_id=sign.id, question_id=qid))
    for qid, link in existing.items():
        if qid not in wanted:
            db.delete(link)
    db.flush()


def edit_sign(db: Session, actor: User, sign_id: str, data: SignContentInput) -> RoadSignVersion:
    sign = db.get(RoadSign, sign_id)
    if sign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Belgi topilmadi")
    working = db.scalar(
        select(RoadSignVersion)
        .where(RoadSignVersion.road_sign_id == sign.id, RoadSignVersion.status.in_(_EDITABLE))
        .order_by(RoadSignVersion.version.desc())
    )
    try:
        if working is not None and not _version_locked(working):
            _apply_sign_content(db, working, data)
            if working.status != VersionStatus.DRAFT:
                working.status = VersionStatus.DRAFT
            version = working
            action = "road_sign.edit"
        else:
            version = RoadSignVersion(
                road_sign_id=sign.id,
                version=_next_version_number(db, RoadSignVersion, "road_sign_id", sign.id),
                status=VersionStatus.DRAFT,
                authored_by_user_id=actor.id,
            )
            db.add(version)
            db.flush()
            _apply_sign_content(db, version, data)
            action = "road_sign.edit_new_version"
        _sync_sign_question_links(db, sign, data.question_ids)
    except TheoryAuthoringError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record_audit(db, actor, action, "road_sign_version", version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


def submit_sign_review(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, RoadSignVersion, version_id, "Versiya topilmadi")
    return _submit_for_review(db, actor, v, v.road_sign, "road_sign_version")


def review_sign(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, RoadSignVersion, version_id, "Versiya topilmadi")
    return _mark_reviewed(db, actor, v, v.road_sign, "road_sign_version")


def publish_sign(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, RoadSignVersion, version_id, "Versiya topilmadi")
    return _publish(db, actor, v, v.road_sign, RoadSignVersion, "road_sign_id", "road_sign_version")


# --------------------------------------------------------------------------- #
# Road markings (immutable versions)
# --------------------------------------------------------------------------- #
@dataclass
class MarkingContentInput:
    name: str
    meaning: str = ""
    can_cross: str | None = None
    can_stop_park: str | None = None
    conflict_rule: str | None = None
    exam_trap: str | None = None
    memory_tip: str | None = None
    keywords: str | None = None
    media_id: str | None = None
    ai_assisted: bool = False
    rule_codes: list[str] = field(default_factory=list)


def create_marking(
    db: Session, actor: User, *, group: str, code: str | None = None,
    media_id: str | None = None, position: int = 0,
) -> RoadMarkingVersion:
    try:
        grp = RoadMarkingGroup(group)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum guruh") from exc
    marking = RoadMarking(
        code=code, marking_group=grp, media_id=media_id,
        position=position, lifecycle_status=VersionStatus.DRAFT,
    )
    db.add(marking)
    db.flush()
    version = RoadMarkingVersion(
        road_marking_id=marking.id, version=1, status=VersionStatus.DRAFT,
        media_id=media_id, authored_by_user_id=actor.id,
    )
    db.add(version)
    db.flush()
    db.add(RoadMarkingTranslation(road_marking_version_id=version.id, language=_LANG, name=code or ""))
    record_audit(db, actor, "road_marking.create", "road_marking_version", version.id, version=1)
    db.commit()
    db.refresh(version)
    return version


def _apply_marking_content(db: Session, version: RoadMarkingVersion, data: MarkingContentInput) -> None:
    for tr in list(version.translations):
        db.delete(tr)
    for link in list(version.rule_links):
        db.delete(link)
    db.flush()
    version.media_id = data.media_id
    version.ai_assisted = data.ai_assisted
    db.add(
        RoadMarkingTranslation(
            road_marking_version_id=version.id, language=_LANG,
            name=data.name, meaning=data.meaning, can_cross=data.can_cross,
            can_stop_park=data.can_stop_park, conflict_rule=data.conflict_rule,
            exam_trap=data.exam_trap, memory_tip=data.memory_tip, keywords=data.keywords,
        )
    )
    for code in dict.fromkeys(data.rule_codes):
        rule = _resolve_rule(db, code)
        db.add(
            RoadMarkingRule(
                road_marking_version_id=version.id, rule_id=rule.id, rule_version=rule.version
            )
        )
    db.flush()


def edit_marking(db: Session, actor: User, marking_id: str, data: MarkingContentInput) -> RoadMarkingVersion:
    marking = db.get(RoadMarking, marking_id)
    if marking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chiziq topilmadi")
    working = db.scalar(
        select(RoadMarkingVersion)
        .where(RoadMarkingVersion.road_marking_id == marking.id, RoadMarkingVersion.status.in_(_EDITABLE))
        .order_by(RoadMarkingVersion.version.desc())
    )
    try:
        if working is not None and not _version_locked(working):
            _apply_marking_content(db, working, data)
            if working.status != VersionStatus.DRAFT:
                working.status = VersionStatus.DRAFT
            version = working
            action = "road_marking.edit"
        else:
            version = RoadMarkingVersion(
                road_marking_id=marking.id,
                version=_next_version_number(db, RoadMarkingVersion, "road_marking_id", marking.id),
                status=VersionStatus.DRAFT, authored_by_user_id=actor.id,
            )
            db.add(version)
            db.flush()
            _apply_marking_content(db, version, data)
            action = "road_marking.edit_new_version"
    except TheoryAuthoringError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record_audit(db, actor, action, "road_marking_version", version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


def submit_marking_review(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, RoadMarkingVersion, version_id, "Versiya topilmadi")
    return _submit_for_review(db, actor, v, v.road_marking, "road_marking_version")


def review_marking(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, RoadMarkingVersion, version_id, "Versiya topilmadi")
    return _mark_reviewed(db, actor, v, v.road_marking, "road_marking_version")


def publish_marking(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, RoadMarkingVersion, version_id, "Versiya topilmadi")
    return _publish(db, actor, v, v.road_marking, RoadMarkingVersion, "road_marking_id", "road_marking_version")


# --------------------------------------------------------------------------- #
# Controller gestures (immutable versions)
# --------------------------------------------------------------------------- #
@dataclass
class GestureContentInput:
    name: str
    position_desc: str = ""
    allowed: str = ""
    forbidden: str = ""
    memory_tip: str | None = None
    keywords: str | None = None
    media_id: str | None = None
    animation_media_id: str | None = None
    ai_assisted: bool = False
    rule_codes: list[str] = field(default_factory=list)


def create_gesture(
    db: Session, actor: User, *, code: str | None = None,
    media_id: str | None = None, animation_media_id: str | None = None, position: int = 0,
) -> ControllerGestureVersion:
    gesture = ControllerGesture(
        code=code, media_id=media_id, animation_media_id=animation_media_id,
        position=position, lifecycle_status=VersionStatus.DRAFT,
    )
    db.add(gesture)
    db.flush()
    version = ControllerGestureVersion(
        gesture_id=gesture.id, version=1, status=VersionStatus.DRAFT,
        media_id=media_id, animation_media_id=animation_media_id, authored_by_user_id=actor.id,
    )
    db.add(version)
    db.flush()
    db.add(ControllerGestureTranslation(gesture_version_id=version.id, language=_LANG, name=code or ""))
    record_audit(db, actor, "controller_gesture.create", "controller_gesture_version", version.id, version=1)
    db.commit()
    db.refresh(version)
    return version


def _apply_gesture_content(db: Session, version: ControllerGestureVersion, data: GestureContentInput) -> None:
    for tr in list(version.translations):
        db.delete(tr)
    for link in list(version.rule_links):
        db.delete(link)
    db.flush()
    version.media_id = data.media_id
    version.animation_media_id = data.animation_media_id
    version.ai_assisted = data.ai_assisted
    db.add(
        ControllerGestureTranslation(
            gesture_version_id=version.id, language=_LANG, name=data.name,
            position_desc=data.position_desc, allowed=data.allowed, forbidden=data.forbidden,
            memory_tip=data.memory_tip, keywords=data.keywords,
        )
    )
    for code in dict.fromkeys(data.rule_codes):
        rule = _resolve_rule(db, code)
        db.add(
            ControllerGestureRule(
                gesture_version_id=version.id, rule_id=rule.id, rule_version=rule.version
            )
        )
    db.flush()


def edit_gesture(db: Session, actor: User, gesture_id: str, data: GestureContentInput) -> ControllerGestureVersion:
    gesture = db.get(ControllerGesture, gesture_id)
    if gesture is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ishora topilmadi")
    working = db.scalar(
        select(ControllerGestureVersion)
        .where(ControllerGestureVersion.gesture_id == gesture.id, ControllerGestureVersion.status.in_(_EDITABLE))
        .order_by(ControllerGestureVersion.version.desc())
    )
    try:
        if working is not None and not _version_locked(working):
            _apply_gesture_content(db, working, data)
            if working.status != VersionStatus.DRAFT:
                working.status = VersionStatus.DRAFT
            version = working
            action = "controller_gesture.edit"
        else:
            version = ControllerGestureVersion(
                gesture_id=gesture.id,
                version=_next_version_number(db, ControllerGestureVersion, "gesture_id", gesture.id),
                status=VersionStatus.DRAFT, authored_by_user_id=actor.id,
            )
            db.add(version)
            db.flush()
            _apply_gesture_content(db, version, data)
            action = "controller_gesture.edit_new_version"
    except TheoryAuthoringError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record_audit(db, actor, action, "controller_gesture_version", version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


def submit_gesture_review(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, ControllerGestureVersion, version_id, "Versiya topilmadi")
    return _submit_for_review(db, actor, v, v.gesture, "controller_gesture_version")


def review_gesture(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, ControllerGestureVersion, version_id, "Versiya topilmadi")
    return _mark_reviewed(db, actor, v, v.gesture, "controller_gesture_version")


def publish_gesture(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, ControllerGestureVersion, version_id, "Versiya topilmadi")
    return _publish(db, actor, v, v.gesture, ControllerGestureVersion, "gesture_id", "controller_gesture_version")


# --------------------------------------------------------------------------- #
# Traffic-light states (immutable versions)
# --------------------------------------------------------------------------- #
@dataclass
class LightContentInput:
    title: str
    meaning: str = ""
    movement_permitted: str | None = None
    direction_permitted: str | None = None
    exceptions: str | None = None
    typical_exam_situation: str | None = None
    keywords: str | None = None
    media_id: str | None = None
    ai_assisted: bool = False
    rule_codes: list[str] = field(default_factory=list)


def create_light(
    db: Session, actor: User, *, kind: str, media_id: str | None = None, position: int = 0,
) -> TrafficLightStateVersion:
    try:
        kind_enum = TrafficLightKind(kind)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum tur") from exc
    light = TrafficLightState(
        kind=kind_enum, media_id=media_id, position=position, lifecycle_status=VersionStatus.DRAFT
    )
    db.add(light)
    db.flush()
    version = TrafficLightStateVersion(
        light_id=light.id, version=1, status=VersionStatus.DRAFT,
        media_id=media_id, authored_by_user_id=actor.id,
    )
    db.add(version)
    db.flush()
    db.add(TrafficLightStateTranslation(light_version_id=version.id, language=_LANG, title=kind))
    record_audit(db, actor, "traffic_light.create", "traffic_light_state_version", version.id, version=1)
    db.commit()
    db.refresh(version)
    return version


def _apply_light_content(db: Session, version: TrafficLightStateVersion, data: LightContentInput) -> None:
    for tr in list(version.translations):
        db.delete(tr)
    for link in list(version.rule_links):
        db.delete(link)
    db.flush()
    version.media_id = data.media_id
    version.ai_assisted = data.ai_assisted
    db.add(
        TrafficLightStateTranslation(
            light_version_id=version.id, language=_LANG, title=data.title, meaning=data.meaning,
            movement_permitted=data.movement_permitted, direction_permitted=data.direction_permitted,
            exceptions=data.exceptions, typical_exam_situation=data.typical_exam_situation,
            keywords=data.keywords,
        )
    )
    for code in dict.fromkeys(data.rule_codes):
        rule = _resolve_rule(db, code)
        db.add(
            TrafficLightStateRule(
                light_version_id=version.id, rule_id=rule.id, rule_version=rule.version
            )
        )
    db.flush()


def edit_light(db: Session, actor: User, light_id: str, data: LightContentInput) -> TrafficLightStateVersion:
    light = db.get(TrafficLightState, light_id)
    if light is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal topilmadi")
    working = db.scalar(
        select(TrafficLightStateVersion)
        .where(TrafficLightStateVersion.light_id == light.id, TrafficLightStateVersion.status.in_(_EDITABLE))
        .order_by(TrafficLightStateVersion.version.desc())
    )
    try:
        if working is not None and not _version_locked(working):
            _apply_light_content(db, working, data)
            if working.status != VersionStatus.DRAFT:
                working.status = VersionStatus.DRAFT
            version = working
            action = "traffic_light.edit"
        else:
            version = TrafficLightStateVersion(
                light_id=light.id,
                version=_next_version_number(db, TrafficLightStateVersion, "light_id", light.id),
                status=VersionStatus.DRAFT, authored_by_user_id=actor.id,
            )
            db.add(version)
            db.flush()
            _apply_light_content(db, version, data)
            action = "traffic_light.edit_new_version"
    except TheoryAuthoringError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record_audit(db, actor, action, "traffic_light_state_version", version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


def submit_light_review(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, TrafficLightStateVersion, version_id, "Versiya topilmadi")
    return _submit_for_review(db, actor, v, v.light, "traffic_light_state_version")


def review_light(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, TrafficLightStateVersion, version_id, "Versiya topilmadi")
    return _mark_reviewed(db, actor, v, v.light, "traffic_light_state_version")


def publish_light(db: Session, actor: User, version_id: str):
    v = _get_or_404(db, TrafficLightStateVersion, version_id, "Versiya topilmadi")
    return _publish(db, actor, v, v.light, TrafficLightStateVersion, "light_id", "traffic_light_state_version")


def set_verified(db: Session, actor: User, entity: str, version_id: str):
    model_map = {
        "article": TheoryArticleVersion,
        "sign": RoadSignVersion,
        "marking": RoadMarkingVersion,
        "gesture": ControllerGestureVersion,
        "light": TrafficLightStateVersion,
    }
    model = model_map.get(entity)
    if model is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum nishon")
    v = _get_or_404(db, model, version_id, "Versiya topilmadi")
    return _set_verified(db, actor, v, f"theory_{entity}")


# --------------------------------------------------------------------------- #
# Review queue (needs_review + needs_reverification across theory + catalogs)
# --------------------------------------------------------------------------- #
def review_queue(db: Session) -> dict:
    flagged = (VersionStatus.NEEDS_REVIEW, VersionStatus.NEEDS_REVERIFICATION)
    out: dict = {}

    def collect(model, id_attr, label):
        rows = list(db.scalars(select(model).where(model.status.in_(flagged))))
        return [
            {
                "version_id": r.id,
                "container_id": getattr(r, id_attr),
                "version": r.version,
                "status": r.status.value,
            }
            for r in rows
        ]

    out["articles"] = collect(TheoryArticleVersion, "article_id", "article")
    out["signs"] = collect(RoadSignVersion, "road_sign_id", "sign")
    out["markings"] = collect(RoadMarkingVersion, "road_marking_id", "marking")
    out["gestures"] = collect(ControllerGestureVersion, "gesture_id", "gesture")
    out["lights"] = collect(TrafficLightStateVersion, "light_id", "light")
    return out
