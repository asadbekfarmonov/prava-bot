"""Daily activity stats + streaks (kept from SATStudy; cheap).

These feed the dashboard's daily-goal/streak surfaces and the ranking
consistency component. All dates are the user's *local* date (profile timezone,
default Asia/Tashkent) so daily caps and "active day" logic match what the user
experiences.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.exam_config import get_ranking_config
from app.domain.models import StudentDailyStat, Streak, User

_DEFAULT_TZ = "Asia/Tashkent"


def _zone(user: User) -> ZoneInfo:
    tz = _DEFAULT_TZ
    if user.profile is not None and user.profile.timezone:
        tz = user.profile.timezone
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ZoneInfo("UTC")


def local_date_for(user: User, *, at: datetime | None = None) -> date:
    """The user's local calendar date (profile timezone)."""
    moment = at or datetime.now(tz=_zone(user))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo("UTC"))
    return moment.astimezone(_zone(user)).date()


def get_daily_stat(db: Session, user: User, on: date) -> StudentDailyStat | None:
    return db.scalar(
        select(StudentDailyStat).where(
            StudentDailyStat.user_id == user.id, StudentDailyStat.stat_date == on
        )
    )


def is_active_day(db: Session, user: User, on: date) -> bool:
    """An "active day" = met the daily goal OR answered >= active_day_min_answers."""
    stat = get_daily_stat(db, user, on)
    if stat is None:
        return False
    cfg = get_ranking_config()
    goal = user.profile.daily_goal if (user.profile and user.profile.daily_goal) else None
    if goal is not None and stat.answers_count >= goal:
        return True
    return stat.answers_count >= cfg.active_day_min_answers


def record_activity(
    db: Session,
    user: User,
    *,
    correct: bool,
    answers: int = 1,
    correct_answers: int | None = None,
    on: date | None = None,
) -> StudentDailyStat:
    """Increment the day's answer/correct counters and roll the streak forward.
    Idempotency is not required here (it is additive activity, not points).

    For a single practice answer pass ``correct`` (bool). For a batch (e.g. a
    graded mock) pass ``answers`` and ``correct_answers`` so ``correct_count``
    reflects the true number of correct answers, not just +1."""
    day = on or local_date_for(user)
    stat = get_daily_stat(db, user, day)
    if stat is None:
        stat = StudentDailyStat(user_id=user.id, stat_date=day, answers_count=0, correct_count=0)
        db.add(stat)
    stat.answers_count += answers
    if correct_answers is not None:
        stat.correct_count += max(0, correct_answers)
    elif correct:
        stat.correct_count += 1

    _roll_streak(db, user, day)
    db.flush()
    return stat


def _roll_streak(db: Session, user: User, day: date) -> Streak:
    streak = db.scalar(select(Streak).where(Streak.user_id == user.id))
    if streak is None:
        streak = Streak(user_id=user.id, current_streak=0, longest_streak=0)
        db.add(streak)
    last = streak.last_active_date
    if last == day:
        return streak  # already counted today
    if last == day - timedelta(days=1):
        streak.current_streak += 1
    else:
        streak.current_streak = 1
    streak.last_active_date = day
    streak.longest_streak = max(streak.longest_streak, streak.current_streak)
    return streak


def get_streak(db: Session, user: User) -> Streak | None:
    return db.scalar(select(Streak).where(Streak.user_id == user.id))
