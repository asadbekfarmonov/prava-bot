"""Question authoring with IMMUTABLE versions (docs/spec/02, 08).

- Admin CRUD creates DRAFT ``QuestionVersion`` rows.
- Editing a PUBLISHED (or attempt-referenced) version NEVER mutates it: a new draft
  version is created; publishing it repoints ``Question.current_version_id`` and
  supersedes the prior published version (retained for historical attempts).
- Content is authored as ``uz`` translations (prompt, short_explanation, per-option
  text + explanation). 2-5 options, exactly one correct. One or more Rules linked via
  ``QuestionVersionRule`` (snapshotting the rule version). Supporting sources tracked.
- Review lifecycle: draft -> needs_review -> reviewed -> published ->
  superseded/archived (+ needs_reverification). Publish requires the pre-publish
  validation to pass AND a reviewer/admin actor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.enums import Category, Language, Topic, VersionStatus
from app.domain.exam_config import ANSWER_OPTIONS_MAX, ANSWER_OPTIONS_MIN
from app.domain.models import (
    AnswerOption,
    AnswerOptionTranslation,
    MockAnswer,
    MockQuestion,
    PracticeAnswer,
    Question,
    QuestionMedia,
    QuestionVersion,
    QuestionVersionRule,
    QuestionVersionSource,
    QuestionVersionTranslation,
    Rule,
    User,
)
from app.services.audit import record_audit

_LANG = Language.UZ
_EDITABLE_STATUSES = {
    VersionStatus.DRAFT,
    VersionStatus.NEEDS_REVIEW,
    VersionStatus.REVIEWED,
    VersionStatus.NEEDS_REVERIFICATION,
}


class AuthoringError(ValueError):
    pass


@dataclass
class OptionInput:
    text: str
    explanation: str
    is_correct: bool


@dataclass
class SourceInput:
    url: str = ""
    note: str | None = None
    kind: str = "reference"


@dataclass
class QuestionContentInput:
    category: Category
    topic: Topic
    prompt: str
    short_explanation: str
    options: list[OptionInput]
    rule_codes: list[str] = field(default_factory=list)
    subtopic: str | None = None
    is_sign_question: bool = False
    difficulty: int = 1
    ai_assisted: bool = False
    media_id: str | None = None
    sources: list[SourceInput] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Immutability guard
# --------------------------------------------------------------------------- #
def is_version_referenced(db: Session, version_id: str) -> bool:
    """True if any attempt references the version (then it must never be mutated)."""
    if db.scalar(select(MockQuestion.id).where(MockQuestion.question_version_id == version_id).limit(1)):
        return True
    if db.scalar(select(MockAnswer.id).where(MockAnswer.question_version_id == version_id).limit(1)):
        return True
    if db.scalar(select(PracticeAnswer.id).where(PracticeAnswer.question_version_id == version_id).limit(1)):
        return True
    return False


def is_version_locked(db: Session, version: QuestionVersion) -> bool:
    """A version is immutable once published/superseded/archived OR attempt-referenced.

    ``published_at`` (not the current status) is the authoritative discriminator: a
    version that was ever published stays immutable even if a rule supersede later
    flips it to NEEDS_REVERIFICATION. Editing such a question must fork a new version.
    """
    if version.status in (VersionStatus.PUBLISHED, VersionStatus.SUPERSEDED, VersionStatus.ARCHIVED):
        return True
    if version.published_at is not None:
        return True
    return is_version_referenced(db, version.id)


# --------------------------------------------------------------------------- #
# Content application (draft versions only)
# --------------------------------------------------------------------------- #
def _clear_version_content(db: Session, version: QuestionVersion) -> None:
    for tr in list(version.translations):
        db.delete(tr)
    for opt in list(version.options):
        for otr in list(opt.translations):
            db.delete(otr)
        db.delete(opt)
    for link in list(version.rule_links):
        db.delete(link)
    for src in list(version.sources):
        db.delete(src)
    db.flush()


def _apply_content(db: Session, version: QuestionVersion, data: QuestionContentInput) -> None:
    from app.domain.enums import SourceKind

    _clear_version_content(db, version)

    version.difficulty = data.difficulty
    version.ai_assisted = data.ai_assisted
    if data.media_id:
        if db.get(QuestionMedia, data.media_id) is None:
            raise AuthoringError("Media topilmadi.")
        version.media_id = data.media_id
    else:
        version.media_id = None
    db.flush()

    db.add(
        QuestionVersionTranslation(
            question_version_id=version.id,
            language=_LANG,
            prompt=data.prompt,
            short_explanation=data.short_explanation,
        )
    )
    for position, opt in enumerate(data.options, start=1):
        option = AnswerOption(
            question_version_id=version.id, position=position, is_correct=opt.is_correct
        )
        db.add(option)
        db.flush()
        db.add(
            AnswerOptionTranslation(
                answer_option_id=option.id,
                language=_LANG,
                text=opt.text,
                explanation=opt.explanation,
            )
        )
    # Rules: snapshot each rule's current version.
    for code in dict.fromkeys(data.rule_codes):
        rule = db.scalar(select(Rule).where(Rule.code == code))
        if rule is None:
            raise AuthoringError(f"Qoida topilmadi: {code}")
        db.add(
            QuestionVersionRule(
                question_version_id=version.id, rule_id=rule.id, rule_version=rule.version
            )
        )
    for src in data.sources:
        try:
            kind = SourceKind(src.kind)
        except ValueError:
            kind = SourceKind.REFERENCE
        db.add(
            QuestionVersionSource(
                question_version_id=version.id, url=src.url, note=src.note, kind=kind
            )
        )
    db.flush()


# --------------------------------------------------------------------------- #
# Create / edit
# --------------------------------------------------------------------------- #
def create_question(db: Session, author: User, data: QuestionContentInput) -> QuestionVersion:
    question = Question(
        category=data.category,
        topic=data.topic,
        subtopic=data.subtopic,
        is_sign_question=data.is_sign_question,
        lifecycle_status=VersionStatus.DRAFT,
        created_by_user_id=author.id,
    )
    db.add(question)
    db.flush()

    version = QuestionVersion(
        question_id=question.id,
        version=1,
        status=VersionStatus.DRAFT,
        difficulty=data.difficulty,
        ai_assisted=data.ai_assisted,
        authored_by_user_id=author.id,
    )
    db.add(version)
    db.flush()
    _apply_content(db, version, data)

    record_audit(db, author, "question.create", "question_version", version.id, version=1)
    db.commit()
    db.refresh(version)
    return version


def _next_version_number(db: Session, question_id: str) -> int:
    current = db.scalar(
        select(func.max(QuestionVersion.version)).where(QuestionVersion.question_id == question_id)
    )
    return (current or 0) + 1


def _new_draft_version(db: Session, question: Question, author: User, data: QuestionContentInput) -> QuestionVersion:
    version = QuestionVersion(
        question_id=question.id,
        version=_next_version_number(db, question.id),
        status=VersionStatus.DRAFT,
        difficulty=data.difficulty,
        ai_assisted=data.ai_assisted,
        authored_by_user_id=author.id,
    )
    db.add(version)
    db.flush()
    _apply_content(db, version, data)
    return version


def edit_question(db: Session, actor: User, question_id: str, data: QuestionContentInput) -> QuestionVersion:
    """Edit a question. If the working version is locked (published/used), create a NEW
    draft version instead of mutating it (immutability)."""
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")

    # Update mutable classification on the container.
    question.category = data.category
    question.topic = data.topic
    question.subtopic = data.subtopic
    question.is_sign_question = data.is_sign_question

    # Pick the latest editable draft version (highest version, editable, not locked).
    working = db.scalar(
        select(QuestionVersion)
        .where(
            QuestionVersion.question_id == question.id,
            QuestionVersion.status.in_(_EDITABLE_STATUSES),
        )
        .order_by(QuestionVersion.version.desc())
    )
    if working is not None and not is_version_locked(db, working):
        _apply_content(db, working, data)
        # Editing resets an in-review draft back to draft.
        if working.status != VersionStatus.DRAFT:
            working.status = VersionStatus.DRAFT
        version = working
        action = "question.edit"
    else:
        version = _new_draft_version(db, question, actor, data)
        action = "question.edit_new_version"

    question.lifecycle_status = VersionStatus.DRAFT if question.current_version_id is None else question.lifecycle_status
    record_audit(db, actor, action, "question_version", version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


# --------------------------------------------------------------------------- #
# Pre-publish validation (the automated QA checklist gate)
# --------------------------------------------------------------------------- #
def _uz_translation(db: Session, version_id: str) -> QuestionVersionTranslation | None:
    return db.scalar(
        select(QuestionVersionTranslation).where(
            QuestionVersionTranslation.question_version_id == version_id,
            QuestionVersionTranslation.language == _LANG,
        )
    )


def _options(db: Session, version_id: str) -> list[AnswerOption]:
    return list(
        db.scalars(
            select(AnswerOption)
            .where(AnswerOption.question_version_id == version_id)
            .order_by(AnswerOption.position)
        )
    )


def _option_tr(db: Session, option_id: str) -> AnswerOptionTranslation | None:
    return db.scalar(
        select(AnswerOptionTranslation).where(
            AnswerOptionTranslation.answer_option_id == option_id,
            AnswerOptionTranslation.language == _LANG,
        )
    )


def validate_version_for_publish(db: Session, version: QuestionVersion) -> list[str]:
    """Return a list of validation error messages (empty => publishable)."""
    errors: list[str] = []
    options = _options(db, version.id)
    n = len(options)
    if not (ANSWER_OPTIONS_MIN <= n <= ANSWER_OPTIONS_MAX):
        errors.append(f"Variantlar soni {ANSWER_OPTIONS_MIN}-{ANSWER_OPTIONS_MAX} bo'lishi kerak (hozir {n}).")
    correct = [o for o in options if o.is_correct]
    if len(correct) != 1:
        errors.append("Aynan bitta to'g'ri variant bo'lishi kerak.")

    tr = _uz_translation(db, version.id)
    if tr is None or not tr.prompt.strip():
        errors.append("Savol matni (uz) bo'sh bo'lmasligi kerak.")
    if tr is None or not tr.short_explanation.strip():
        errors.append("Qisqa 'eslab qoling' izohi talab qilinadi.")

    for o in options:
        otr = _option_tr(db, o.id)
        if otr is None or not otr.text.strip():
            errors.append("Har bir variant matni bo'lishi kerak.")
        if otr is None or not otr.explanation.strip():
            errors.append("Har bir variant uchun izoh talab qilinadi.")

    # Correct-answer reasoning present (the correct option's explanation).
    if correct:
        cotr = _option_tr(db, correct[0].id)
        if cotr is None or not cotr.explanation.strip():
            errors.append("To'g'ri javob uchun asos (izoh) talab qilinadi.")

    # At least one current (non-superseded) rule linked.
    links = list(
        db.scalars(select(QuestionVersionRule).where(QuestionVersionRule.question_version_id == version.id))
    )
    if not links:
        errors.append("Kamida bitta amaldagi qoida bog'lanishi kerak.")
    else:
        from app.domain.enums import RuleStatus

        has_current = False
        for link in links:
            rule = db.get(Rule, link.rule_id)
            if rule is not None and rule.status == RuleStatus.ACTIVE and rule.version == link.rule_version:
                has_current = True
        if not has_current:
            errors.append("Bog'langan qoida eskirgan yoki bekor qilingan (amaldagi qoida kerak).")

    # Media accessible (metadata resolves + object present in storage).
    if version.media_id:
        media = db.get(QuestionMedia, version.media_id)
        if media is None:
            errors.append("Media topilmadi.")
        else:
            from app.storage.media_storage import get_media_storage

            if not get_media_storage().exists(media.storage_key):
                errors.append("Media obyekt xotirasida mavjud emas.")
    return errors


# --------------------------------------------------------------------------- #
# Lifecycle transitions
# --------------------------------------------------------------------------- #
def _get_version(db: Session, version_id: str) -> QuestionVersion:
    version = db.get(QuestionVersion, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Versiya topilmadi")
    return version


def submit_for_review(db: Session, actor: User, version_id: str) -> QuestionVersion:
    version = _get_version(db, version_id)
    if version.status not in (VersionStatus.DRAFT, VersionStatus.NEEDS_REVERIFICATION):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Faqat qoralamani ko'rikka yuborish mumkin")
    version.status = VersionStatus.NEEDS_REVIEW
    version.question.lifecycle_status = VersionStatus.NEEDS_REVIEW
    record_audit(db, actor, "question.submit_review", "question_version", version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


def mark_reviewed(db: Session, reviewer: User, version_id: str) -> QuestionVersion:
    version = _get_version(db, version_id)
    if version.status != VersionStatus.NEEDS_REVIEW:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Faqat ko'rikdagi versiyani tasdiqlash mumkin")
    version.status = VersionStatus.REVIEWED
    version.reviewed_by_user_id = reviewer.id
    version.question.lifecycle_status = VersionStatus.REVIEWED
    record_audit(db, reviewer, "question.review", "question_version", version.id, version=version.version)
    db.commit()
    db.refresh(version)
    return version


def publish_version(db: Session, approver: User, version_id: str) -> QuestionVersion:
    version = _get_version(db, version_id)
    if version.status not in (VersionStatus.REVIEWED, VersionStatus.NEEDS_REVIEW):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nashrdan oldin versiya ko'rikdan o'tishi kerak")

    errors = validate_version_for_publish(db, version)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Nashr validatsiyasi muvaffaqiyatsiz", "errors": errors},
        )

    # Separation-of-duties: approver == sole author => warning (or hard block if configured).
    warning = None
    settings = get_settings()
    if version.authored_by_user_id == approver.id and (
        version.reviewed_by_user_id in (None, approver.id)
    ):
        if settings.require_second_reviewer:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Muallif o'z versiyasini yakka o'zi tasdiqlay olmaydi (ikkinchi ko'rikchi talab qilinadi)",
            )
        warning = "Separation-of-duties: approver == sole author"

    question = version.question
    # Supersede the prior published version (retained for historical attempts).
    prior = db.scalar(
        select(QuestionVersion).where(
            QuestionVersion.question_id == question.id,
            QuestionVersion.status == VersionStatus.PUBLISHED,
            QuestionVersion.id != version.id,
        )
    )
    if prior is not None:
        prior.status = VersionStatus.SUPERSEDED

    now = _now()
    version.status = VersionStatus.PUBLISHED
    version.approved_by_user_id = approver.id
    if version.reviewed_by_user_id is None:
        version.reviewed_by_user_id = approver.id
    version.published_at = now
    version.verified_at = now
    question.current_version_id = version.id
    question.lifecycle_status = VersionStatus.PUBLISHED

    record_audit(
        db, approver, "question.publish", "question_version", version.id,
        version=version.version, warning=warning,
    )
    db.commit()
    db.refresh(version)
    return version


def archive_question(db: Session, actor: User, question_id: str) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    for version in list(question.versions):
        if version.status != VersionStatus.SUPERSEDED:
            version.status = VersionStatus.ARCHIVED
    question.lifecycle_status = VersionStatus.ARCHIVED
    question.current_version_id = None
    record_audit(db, actor, "question.archive", "question", question.id)
    db.commit()
    db.refresh(question)
    return question


# --------------------------------------------------------------------------- #
# Admin question listing + search/filters (docs/spec/08 search and filters)
# --------------------------------------------------------------------------- #
def list_questions(
    db: Session,
    *,
    q: str | None = None,
    topic: str | None = None,
    status_filter: str | None = None,
    has_media: bool | None = None,
    is_sign: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    stmt = select(Question)
    if topic:
        try:
            stmt = stmt.where(Question.topic == Topic(topic))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum mavzu") from exc
    if status_filter:
        try:
            stmt = stmt.where(Question.lifecycle_status == VersionStatus(status_filter))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum holat") from exc
    if is_sign is not None:
        stmt = stmt.where(Question.is_sign_question == is_sign)

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(db.scalars(stmt.order_by(Question.created_at.desc()).limit(limit).offset(offset)))

    items = []
    needle = (q or "").strip().casefold()
    for question in rows:
        working = db.scalar(
            select(QuestionVersion)
            .where(
                QuestionVersion.question_id == question.id,
                QuestionVersion.status != VersionStatus.ARCHIVED,
            )
            .order_by(QuestionVersion.version.desc())
        )
        prompt = ""
        media_id = None
        if working is not None:
            media_id = working.media_id
            tr = db.scalar(
                select(QuestionVersionTranslation).where(
                    QuestionVersionTranslation.question_version_id == working.id,
                    QuestionVersionTranslation.language == _LANG,
                )
            )
            prompt = tr.prompt if tr else ""
        if needle and needle not in prompt.casefold():
            continue
        if has_media is True and media_id is None:
            continue
        if has_media is False and media_id is not None:
            continue
        items.append(
            {
                "id": question.id,
                "topic": question.topic.value,
                "category": question.category.value,
                "is_sign_question": question.is_sign_question,
                "lifecycle_status": question.lifecycle_status.value,
                "current_version_id": question.current_version_id,
                "working_version_id": working.id if working else None,
                "prompt": prompt,
                "has_media": media_id is not None,
            }
        )
    return {"total": total, "limit": limit, "offset": offset, "items": items}
