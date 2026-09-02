"""Personalized "Davom etish" resolver (docs/spec/16 Phase 4 + 17 §A).

Returns a small server-side directive telling the client what the single primary
Home CTA should do. Selection is server-authoritative and reuses existing services;
the client never chooses among answer-bearing options here.

Priority (first match wins):
  1. resume an in-progress, non-expired mock attempt
  2. unresolved mistakes waiting in the queue
  3. a weak topic (enough sample, low mastery)
  4. curriculum coverage gap (a topic still below the coverage floor)
  5. personalized practice (unseen / stale / mixed) — the default
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import Category, MockStatus, Topic
from app.domain.exam_config import (
    get_personalized_practice_config,
    get_readiness_config,
)
from app.domain.models import MockAttempt, User
from app.services import mistakes as mistakes_service
from app.services import readiness as readiness_service
from app.services.mock import finalize_if_expired


def resolve(db: Session, user: User) -> dict:
    category = user.profile.category if user.profile else Category.B
    p_cfg = get_personalized_practice_config()
    r_cfg = get_readiness_config()

    # 1. Resume an active mock (server-authoritative; finalize if the timer expired).
    active = db.scalar(
        select(MockAttempt)
        .where(MockAttempt.user_id == user.id, MockAttempt.status == MockStatus.IN_PROGRESS)
        .order_by(MockAttempt.started_at.desc())
    )
    if active is not None:
        active = finalize_if_expired(db, active)
        if active.status == MockStatus.IN_PROGRESS:
            return {
                "action": "resume_mock",
                "source": None,
                "topic": None,
                "topic_label": None,
                "attempt_id": active.id,
                "label": "Imtihonni davom ettirish",
                "reason": "active_mock",
            }

    # 2. Unresolved mistakes.
    queue = mistakes_service.queue(db, user, limit=1)
    if queue:
        return {
            "action": "mistakes",
            "source": "mistakes",
            "topic": None,
            "topic_label": None,
            "attempt_id": None,
            "label": "Xatolarni takrorlash",
            "reason": "open_mistakes",
        }

    topics = readiness_service.topic_progress(db, user)

    # 3. Weak topic (enough sample, low mastery).
    for row in topics:
        if (
            row["answered"] >= p_cfg.weak_topic_min_answers
            and row["mastery"] < p_cfg.weak_topic_max_mastery
        ):
            return {
                "action": "weak_topic",
                "source": "topic",
                "topic": row["topic"],
                "topic_label": row["label"],
                "attempt_id": None,
                "label": "Zaif mavzuni mashq qilish",
                "reason": "weak_topic",
            }

    # 4. Curriculum coverage gap (a topic still under the coverage floor).
    for row in topics:
        if row["answered"] < r_cfg.gate_min_answers_per_topic:
            # Only surface topics that actually have questions to serve is left to the
            # practice selector; the directive still points the user at the topic.
            try:
                Topic(row["topic"])
            except ValueError:
                continue
            return {
                "action": "coverage",
                "source": "topic",
                "topic": row["topic"],
                "topic_label": row["label"],
                "attempt_id": None,
                "label": "Yangi mavzuni boshlash",
                "reason": "coverage_gap",
            }

    # 5. Default: personalized practice.
    return {
        "action": "personalized",
        "source": "personalized",
        "topic": None,
        "topic_label": None,
        "attempt_id": None,
        "label": "Siz uchun mashq",
        "reason": "personalized",
    }
