"""Practice loop: repeatable, version-pinned, server-authoritative grading.

The next-question payload deliberately excludes correctness/explanation/rule so a
client can never infer the answer before submitting (docs/spec/09 exam-answer
non-leak — practice reveals only *after* answering).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import Category, Language, PracticeSource, Topic, VersionStatus
from app.domain.exam_config import get_personalized_practice_config
from app.domain.models import (
    AnswerOption,
    AnswerOptionTranslation,
    PracticeAnswer,
    PracticeSession,
    Question,
    QuestionVersion,
    QuestionVersionRule,
    QuestionVersionTranslation,
    Rule,
    RuleTranslation,
    User,
)

_LANG = Language.UZ


def _media_meta(db: Session, media_id: str | None) -> dict | None:
    """No-leak media presentation metadata (delegates to the media service)."""
    from app.services.media import media_meta

    return media_meta(db, media_id)


def create_practice_session(
    db: Session,
    user: User,
    topic: Topic | None,
    category: Category = Category.B,
    source: PracticeSource | None = None,
) -> PracticeSession:
    if source is None:
        source = PracticeSource.TOPIC if topic else PracticeSource.MIXED
    session = PracticeSession(
        user_id=user.id,
        category=category,
        topic=topic,
        source=source,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_owned_session(db: Session, user: User, session_id: str) -> PracticeSession:
    """Return the session only if it belongs to ``user``; 404 otherwise (IDOR-safe)."""
    session = db.get(PracticeSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessiya topilmadi")
    return session


def _published_version_query(topic: Topic | None, category: Category):
    q = (
        select(QuestionVersion)
        .join(Question, Question.current_version_id == QuestionVersion.id)
        .where(
            QuestionVersion.status == VersionStatus.PUBLISHED,
            Question.category == category,
        )
    )
    if topic is not None:
        q = q.where(Question.topic == topic)
    return q


def pick_next_version(
    db: Session, topic: Topic | None, category: Category = Category.B
) -> QuestionVersion | None:
    version_ids = list(
        db.scalars(_published_version_query(topic, category).with_only_columns(QuestionVersion.id))
    )
    if not version_ids:
        return None
    chosen = random.choice(version_ids)
    return db.get(QuestionVersion, chosen)


def _uz_prompt(db: Session, version: QuestionVersion) -> QuestionVersionTranslation | None:
    return db.scalar(
        select(QuestionVersionTranslation).where(
            QuestionVersionTranslation.question_version_id == version.id,
            QuestionVersionTranslation.language == _LANG,
        )
    )


def _option_text(db: Session, option_id: str) -> str:
    tr = db.scalar(
        select(AnswerOptionTranslation).where(
            AnswerOptionTranslation.answer_option_id == option_id,
            AnswerOptionTranslation.language == _LANG,
        )
    )
    return tr.text if tr else ""


def _option_explanation(db: Session, option_id: str) -> str:
    tr = db.scalar(
        select(AnswerOptionTranslation).where(
            AnswerOptionTranslation.answer_option_id == option_id,
            AnswerOptionTranslation.language == _LANG,
        )
    )
    return tr.explanation if tr else ""


def _sign_version_query(category: Category):
    return (
        select(QuestionVersion)
        .join(Question, Question.current_version_id == QuestionVersion.id)
        .where(
            QuestionVersion.status == VersionStatus.PUBLISHED,
            Question.category == category,
            Question.is_sign_question.is_(True),
        )
    )


def pick_next_sign_version(db: Session, category: Category = Category.B) -> QuestionVersion | None:
    version_ids = list(db.scalars(_sign_version_query(category).with_only_columns(QuestionVersion.id)))
    if not version_ids:
        return None
    return db.get(QuestionVersion, random.choice(version_ids))


def _payload_for_version(db: Session, version: QuestionVersion) -> dict:
    """Safe no-leak payload for a specific version: prompt + option ids/text/position."""
    translation = _uz_prompt(db, version)
    options = list(
        db.scalars(
            select(AnswerOption)
            .where(AnswerOption.question_version_id == version.id)
            .order_by(AnswerOption.position)
        )
    )
    question = db.get(Question, version.question_id)
    return {
        "question_id": version.question_id,
        "question_version_id": version.id,
        "topic": question.topic.value if question else None,
        "is_sign_question": bool(question and question.is_sign_question),
        "prompt": translation.prompt if translation else "",
        "media_id": version.media_id,
        # No-leak media metadata for QuestionMedia (never answer/explanation/rule).
        "media": _media_meta(db, version.media_id),
        "options": [
            {"id": o.id, "position": o.position, "text": _option_text(db, o.id)} for o in options
        ],
    }


def next_question_payload(
    db: Session, topic: Topic | None, category: Category = Category.B
) -> dict | None:
    """Safe payload: prompt + option ids/text/position ONLY. No correctness/explanation/rule."""
    version = pick_next_version(db, topic, category)
    if version is None:
        return None
    return _payload_for_version(db, version)


def next_mistake_payload(db: Session, user: User) -> dict | None:
    """No-leak payload for the top of the user's (unresolved) mistakes queue."""
    from app.services import mistakes as mistakes_service

    version = mistakes_service.pick_next_mistake_version(db, user)
    if version is None:
        return None
    return _payload_for_version(db, version)


def next_sign_payload(db: Session, category: Category = Category.B) -> dict | None:
    """No-leak payload for a random published sign question (road-sign trainer)."""
    version = pick_next_sign_version(db, category)
    if version is None:
        return None
    return _payload_for_version(db, version)


def _rule_for_version(db: Session, version: QuestionVersion) -> dict | None:
    link = db.scalar(
        select(QuestionVersionRule).where(QuestionVersionRule.question_version_id == version.id)
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


def submit_answer(
    db: Session,
    user: User,
    practice_session_id: str,
    question_id: str,
    selected_option_id: str | None,
    time_spent_seconds: int | None,
) -> dict:
    """Grade an answer server-side, persist a PracticeAnswer, and return the
    post-answer explanation payload (correct option + per-option explanations + rule)."""
    session = get_owned_session(db, user, practice_session_id)

    question = db.get(Question, question_id)
    if question is None or question.current_version_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    version = db.get(QuestionVersion, question.current_version_id)
    if version is None or version.status != VersionStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")

    options = list(
        db.scalars(
            select(AnswerOption)
            .where(AnswerOption.question_version_id == version.id)
            .order_by(AnswerOption.position)
        )
    )
    options_by_id = {o.id: o for o in options}

    selected = None
    if selected_option_id is not None:
        selected = options_by_id.get(selected_option_id)
        if selected is None:
            # Option must belong to the resolved version — reject injected ids.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Javob varianti mos emas"
            )

    is_correct = bool(selected and selected.is_correct)
    correct_option = next((o for o in options if o.is_correct), None)

    answer = PracticeAnswer(
        practice_session_id=session.id,
        question_version_id=version.id,
        selected_option_id=selected.id if selected else None,
        is_correct=is_correct,
        time_spent_seconds=time_spent_seconds,
        attempted_at=datetime.now(timezone.utc),
    )
    db.add(answer)
    db.flush()

    # Slice 4 hooks: mistakes upsert/resolve, daily activity, learning-weighted points.
    # (Order matters: record activity before crediting so the daily-consistency check
    # sees today's answer count.)
    from app.services import mistakes as mistakes_service
    from app.services import ranking as ranking_service
    from app.services import stats as stats_service

    mistake_result = mistakes_service.record_answer(db, user, question.id, is_correct)
    stats_service.record_activity(db, user, correct=is_correct)
    ranking_service.credit_practice_answer(
        db,
        user,
        question.id,
        is_correct,
        time_spent_seconds,
        resolved_mistake=bool(mistake_result.get("resolved")),
    )
    db.commit()

    translation = _uz_prompt(db, version)
    return {
        "is_correct": is_correct,
        "selected_option_id": selected.id if selected else None,
        "correct_option_id": correct_option.id if correct_option else None,
        "short_explanation": translation.short_explanation if translation else "",
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
        "rule": _rule_for_version(db, version),
    }


# --------------------------------------------------------------------------- #
# Personalized practice ("Siz uchun") — docs/spec/17 §A.
# Server-side selector over stored facts. Reuses the SAME no-leak payload and the
# SAME server-side grading; a client can never request an answer key or bias the
# selection toward a known answer.
# --------------------------------------------------------------------------- #
def _answered_question_ids_with_recency(
    db: Session, user: User
) -> dict[str, datetime]:
    """Map question_id -> most-recent attempt time across practice + mock answers."""
    seen: dict[str, datetime] = {}

    rows = db.execute(
        select(Question.id, PracticeAnswer.attempted_at)
        .join(QuestionVersion, QuestionVersion.id == PracticeAnswer.question_version_id)
        .join(Question, Question.id == QuestionVersion.question_id)
        .join(PracticeSession, PracticeSession.id == PracticeAnswer.practice_session_id)
        .where(PracticeSession.user_id == user.id)
    ).all()
    for qid, when in rows:
        w = when.replace(tzinfo=timezone.utc) if (when and when.tzinfo is None) else when
        if w is not None and (qid not in seen or w > seen[qid]):
            seen[qid] = w
    return seen


def _random_published_version_in_ids(
    db: Session, question_ids: list[str], category: Category
) -> QuestionVersion | None:
    if not question_ids:
        return None
    version_ids = list(
        db.scalars(
            _published_version_query(None, category)
            .with_only_columns(QuestionVersion.id)
            .where(Question.id.in_(question_ids))
        )
    )
    if not version_ids:
        return None
    return db.get(QuestionVersion, random.choice(version_ids))


def pick_next_personalized_version(
    db: Session, user: User, category: Category = Category.B
) -> QuestionVersion | None:
    """Choose a next question from weighted buckets:
    unresolved mistakes -> weak topics -> unseen -> stale (weights in domain config).
    Only non-empty buckets are considered; falls back to a random published question.
    """
    from app.services import mistakes as mistakes_service
    from app.services import readiness as readiness_service

    cfg = get_personalized_practice_config()
    now = datetime.now(timezone.utc)

    # Bucket 1: unresolved mistakes (hardest first).
    mistake_version = mistakes_service.pick_next_mistake_version(db, user)

    seen = _answered_question_ids_with_recency(db, user)
    seen_ids = set(seen.keys())

    # Bucket 2: weak topics (enough sample, low mastery) -> a question in that topic.
    weak_topic_value: str | None = None
    for row in readiness_service.topic_progress(db, user):
        if (
            row["answered"] >= cfg.weak_topic_min_answers
            and row["mastery"] < cfg.weak_topic_max_mastery
        ):
            weak_topic_value = row["topic"]
            break
    weak_version = None
    if weak_topic_value is not None:
        try:
            weak_version = pick_next_version(db, Topic(weak_topic_value), category)
        except ValueError:
            weak_version = None

    # Bucket 3: unseen published questions.
    all_ids = list(
        db.scalars(
            _published_version_query(None, category).with_only_columns(Question.id)
        )
    )
    unseen_ids = [qid for qid in all_ids if qid not in seen_ids]
    unseen_version = _random_published_version_in_ids(db, unseen_ids, category)

    # Bucket 4: stale (seen but not in the recent window).
    stale_cutoff = now - timedelta(days=cfg.stale_days)
    stale_ids = [qid for qid, when in seen.items() if when < stale_cutoff]
    stale_version = _random_published_version_in_ids(db, stale_ids, category)

    buckets: list[tuple[int, QuestionVersion]] = []
    if mistake_version is not None:
        buckets.append((cfg.weight_mistakes, mistake_version))
    if weak_version is not None:
        buckets.append((cfg.weight_weak_topic, weak_version))
    if unseen_version is not None and len(unseen_ids) >= cfg.unseen_min_pool:
        buckets.append((cfg.weight_unseen, unseen_version))
    if stale_version is not None:
        buckets.append((cfg.weight_stale, stale_version))

    if buckets:
        weights = [w for w, _ in buckets]
        chosen = random.choices([v for _, v in buckets], weights=weights, k=1)[0]
        return chosen

    # Fallback: any published question (keeps the flow alive for a fresh user).
    return pick_next_version(db, None, category)


def next_personalized_payload(
    db: Session, user: User, category: Category = Category.B
) -> dict | None:
    """No-leak payload for the personalized selector."""
    version = pick_next_personalized_version(db, user, category)
    if version is None:
        return None
    return _payload_for_version(db, version)
