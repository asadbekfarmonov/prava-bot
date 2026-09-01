"""Mistakes review (docs/spec/03 + 02).

A wrong answer in practice OR mock upserts a ``MistakeEntry`` for (user, question).
v1 resolves an entry on the first correct re-answer. Re-missing an already-resolved
question re-opens it, but re-resolving never re-awards points (the ranking ledger's
UNIQUE(user, source, ref_type, ref_id) guarantees mistake-recovery is credited once
per question, ever).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import Language, VersionStatus
from app.domain.models import (
    MistakeEntry,
    Question,
    QuestionVersion,
    QuestionVersionTranslation,
    User,
)

_LANG = Language.UZ


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_answer(db: Session, user: User, question_id: str, is_correct: bool) -> dict:
    """Upsert the mistake entry for a single graded answer.

    Returns ``{"resolved": bool}`` where ``resolved`` is True only when an entry
    that was previously unresolved transitions to resolved on this correct answer
    (the single moment mistake-recovery points may be awarded)."""
    entry = db.scalar(
        select(MistakeEntry).where(
            MistakeEntry.user_id == user.id, MistakeEntry.question_id == question_id
        )
    )
    resolved_now = False

    if is_correct:
        if entry is not None:
            if not entry.resolved:
                entry.resolved = True
                resolved_now = True
            entry.last_result = True
        # correct answer with no prior mistake: nothing to track
    else:
        if entry is None:
            entry = MistakeEntry(
                user_id=user.id,
                question_id=question_id,
                first_missed_at=_now(),
                last_missed_at=_now(),
                miss_count=1,
                resolved=False,
                last_result=False,
            )
            db.add(entry)
        else:
            entry.miss_count += 1
            entry.last_missed_at = _now()
            entry.last_result = False
            entry.resolved = False  # re-missing re-opens the entry
    db.flush()
    return {"resolved": resolved_now, "entry_id": entry.id if entry else None}


def queue(db: Session, user: User, limit: int = 50) -> list[dict]:
    """Unresolved mistakes, hardest first (miss_count desc) then most-recent."""
    entries = list(
        db.scalars(
            select(MistakeEntry)
            .where(MistakeEntry.user_id == user.id, MistakeEntry.resolved.is_(False))
            .order_by(MistakeEntry.miss_count.desc(), MistakeEntry.last_missed_at.desc())
            .limit(limit)
        )
    )
    out: list[dict] = []
    for e in entries:
        question = db.get(Question, e.question_id)
        prompt = ""
        topic = None
        if question is not None:
            topic = question.topic.value
            if question.current_version_id is not None:
                tr = db.scalar(
                    select(QuestionVersionTranslation).where(
                        QuestionVersionTranslation.question_version_id
                        == question.current_version_id,
                        QuestionVersionTranslation.language == _LANG,
                    )
                )
                prompt = tr.prompt if tr else ""
        out.append(
            {
                "question_id": e.question_id,
                "topic": topic,
                "prompt": prompt,
                "miss_count": e.miss_count,
                "last_missed_at": e.last_missed_at.isoformat() if e.last_missed_at else None,
                "resolved": e.resolved,
            }
        )
    return out


def _current_published_version(db: Session, question_id: str) -> QuestionVersion | None:
    question = db.get(Question, question_id)
    if question is None or question.current_version_id is None:
        return None
    version = db.get(QuestionVersion, question.current_version_id)
    if version is None or version.status != VersionStatus.PUBLISHED:
        return None
    return version


def pick_next_mistake_version(db: Session, user: User) -> QuestionVersion | None:
    """Serve the top of the (unresolved, hardest-first) queue as the next question."""
    entries = db.scalars(
        select(MistakeEntry)
        .where(MistakeEntry.user_id == user.id, MistakeEntry.resolved.is_(False))
        .order_by(MistakeEntry.miss_count.desc(), MistakeEntry.last_missed_at.desc())
    )
    for e in entries:
        version = _current_published_version(db, e.question_id)
        if version is not None:
            return version
    return None
