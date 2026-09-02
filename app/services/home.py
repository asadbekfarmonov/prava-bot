"""Home hub summary (docs/spec/16 Phase 4 + 17 §O/§A).

Composes the intelligent Home dashboard from existing services (readiness, stats,
ranking, mistakes, next-action). Adds only the exam countdown and the display name;
everything else reuses already-verified logic. No answer data is ever included.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import MockStatus
from app.domain.models import MockAttempt, User
from app.services import mistakes, next_action, ranking, readiness, stats


def _exam_countdown(profile, today: date) -> dict | None:
    if profile is None or profile.target_exam_date is None:
        return None
    days = (profile.target_exam_date - today).days
    return {
        "target_exam_date": profile.target_exam_date.isoformat(),
        "days_remaining": days,
        "passed": days < 0,
    }


def _display_name(user: User) -> str:
    profile = user.profile
    if profile is not None and profile.display_name:
        return profile.display_name
    return user.first_name or "Haydovchi"


def build(db: Session, user: User) -> dict:
    readiness_payload = readiness.compute(db, user)
    today = stats.local_date_for(user)

    # Last completed mock (correct/total).
    last_mock_row = db.scalar(
        select(MockAttempt)
        .where(MockAttempt.user_id == user.id, MockAttempt.status == MockStatus.COMPLETED)
        .order_by(MockAttempt.started_at.desc())
    )
    last_mock = (
        {
            "id": last_mock_row.id,
            "correct_count": last_mock_row.correct_count,
            "question_count": last_mock_row.question_count,
            "passed": last_mock_row.passed,
            "completed_at": last_mock_row.completed_at.isoformat()
            if last_mock_row.completed_at
            else None,
        }
        if last_mock_row
        else None
    )

    daily = stats.get_daily_stat(db, user, today)
    streak = stats.get_streak(db, user)
    goal = user.profile.daily_goal if (user.profile and user.profile.daily_goal) else None
    answered_today = daily.answers_count if daily else 0

    weak_topics = readiness_payload.get("weak_topics", [])
    top_weak = None
    for wt in weak_topics:
        if wt["answered"] > 0:
            top_weak = {
                "topic": wt["topic"],
                "label": wt["label"],
                "mastery": wt["mastery"],
                "answered": wt["answered"],
            }
            break

    mistakes_open = len(mistakes.queue(db, user, limit=1000))

    week = ranking.leaderboard(db, user, "week", limit=1)["own"]
    all_time = ranking.leaderboard(db, user, "all", limit=1)["own"]

    return {
        "display_name": _display_name(user),
        "exam_countdown": _exam_countdown(user.profile, today),
        "readiness": {
            "state": readiness_payload["state"],
            "label": readiness_payload["label"],
            "score": readiness_payload["score"],
            "exam_ready": readiness_payload["exam_ready"],
            "coverage_met": readiness_payload["coverage_met"],
            "mocks_completed": readiness_payload["mocks_completed"],
            "unique_questions_attempted": readiness_payload["unique_questions_attempted"],
        },
        "last_mock": last_mock,
        "daily_goal": {
            "goal": goal,
            "answered_today": answered_today,
            "met": bool(goal and answered_today >= goal),
        },
        "streak": {
            "current": streak.current_streak if streak else 0,
            "longest": streak.longest_streak if streak else 0,
        },
        "recommendations": {
            "weak_topic": top_weak,
            "mistakes_open": mistakes_open,
        },
        "ranking": {
            "week": {"points": week["points"], "position": week["position"]},
            "all": {"points": all_time["points"], "position": all_time["position"]},
        },
        "next_action": next_action.resolve(db, user),
    }
