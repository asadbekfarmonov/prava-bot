"""Mock exam: shared-bank version-pinned selection, server-authoritative timer,
lazy finalize, no-answer-leak payloads, and server-side grading.

Integrity rules (docs/spec/09 "Exam integrity — critical"):
- While ``in_progress`` the API returns ONLY question_version_id, prompt, media ref,
  and options as {id, position, text}. Never is_correct / explanation / rule text.
- ``expires_at`` is the single deadline authority; remaining = expires_at - now
  (server clock). No pause. Any access to an in-progress attempt lazily finalizes it
  if ``now >= expires_at`` before doing anything else.
- Grading is server-side at submit/expiry; the question set is pinned at start.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import Category, Language, MockStatus, VersionStatus
from app.domain.exam_config import get_exam_config
from app.domain.models import (
    AnswerOption,
    AnswerOptionTranslation,
    MockAnswer,
    MockAttempt,
    MockQuestion,
    Question,
    QuestionVersion,
    QuestionVersionRule,
    QuestionVersionTranslation,
    Rule,
    RuleTranslation,
    User,
)

_LANG = Language.UZ


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    """SQLite may return naive datetimes; treat stored timestamps as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# --------------------------------------------------------------------------- #
# Ownership / IDOR
# --------------------------------------------------------------------------- #
def get_owned_attempt(db: Session, user: User, attempt_id: str) -> MockAttempt:
    """Return the attempt only if it belongs to ``user``; 404 otherwise (IDOR-safe)."""
    attempt = db.get(MockAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imtihon topilmadi")
    return attempt


# --------------------------------------------------------------------------- #
# Selection (shared bank, version-pinned, without replacement)
# --------------------------------------------------------------------------- #
def _eligible_version_ids(db: Session, category: Category, language: Language) -> list[str]:
    """Current published version ids for the category that have a translation in ``language``."""
    rows = db.scalars(
        select(QuestionVersion.id)
        .join(Question, Question.current_version_id == QuestionVersion.id)
        .join(
            QuestionVersionTranslation,
            QuestionVersionTranslation.question_version_id == QuestionVersion.id,
        )
        .where(
            QuestionVersion.status == VersionStatus.PUBLISHED,
            Question.category == category,
            QuestionVersionTranslation.language == language,
        )
    )
    # Distinct (a version could in theory have >1 translation row for the language guard).
    return list(dict.fromkeys(rows))


# --------------------------------------------------------------------------- #
# Lazy finalize (timer authority)
# --------------------------------------------------------------------------- #
def _finalize(db: Session, attempt: MockAttempt, *, at: datetime | None = None) -> MockAttempt:
    """Grade the attempt server-side and mark it completed. Idempotent."""
    if attempt.status != MockStatus.IN_PROGRESS:
        return attempt

    mock_questions = list(
        db.scalars(
            select(MockQuestion)
            .where(MockQuestion.mock_attempt_id == attempt.id)
            .order_by(MockQuestion.position)
        )
    )
    answers = {
        a.question_version_id: a
        for a in db.scalars(
            select(MockAnswer).where(MockAnswer.mock_attempt_id == attempt.id)
        )
    }

    correct_count = 0
    answered_count = 0
    per_topic: dict[str, dict[str, int]] = {}
    missed: list[dict] = []
    answer_times: list[float] = []
    started = _as_aware(attempt.started_at)

    for mq in mock_questions:
        version = db.get(QuestionVersion, mq.question_version_id)
        question = db.get(Question, version.question_id) if version else None
        topic = question.topic.value if question else "unknown"
        bucket = per_topic.setdefault(topic, {"total": 0, "correct": 0})
        bucket["total"] += 1

        options = list(
            db.scalars(
                select(AnswerOption).where(
                    AnswerOption.question_version_id == mq.question_version_id
                )
            )
        )
        correct_option = next((o for o in options if o.is_correct), None)
        options_by_id = {o.id: o for o in options}

        ans = answers.get(mq.question_version_id)
        selected = options_by_id.get(ans.selected_option_id) if (ans and ans.selected_option_id) else None
        is_correct = bool(selected and selected.is_correct)

        if ans is not None:
            # Persist the server-side grade onto the answer row.
            ans.is_correct = is_correct
            if ans.selected_option_id is not None:
                answered_count += 1
                if ans.answered_at is not None:
                    answer_times.append(
                        (_as_aware(ans.answered_at) - started).total_seconds()
                    )

        if is_correct:
            correct_count += 1
            bucket["correct"] += 1
        else:
            missed.append(
                {
                    "position": mq.position,
                    "question_version_id": mq.question_version_id,
                    "topic": topic,
                    "correct_option_id": correct_option.id if correct_option else None,
                }
            )

    pass_correct = attempt.pass_correct
    avg_answer_time = round(sum(answer_times) / len(answer_times), 1) if answer_times else None

    attempt.correct_count = correct_count
    attempt.answered_count = answered_count
    attempt.passed = correct_count >= pass_correct
    attempt.status = MockStatus.COMPLETED
    attempt.completed_at = at or _now()
    attempt.result_json = {
        "correct_count": correct_count,
        "answered_count": answered_count,
        "question_count": attempt.question_count,
        "pass_correct": pass_correct,
        "passed": attempt.passed,
        "per_topic": per_topic,
        "missed": missed,
        "avg_answer_time_seconds": avg_answer_time,
    }
    db.commit()
    db.refresh(attempt)

    # Slice 4 hooks (run once, on the in_progress -> completed transition above):
    # upsert/resolve mistakes from the graded answers, then credit ranking points and
    # recompute the cached readiness snapshot. Idempotent via the ledger UNIQUE.
    _post_finalize_hooks(db, attempt)
    return attempt


def _post_finalize_hooks(db: Session, attempt: MockAttempt) -> None:
    from app.services import mistakes as mistakes_service
    from app.services import ranking as ranking_service
    from app.services import readiness as readiness_service
    from app.services import stats as stats_service

    owner = db.get(User, attempt.user_id)
    if owner is None:
        return

    mock_questions = list(
        db.scalars(
            select(MockQuestion).where(MockQuestion.mock_attempt_id == attempt.id)
        )
    )
    answers = {
        a.question_version_id: a
        for a in db.scalars(select(MockAnswer).where(MockAnswer.mock_attempt_id == attempt.id))
    }
    # Count the completed mock as one active-day's activity (answered questions).
    answered = sum(
        1 for a in answers.values() if a.selected_option_id is not None
    )
    if answered:
        # Record the whole graded mock as one active-day's activity; correct_count
        # must reflect the server-graded correct answers, not a flat +1.
        stats_service.record_activity(
            db,
            owner,
            correct=False,
            answers=answered,
            correct_answers=int(attempt.correct_count or 0),
        )

    # Upsert/resolve mistakes per graded answer (only answered ones carry a grade).
    for mq in mock_questions:
        ans = answers.get(mq.question_version_id)
        if ans is None or ans.selected_option_id is None:
            continue
        version = db.get(QuestionVersion, mq.question_version_id)
        if version is None:
            continue
        res = mistakes_service.record_answer(db, owner, version.question_id, bool(ans.is_correct))
        if res.get("resolved"):
            ranking_service.credit_mistake_recovery(db, owner, version.question_id)

    ranking_service.credit_mock(db, attempt)
    readiness_service.recompute_and_cache(db, owner)
    db.commit()


def _finalize_if_expired(db: Session, attempt: MockAttempt) -> MockAttempt:
    """The lazy-finalize gate: called by EVERY endpoint touching an in-progress attempt."""
    if attempt.status == MockStatus.IN_PROGRESS and _now() >= _as_aware(attempt.expires_at):
        # Grade as of the deadline; a late client cannot extend it.
        return _finalize(db, attempt, at=_as_aware(attempt.expires_at))
    return attempt


def finalize_if_expired(db: Session, attempt: MockAttempt) -> MockAttempt:
    """Public lazy-finalize gate (thin wrapper over the internal helper)."""
    return _finalize_if_expired(db, attempt)


# --------------------------------------------------------------------------- #
# Start
# --------------------------------------------------------------------------- #
def start_attempt(
    db: Session, user: User, category: Category = Category.B, language: Language = _LANG
) -> MockAttempt:
    existing = db.scalar(
        select(MockAttempt).where(
            MockAttempt.user_id == user.id, MockAttempt.status == MockStatus.IN_PROGRESS
        )
    )
    if existing is not None:
        # Lazily finalize a silently-expired attempt, then re-check.
        existing = _finalize_if_expired(db, existing)
        if existing.status == MockStatus.IN_PROGRESS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Sizda tugallanmagan imtihon mavjud",
            )

    config = get_exam_config(category)
    eligible = _eligible_version_ids(db, category, language)
    if len(eligible) < config.questions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Imtihon uchun yetarli savol yo'q",
        )

    # 20 random, unique, WITHOUT replacement.
    chosen = random.sample(eligible, config.questions)

    started_at = _now()
    attempt = MockAttempt(
        user_id=user.id,
        category=category,
        language=language,
        status=MockStatus.IN_PROGRESS,
        started_at=started_at,
        expires_at=started_at + timedelta(seconds=config.time_limit_seconds),
        exam_config_version=config.version,
        question_count=config.questions,
        time_limit_seconds=config.time_limit_seconds,
        pass_correct=config.minimum_correct,
    )
    db.add(attempt)
    try:
        # Force the INSERT so the partial unique index is checked atomically; a
        # concurrent start that already created an in-progress attempt loses here.
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sizda tugallanmagan imtihon mavjud",
        )
    for position, version_id in enumerate(chosen, start=1):
        db.add(
            MockQuestion(
                mock_attempt_id=attempt.id,
                question_version_id=version_id,
                position=position,
            )
        )
    db.commit()
    db.refresh(attempt)
    return attempt


# --------------------------------------------------------------------------- #
# Payload builders
# --------------------------------------------------------------------------- #
def _option_text(db: Session, option_id: str) -> str:
    tr = db.scalar(
        select(AnswerOptionTranslation).where(
            AnswerOptionTranslation.answer_option_id == option_id,
            AnswerOptionTranslation.language == _LANG,
        )
    )
    return tr.text if tr else ""


def _uz_prompt(db: Session, version_id: str) -> QuestionVersionTranslation | None:
    return db.scalar(
        select(QuestionVersionTranslation).where(
            QuestionVersionTranslation.question_version_id == version_id,
            QuestionVersionTranslation.language == _LANG,
        )
    )


def _remaining_seconds(attempt: MockAttempt) -> int:
    return max(0, int((_as_aware(attempt.expires_at) - _now()).total_seconds()))


def _safe_question_payload(db: Session, mq: MockQuestion, answer: MockAnswer | None) -> dict:
    """NO-ANSWER-LEAK payload: only question_version_id, prompt, media ref, and
    options as {id, position, text}. Option order is by position (stored order is
    already random UUIDs, not correct-first)."""
    version = db.get(QuestionVersion, mq.question_version_id)
    translation = _uz_prompt(db, mq.question_version_id)
    options = list(
        db.scalars(
            select(AnswerOption)
            .where(AnswerOption.question_version_id == mq.question_version_id)
            .order_by(AnswerOption.position)
        )
    )
    return {
        "position": mq.position,
        "question_version_id": mq.question_version_id,
        "prompt": translation.prompt if translation else "",
        "media_id": version.media_id if version else None,
        "options": [
            {"id": o.id, "position": o.position, "text": _option_text(db, o.id)} for o in options
        ],
        "selected_option_id": answer.selected_option_id if answer else None,
        "marked_for_review": bool(answer.marked_for_review) if answer else False,
    }


def _attempt_meta(attempt: MockAttempt) -> dict:
    return {
        "id": attempt.id,
        "status": attempt.status.value,
        "category": attempt.category.value,
        "language": attempt.language.value,
        "started_at": _as_aware(attempt.started_at).isoformat(),
        "expires_at": _as_aware(attempt.expires_at).isoformat(),
        "completed_at": _as_aware(attempt.completed_at).isoformat()
        if attempt.completed_at
        else None,
        "question_count": attempt.question_count,
        "time_limit_seconds": attempt.time_limit_seconds,
        "pass_correct": attempt.pass_correct,
        "exam_config_version": attempt.exam_config_version,
        "remaining_seconds": _remaining_seconds(attempt)
        if attempt.status == MockStatus.IN_PROGRESS
        else 0,
        "correct_count": attempt.correct_count,
        "answered_count": attempt.answered_count,
        "passed": attempt.passed,
        "result": attempt.result_json,
    }


def attempt_state(db: Session, attempt: MockAttempt) -> dict:
    """Full state for GET current / GET {id}. In-progress -> safe questions only."""
    meta = _attempt_meta(attempt)
    mock_questions = list(
        db.scalars(
            select(MockQuestion)
            .where(MockQuestion.mock_attempt_id == attempt.id)
            .order_by(MockQuestion.position)
        )
    )
    answers = {
        a.question_version_id: a
        for a in db.scalars(
            select(MockAnswer).where(MockAnswer.mock_attempt_id == attempt.id)
        )
    }
    if attempt.status == MockStatus.IN_PROGRESS:
        meta["questions"] = [
            _safe_question_payload(db, mq, answers.get(mq.question_version_id))
            for mq in mock_questions
        ]
    else:
        # Completed/abandoned: expose the pinned set + the user's answers (no keys here;
        # answer keys live in the /review endpoint).
        meta["questions"] = [
            {
                "position": mq.position,
                "question_version_id": mq.question_version_id,
                "selected_option_id": answers[mq.question_version_id].selected_option_id
                if mq.question_version_id in answers
                else None,
                "is_correct": answers[mq.question_version_id].is_correct
                if mq.question_version_id in answers
                else None,
                "marked_for_review": bool(answers[mq.question_version_id].marked_for_review)
                if mq.question_version_id in answers
                else False,
            }
            for mq in mock_questions
        ]
    return meta


def get_current(db: Session, user: User) -> dict | None:
    """Return the in-progress attempt (lazily finalized if expired) or the most recent
    completed attempt, or None if the user has never started a mock."""
    attempt = db.scalar(
        select(MockAttempt).where(
            MockAttempt.user_id == user.id, MockAttempt.status == MockStatus.IN_PROGRESS
        )
    )
    if attempt is not None:
        attempt = _finalize_if_expired(db, attempt)
        return attempt_state(db, attempt)

    latest = db.scalar(
        select(MockAttempt)
        .where(MockAttempt.user_id == user.id)
        .order_by(MockAttempt.started_at.desc())
    )
    if latest is None:
        return None
    return attempt_state(db, latest)


# --------------------------------------------------------------------------- #
# Autosave answer
# --------------------------------------------------------------------------- #
def save_answer(
    db: Session,
    user: User,
    attempt_id: str,
    question_version_id: str,
    selected_option_id: str | None,
    marked_for_review: bool,
) -> dict:
    attempt = get_owned_attempt(db, user, attempt_id)
    attempt = _finalize_if_expired(db, attempt)
    if attempt.status != MockStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Imtihon yakunlangan"
        )

    mq = db.scalar(
        select(MockQuestion).where(
            MockQuestion.mock_attempt_id == attempt.id,
            MockQuestion.question_version_id == question_version_id,
        )
    )
    if mq is None:
        # Reject any question_version_id not pinned into this attempt.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Savol ushbu imtihonga tegishli emas"
        )

    if selected_option_id is not None:
        option = db.get(AnswerOption, selected_option_id)
        if option is None or option.question_version_id != question_version_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Javob varianti mos emas"
            )

    answer = db.scalar(
        select(MockAnswer).where(
            MockAnswer.mock_attempt_id == attempt.id,
            MockAnswer.question_version_id == question_version_id,
        )
    )
    if answer is None:
        answer = MockAnswer(
            mock_attempt_id=attempt.id,
            question_version_id=question_version_id,
        )
        db.add(answer)
    answer.selected_option_id = selected_option_id
    answer.marked_for_review = bool(marked_for_review)
    answer.answered_at = _now() if selected_option_id is not None else None
    # is_correct stays None until server-side grading at submit/expiry.
    answer.is_correct = None
    try:
        db.commit()
    except IntegrityError:
        # A concurrent save created the row first; update that row instead of failing.
        db.rollback()
        answer = db.scalar(
            select(MockAnswer).where(
                MockAnswer.mock_attempt_id == attempt.id,
                MockAnswer.question_version_id == question_version_id,
            )
        )
        if answer is not None:
            answer.selected_option_id = selected_option_id
            answer.marked_for_review = bool(marked_for_review)
            answer.answered_at = _now() if selected_option_id is not None else None
            answer.is_correct = None
            db.commit()

    return {
        "question_version_id": question_version_id,
        "selected_option_id": selected_option_id,
        "marked_for_review": bool(marked_for_review),
        "remaining_seconds": _remaining_seconds(attempt),
        "saved": True,
    }


# --------------------------------------------------------------------------- #
# Submit
# --------------------------------------------------------------------------- #
def submit_attempt(db: Session, user: User, attempt_id: str) -> dict:
    attempt = get_owned_attempt(db, user, attempt_id)
    # If already expired, finalize as of the deadline; else grade now.
    if attempt.status == MockStatus.IN_PROGRESS and _now() >= _as_aware(attempt.expires_at):
        attempt = _finalize(db, attempt, at=_as_aware(attempt.expires_at))
    elif attempt.status == MockStatus.IN_PROGRESS:
        attempt = _finalize(db, attempt)
    # Duplicate submit is idempotent: an already-completed attempt just returns its state.
    return attempt_state(db, attempt)


# --------------------------------------------------------------------------- #
# Review (post-completion only — reveals full answer keys)
# --------------------------------------------------------------------------- #
def _rule_for_version(db: Session, version_id: str) -> dict | None:
    link = db.scalar(
        select(QuestionVersionRule).where(
            QuestionVersionRule.question_version_id == version_id
        )
    )
    if link is None:
        return None
    rule = db.get(Rule, link.rule_id)
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
        "rule_version": link.rule_version,
    }


def _option_explanation(db: Session, option_id: str) -> str:
    tr = db.scalar(
        select(AnswerOptionTranslation).where(
            AnswerOptionTranslation.answer_option_id == option_id,
            AnswerOptionTranslation.language == _LANG,
        )
    )
    return tr.explanation if tr else ""


def review(db: Session, user: User, attempt_id: str) -> dict:
    attempt = get_owned_attempt(db, user, attempt_id)
    # Even if not explicitly submitted, a silently-expired attempt is finalized here.
    attempt = _finalize_if_expired(db, attempt)
    if attempt.status != MockStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ko'rib chiqish faqat imtihon yakunlangach mavjud",
        )

    mock_questions = list(
        db.scalars(
            select(MockQuestion)
            .where(MockQuestion.mock_attempt_id == attempt.id)
            .order_by(MockQuestion.position)
        )
    )
    answers = {
        a.question_version_id: a
        for a in db.scalars(
            select(MockAnswer).where(MockAnswer.mock_attempt_id == attempt.id)
        )
    }

    items = []
    for mq in mock_questions:
        version = db.get(QuestionVersion, mq.question_version_id)
        translation = _uz_prompt(db, mq.question_version_id)
        options = list(
            db.scalars(
                select(AnswerOption)
                .where(AnswerOption.question_version_id == mq.question_version_id)
                .order_by(AnswerOption.position)
            )
        )
        ans = answers.get(mq.question_version_id)
        correct_option = next((o for o in options if o.is_correct), None)
        items.append(
            {
                "position": mq.position,
                "question_version_id": mq.question_version_id,
                "prompt": translation.prompt if translation else "",
                "media_id": version.media_id if version else None,
                "short_explanation": translation.short_explanation if translation else "",
                "selected_option_id": ans.selected_option_id if ans else None,
                "is_correct": ans.is_correct if ans else False,
                "correct_option_id": correct_option.id if correct_option else None,
                "options": [
                    {
                        "id": o.id,
                        "position": o.position,
                        "text": _option_text(db, o.id),
                        "is_correct": o.is_correct,
                        "explanation": _option_explanation(db, o.id),
                    }
                    for o in options
                ],
                "rule": _rule_for_version(db, mq.question_version_id),
            }
        )

    meta = _attempt_meta(attempt)
    meta["items"] = items
    return meta
