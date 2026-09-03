"""Training-assessment domain (docs/spec/20 Phase 7).

Separate from the official mock-exam system; the official exam configuration is never touched.
Published AssessmentVersions are immutable; editing a published assessment forks a new draft
version. Attempts pin the current published QuestionVersion of each selected question, so later
question or assessment edits never change historical attempts. Live attempt payloads never leak
correctness/explanations before the configured reveal point.
"""

from __future__ import annotations

import random
import re
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    AssessmentAttemptStatus,
    AssessmentRevealMode,
    AssessmentSelectionMode,
    AssessmentStatus,
    AssessmentType,
    Category,
    Language,
    Topic,
    VersionStatus,
)
from app.domain.models import (
    AnswerOption,
    AnswerOptionTranslation,
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentAttemptQuestion,
    AssessmentQuestion,
    AssessmentVersion,
    Question,
    QuestionVersion,
    QuestionVersionTranslation,
    User,
)

_LANG = Language.UZ
# Types whose question_count is locked (docs/spec/20 Phase 8).
_LOCKED_COUNTS = {AssessmentType.ENDURANCE_50: 50, AssessmentType.ENDURANCE_100: 100}


class AssessmentError(Exception):
    """Domain error -> mapped to HTTP 422 by the routers."""


def _slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return base or "test"


def _unique_slug(db: Session, desired: str) -> str:
    slug = desired
    n = 2
    while db.scalar(select(Assessment.id).where(Assessment.slug == slug)) is not None:
        slug = f"{desired}-{n}"
        n += 1
    return slug


# --------------------------------------------------------------------------- #
# Eligible pool (current published question containers matching filters)
# --------------------------------------------------------------------------- #
def _eligible_question_query(topics: list[str] | None, difficulties: list[int] | None):
    q = (
        select(Question.id)
        .join(QuestionVersion, Question.current_version_id == QuestionVersion.id)
        .where(
            QuestionVersion.status == VersionStatus.PUBLISHED,
            Question.category == Category.B,
        )
    )
    if topics:
        valid = [Topic(t) for t in topics if t in Topic._value2member_map_]
        if valid:
            q = q.where(Question.topic.in_(valid))
    if difficulties:
        q = q.where(QuestionVersion.difficulty.in_(difficulties))
    return q


def _filters(version: AssessmentVersion) -> tuple[list[str] | None, list[int] | None]:
    topics = (version.topic_filters_json or {}).get("topics") if version.topic_filters_json else None
    diffs = (version.difficulty_filters_json or {}).get("difficulties") if version.difficulty_filters_json else None
    return topics, diffs


def eligible_count(db: Session, version: AssessmentVersion) -> int:
    if version.selection_mode == AssessmentSelectionMode.MANUAL:
        # Manual: how many pinned questions currently resolve to a published version.
        rows = db.scalars(
            select(AssessmentQuestion.question_id).where(
                AssessmentQuestion.assessment_version_id == version.id
            )
        ).all()
        if not rows:
            return 0
        count = 0
        for qid in rows:
            q = db.get(Question, qid)
            if q and q.current_version_id:
                v = db.get(QuestionVersion, q.current_version_id)
                if v and v.status == VersionStatus.PUBLISHED:
                    count += 1
        return count
    topics, diffs = _filters(version)
    return int(db.scalar(select(func.count()).select_from(_eligible_question_query(topics, diffs).subquery())) or 0)


# --------------------------------------------------------------------------- #
# Admin: create / edit (fork) / publish / archive
# --------------------------------------------------------------------------- #
def _latest_version(db: Session, assessment: Assessment) -> AssessmentVersion | None:
    return db.scalar(
        select(AssessmentVersion)
        .where(AssessmentVersion.assessment_id == assessment.id)
        .order_by(AssessmentVersion.version.desc())
    )


def _editable_version(db: Session, assessment: Assessment, actor: User) -> AssessmentVersion:
    """Return a draft version to edit; fork a new draft if the latest is published."""
    latest = _latest_version(db, assessment)
    if latest is not None and latest.status != VersionStatus.PUBLISHED:
        return latest
    next_num = (latest.version + 1) if latest else 1
    fork = AssessmentVersion(
        assessment_id=assessment.id,
        version=next_num,
        title=latest.title if latest else "",
        description=latest.description if latest else None,
        selection_mode=latest.selection_mode if latest else AssessmentSelectionMode.MANUAL,
        question_count=latest.question_count if latest else 0,
        time_limit_seconds=latest.time_limit_seconds if latest else None,
        pass_correct=latest.pass_correct if latest else None,
        show_explanations_after=latest.show_explanations_after if latest else AssessmentRevealMode.EACH_ANSWER,
        topic_filters_json=latest.topic_filters_json if latest else None,
        difficulty_filters_json=latest.difficulty_filters_json if latest else None,
        randomize_order=latest.randomize_order if latest else False,
        status=VersionStatus.DRAFT,
        authored_by_user_id=actor.id,
    )
    db.add(fork)
    db.flush()
    if latest is not None:
        for aq in latest.questions:
            db.add(AssessmentQuestion(assessment_version_id=fork.id, question_id=aq.question_id, position=aq.position))
    db.flush()
    return fork


def create_assessment(db: Session, actor: User, *, type: str, title: str, description: str | None = None) -> Assessment:
    try:
        atype = AssessmentType(type)
    except ValueError as exc:
        raise AssessmentError("Noma'lum test turi") from exc
    assessment = Assessment(
        slug=_unique_slug(db, _slugify(title)),
        type=atype,
        status=AssessmentStatus.DRAFT,
        created_by_user_id=actor.id,
    )
    db.add(assessment)
    db.flush()
    version = AssessmentVersion(
        assessment_id=assessment.id,
        version=1,
        title=title.strip() or "Test",
        description=description,
        selection_mode=AssessmentSelectionMode.MANUAL,
        question_count=_LOCKED_COUNTS.get(atype, 0),
        show_explanations_after=AssessmentRevealMode.EACH_ANSWER,
        randomize_order=False,
        status=VersionStatus.DRAFT,
        authored_by_user_id=actor.id,
    )
    db.add(version)
    db.flush()
    return assessment


def update_assessment(db: Session, actor: User, assessment_id: str, data: dict) -> AssessmentVersion:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test topilmadi")
    version = _editable_version(db, assessment, actor)

    if "title" in data and data["title"] is not None:
        version.title = str(data["title"]).strip() or version.title
    if "description" in data:
        version.description = data["description"]
    if "selection_mode" in data and data["selection_mode"]:
        try:
            version.selection_mode = AssessmentSelectionMode(data["selection_mode"])
        except ValueError as exc:
            raise AssessmentError("Noma'lum tanlash usuli") from exc
    if "time_limit_seconds" in data:
        version.time_limit_seconds = data["time_limit_seconds"]
    if "pass_correct" in data:
        version.pass_correct = data["pass_correct"]
    if "show_explanations_after" in data and data["show_explanations_after"]:
        try:
            version.show_explanations_after = AssessmentRevealMode(data["show_explanations_after"])
        except ValueError as exc:
            raise AssessmentError("Noma'lum izoh rejimi") from exc
    if "randomize_order" in data:
        version.randomize_order = bool(data["randomize_order"])
    if "topic_filters" in data:
        version.topic_filters_json = {"topics": data["topic_filters"]} if data["topic_filters"] else None
    if "difficulty_filters" in data:
        version.difficulty_filters_json = {"difficulties": data["difficulty_filters"]} if data["difficulty_filters"] else None

    # question_count: locked for endurance types.
    locked = _LOCKED_COUNTS.get(assessment.type)
    if locked is not None:
        version.question_count = locked
    elif "question_count" in data and data["question_count"] is not None:
        version.question_count = int(data["question_count"])

    # Manual question list (ordered).
    if version.selection_mode == AssessmentSelectionMode.MANUAL and "question_ids" in data and data["question_ids"] is not None:
        for aq in list(version.questions):
            db.delete(aq)
        db.flush()
        seen: set[str] = set()
        pos = 1
        for qid in data["question_ids"]:
            if qid in seen:
                continue
            if db.get(Question, qid) is None:
                raise AssessmentError(f"Savol topilmadi: {qid}")
            seen.add(qid)
            db.add(AssessmentQuestion(assessment_version_id=version.id, question_id=qid, position=pos))
            pos += 1
        db.flush()
        if not version.question_count:
            version.question_count = len(seen)
    db.flush()
    return version


def publish_assessment(db: Session, actor: User, assessment_id: str) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test topilmadi")
    version = _latest_version(db, assessment)
    if version is None:
        raise AssessmentError("Nashr etiladigan versiya yo'q")
    if version.question_count < 1:
        raise AssessmentError("Savollar soni belgilanmagan")
    if eligible_count(db, version) < version.question_count:
        raise AssessmentError("Yetarli mos savol yo'q — nashr etib bo'lmaydi")
    version.status = VersionStatus.PUBLISHED
    version.published_at = datetime.now(timezone.utc)
    assessment.current_version_id = version.id
    assessment.status = AssessmentStatus.PUBLISHED
    db.flush()
    return assessment


def archive_assessment(db: Session, actor: User, assessment_id: str) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test topilmadi")
    assessment.status = AssessmentStatus.ARCHIVED
    assessment.archived_at = datetime.now(timezone.utc)
    db.flush()
    return assessment


# --------------------------------------------------------------------------- #
# Attempt selection + lifecycle
# --------------------------------------------------------------------------- #
def _resolve_pinned_versions(db: Session, version: AssessmentVersion) -> list[str]:
    if version.selection_mode == AssessmentSelectionMode.MANUAL:
        pinned: list[str] = []
        for aq in version.questions:  # ordered by position
            q = db.get(Question, aq.question_id)
            if q and q.current_version_id:
                v = db.get(QuestionVersion, q.current_version_id)
                if v and v.status == VersionStatus.PUBLISHED:
                    pinned.append(v.id)
        return pinned
    # random_filter: uniformly choose unique eligible containers, pin their current versions.
    topics, diffs = _filters(version)
    container_ids = list(db.scalars(_eligible_question_query(topics, diffs)).all())
    if len(container_ids) < version.question_count:
        return []
    chosen = random.sample(container_ids, version.question_count)
    pinned = []
    for qid in chosen:
        q = db.get(Question, qid)
        if q and q.current_version_id:
            pinned.append(q.current_version_id)
    return pinned


def start_attempt(db: Session, user: User, slug: str) -> AssessmentAttempt:
    assessment = db.scalar(select(Assessment).where(Assessment.slug == slug))
    if assessment is None or assessment.status != AssessmentStatus.PUBLISHED or assessment.current_version_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test topilmadi")
    version = db.get(AssessmentVersion, assessment.current_version_id)
    pinned = _resolve_pinned_versions(db, version)
    if len(pinned) < version.question_count:
        raise AssessmentError("Yetarli mos savol yo'q")
    order = list(range(len(pinned)))
    if version.randomize_order:
        random.shuffle(order)
    attempt = AssessmentAttempt(
        user_id=user.id,
        assessment_version_id=version.id,
        status=AssessmentAttemptStatus.IN_PROGRESS,
        question_count=version.question_count,
        correct_count=0,
    )
    if version.time_limit_seconds:
        attempt.expires_at = datetime.now(timezone.utc) + timedelta(seconds=version.time_limit_seconds)
    db.add(attempt)
    db.flush()
    for position, idx in enumerate(order, start=1):
        db.add(AssessmentAttemptQuestion(
            assessment_attempt_id=attempt.id, question_version_id=pinned[idx], position=position
        ))
    db.flush()
    return attempt


def _load_attempt(db: Session, user: User, attempt_id: str) -> AssessmentAttempt:
    attempt = db.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Urinish topilmadi")
    return attempt


def submit_answer(db: Session, user: User, attempt_id: str, question_version_id: str, selected_option_id: str | None) -> AssessmentAnswer:
    attempt = _load_attempt(db, user, attempt_id)
    if attempt.status != AssessmentAttemptStatus.IN_PROGRESS:
        raise AssessmentError("Urinish yakunlangan")
    in_attempt = db.scalar(select(AssessmentAttemptQuestion.id).where(
        AssessmentAttemptQuestion.assessment_attempt_id == attempt.id,
        AssessmentAttemptQuestion.question_version_id == question_version_id,
    ))
    if in_attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol bu urinishda yo'q")
    is_correct = None
    if selected_option_id is not None:
        opt = db.get(AnswerOption, selected_option_id)
        if opt is None or opt.question_version_id != question_version_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Variant bu savolga tegishli emas")
        is_correct = bool(opt.is_correct)
    answer = db.scalar(select(AssessmentAnswer).where(
        AssessmentAnswer.assessment_attempt_id == attempt.id,
        AssessmentAnswer.question_version_id == question_version_id,
    ))
    if answer is None:
        answer = AssessmentAnswer(assessment_attempt_id=attempt.id, question_version_id=question_version_id)
        db.add(answer)
    answer.selected_option_id = selected_option_id
    answer.is_correct = is_correct
    answer.answered_at = datetime.now(timezone.utc)
    db.flush()
    return answer


def submit_attempt(db: Session, user: User, attempt_id: str) -> AssessmentAttempt:
    attempt = _load_attempt(db, user, attempt_id)
    if attempt.status == AssessmentAttemptStatus.COMPLETED:
        return attempt
    version = db.get(AssessmentVersion, attempt.assessment_version_id)
    correct = int(db.scalar(select(func.count(AssessmentAnswer.id)).where(
        AssessmentAnswer.assessment_attempt_id == attempt.id,
        AssessmentAnswer.is_correct.is_(True),
    )) or 0)
    attempt.correct_count = correct
    attempt.status = AssessmentAttemptStatus.COMPLETED
    attempt.completed_at = datetime.now(timezone.utc)
    if version and version.pass_correct is not None:
        attempt.passed = correct >= version.pass_correct
    db.flush()
    return attempt


# --------------------------------------------------------------------------- #
# Payloads (no-leak in live attempt; full reveal in review)
# --------------------------------------------------------------------------- #
def _prompt(db: Session, version_id: str) -> str:
    tr = db.scalar(select(QuestionVersionTranslation).where(
        QuestionVersionTranslation.question_version_id == version_id,
        QuestionVersionTranslation.language == _LANG,
    ))
    return tr.prompt if tr else ""


def _option_text(db: Session, option_id: str) -> str:
    tr = db.scalar(select(AnswerOptionTranslation).where(
        AnswerOptionTranslation.answer_option_id == option_id,
        AnswerOptionTranslation.language == _LANG,
    ))
    return tr.text if tr else ""


def _question_payload(db: Session, version_id: str, *, reveal: bool) -> dict:
    options = db.scalars(select(AnswerOption).where(
        AnswerOption.question_version_id == version_id
    ).order_by(AnswerOption.position)).all()
    out_options = []
    for o in options:
        item = {"id": o.id, "position": o.position, "text": _option_text(db, o.id)}
        if reveal:
            item["is_correct"] = o.is_correct
        out_options.append(item)
    return {"question_version_id": version_id, "prompt": _prompt(db, version_id), "options": out_options}


def attempt_out(db: Session, attempt: AssessmentAttempt, *, reveal: bool) -> dict:
    answers = {a.question_version_id: a for a in attempt.answers}
    questions = []
    for aq in attempt.questions:  # ordered by position
        ans = answers.get(aq.question_version_id)
        payload = _question_payload(db, aq.question_version_id, reveal=reveal)
        payload["position"] = aq.position
        payload["selected_option_id"] = ans.selected_option_id if ans else None
        if reveal:
            payload["is_correct"] = ans.is_correct if ans else None
        questions.append(payload)
    return {
        "id": attempt.id,
        "status": attempt.status.value,
        "question_count": attempt.question_count,
        "correct_count": attempt.correct_count if attempt.status == AssessmentAttemptStatus.COMPLETED else None,
        "passed": attempt.passed,
        "expires_at": attempt.expires_at.isoformat() if attempt.expires_at else None,
        "questions": questions,
    }


def assessment_admin_out(db: Session, assessment: Assessment) -> dict:
    version = _latest_version(db, assessment)
    return {
        "id": assessment.id,
        "slug": assessment.slug,
        "type": assessment.type.value,
        "status": assessment.status.value,
        "current_version_id": assessment.current_version_id,
        "latest_version": None if version is None else {
            "id": version.id,
            "version": version.version,
            "title": version.title,
            "description": version.description,
            "selection_mode": version.selection_mode.value,
            "question_count": version.question_count,
            "time_limit_seconds": version.time_limit_seconds,
            "pass_correct": version.pass_correct,
            "show_explanations_after": version.show_explanations_after.value,
            "topic_filters": (version.topic_filters_json or {}).get("topics") if version.topic_filters_json else None,
            "difficulty_filters": (version.difficulty_filters_json or {}).get("difficulties") if version.difficulty_filters_json else None,
            "randomize_order": version.randomize_order,
            "status": version.status.value,
            "question_ids": [aq.question_id for aq in version.questions],
            "eligible_count": eligible_count(db, version),
        },
    }


def assessment_public_out(assessment: Assessment, version: AssessmentVersion) -> dict:
    return {
        "slug": assessment.slug,
        "type": assessment.type.value,
        "title": version.title,
        "description": version.description,
        "question_count": version.question_count,
        "time_limit_seconds": version.time_limit_seconds,
        "pass_correct": version.pass_correct,
    }
