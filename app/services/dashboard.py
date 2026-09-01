"""Progress / readiness dashboard aggregation (docs/spec/03 + 07).

Returns the readiness snapshot + recent mock result(s) + weak topics + daily-goal +
streak + ranking snapshot for the home screen.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import MockStatus
from app.domain.models import MockAttempt, User
from app.services import mistakes, ranking, readiness, stats


def build(db: Session, user: User) -> dict:
    readiness_payload = readiness.compute(db, user)

    recent_mocks = list(
        db.scalars(
            select(MockAttempt)
            .where(MockAttempt.user_id == user.id, MockAttempt.status == MockStatus.COMPLETED)
            .order_by(MockAttempt.started_at.desc())
            .limit(3)
        )
    )
    recent = [
        {
            "id": m.id,
            "correct_count": m.correct_count,
            "question_count": m.question_count,
            "passed": m.passed,
            "completed_at": m.completed_at.isoformat() if m.completed_at else None,
        }
        for m in recent_mocks
    ]

    today = stats.local_date_for(user)
    daily = stats.get_daily_stat(db, user, today)
    streak = stats.get_streak(db, user)
    goal = user.profile.daily_goal if (user.profile and user.profile.daily_goal) else None
    answered_today = daily.answers_count if daily else 0

    mistakes_open = len([m for m in mistakes.queue(db, user, limit=1000)])

    return {
        "readiness": {
            "state": readiness_payload["state"],
            "label": readiness_payload["label"],
            "score": readiness_payload["score"],
            "exam_ready": readiness_payload["exam_ready"],
            "coverage_met": readiness_payload["coverage_met"],
            "remaining_coverage": readiness_payload["remaining_coverage"],
        },
        "weak_topics": readiness_payload["weak_topics"][:5],
        "recent_mocks": recent,
        "daily_goal": {
            "goal": goal,
            "answered_today": answered_today,
            "met": bool(goal and answered_today >= goal),
        },
        "streak": {
            "current": streak.current_streak if streak else 0,
            "longest": streak.longest_streak if streak else 0,
        },
        "mistakes_open": mistakes_open,
        "ranking": {
            "week": ranking.user_total(db, user, "week"),
            "month": ranking.user_total(db, user, "month"),
            "all": ranking.user_total(db, user, "all"),
        },
    }
