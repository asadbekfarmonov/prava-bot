"""Learning-weighted ranking (docs/spec/10-ranking.md).

All points are computed SERVER-SIDE from stored facts (PracticeAnswer / MockAnswer /
MistakeEntry) and written to an idempotent ledger; the client never submits points.
Crediting is idempotent under retries/concurrency via
``UNIQUE(user_id, source, ref_type, ref_id)``.

Points model:
  +1  first correct answer of a UNIQUE question (once per question, ever)
  +2  a mistake-queue question resolved (once per question, ever)
  mock: +1 per server-graded correct answer (once per mock) + one highest pass bonus
        (18->+10, 19->+20, 20->+35), capped by ``max_mock_bonus_per_day``
  +5  daily consistency (once per active day)

Anti-cheat: unique-only practice credit; sub-``min_answer_seconds`` answers earn 0 and
are flagged; daily practice cap; only completed non-abandoned mocks award; bonus uses the
server ``correct_count``.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import MockStatus, PointsSource
from app.domain.exam_config import get_ranking_config
from app.domain.models import (
    MockAttempt,
    StudentProfile,
    User,
    UserPointsLedger,
)
from app.services import stats


# --------------------------------------------------------------------------- #
# Idempotent credit primitive
# --------------------------------------------------------------------------- #
def _credit(
    db: Session,
    user_id: str,
    source: PointsSource,
    points: int,
    ref_type: str,
    ref_id: str,
    local_date: date,
) -> bool:
    """Insert one ledger row inside a SAVEPOINT. Returns True if newly credited,
    False if the row already existed (idempotent) or points <= 0."""
    if points <= 0:
        return False
    try:
        with db.begin_nested():
            db.add(
                UserPointsLedger(
                    user_id=user_id,
                    source=source,
                    points=points,
                    ref_type=ref_type,
                    ref_id=str(ref_id),
                    local_date=local_date,
                )
            )
        return True
    except IntegrityError:
        return False


def _practice_points_today(db: Session, user_id: str, local_date: date) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(UserPointsLedger.points), 0)).where(
            UserPointsLedger.user_id == user_id,
            UserPointsLedger.source == PointsSource.PRACTICE_UNIQUE,
            UserPointsLedger.local_date == local_date,
        )
    )
    return int(total or 0)


def _mock_bonuses_today(db: Session, user_id: str, local_date: date) -> int:
    count = db.scalar(
        select(func.count(UserPointsLedger.id)).where(
            UserPointsLedger.user_id == user_id,
            UserPointsLedger.source == PointsSource.MOCK_BONUS,
            UserPointsLedger.local_date == local_date,
        )
    )
    return int(count or 0)


# --------------------------------------------------------------------------- #
# Practice crediting (called after a graded practice answer)
# --------------------------------------------------------------------------- #
def credit_practice_answer(
    db: Session,
    user: User,
    question_id: str,
    is_correct: bool,
    time_spent_seconds: int | None,
    *,
    resolved_mistake: bool = False,
) -> dict:
    """Credit unique-correct (+1) and mistake-recovery (+2) points for one answer.

    Enforces min_answer_seconds (too-fast -> 0 + flagged), the daily practice cap,
    and unique-only crediting (ledger uniqueness)."""
    cfg = get_ranking_config()
    result = {"unique_correct_credited": False, "mistake_recovery_credited": False,
              "flagged_too_fast": False}
    local_date = stats.local_date_for(user)

    too_fast = time_spent_seconds is not None and time_spent_seconds < cfg.min_answer_seconds
    if too_fast:
        result["flagged_too_fast"] = True

    if is_correct and not too_fast:
        # +1 first correct of a UNIQUE question (daily cap on practice points).
        if _practice_points_today(db, user.id, local_date) < cfg.daily_practice_cap:
            if _credit(
                db, user.id, PointsSource.PRACTICE_UNIQUE, cfg.practice_unique_correct,
                "question", question_id, local_date,
            ):
                result["unique_correct_credited"] = True

        # +2 mistake resolved (once per question, ever) — not subject to practice cap.
        if resolved_mistake:
            if _credit(
                db, user.id, PointsSource.MISTAKE_RECOVERY, cfg.mistake_recovery,
                "question", question_id, local_date,
            ):
                result["mistake_recovery_credited"] = True

    credit_daily_consistency(db, user, local_date=local_date)
    return result


def credit_mistake_recovery(db: Session, user: User, question_id: str) -> bool:
    """+2 once per question, ever (used when a mock/practice answer resolves a mistake)."""
    cfg = get_ranking_config()
    local_date = stats.local_date_for(user)
    return _credit(
        db, user.id, PointsSource.MISTAKE_RECOVERY, cfg.mistake_recovery,
        "question", question_id, local_date,
    )


# --------------------------------------------------------------------------- #
# Mock crediting (called once when an attempt is finalized -> COMPLETED)
# --------------------------------------------------------------------------- #
def credit_mock(db: Session, attempt: MockAttempt) -> dict:
    """Credit mock base (+1/correct, once per mock) and one highest pass bonus.
    Abandoned/in-progress attempts award nothing; the bonus uses the server-graded
    ``correct_count`` and is capped by ``max_mock_bonus_per_day``."""
    result = {"base_credited": False, "bonus_credited": False, "bonus_points": 0}
    if attempt.status != MockStatus.COMPLETED:
        return result

    cfg = get_ranking_config()
    user = db.get(User, attempt.user_id)
    if user is None:
        return result
    local_date = stats.local_date_for(user)
    correct = int(attempt.correct_count or 0)

    if correct > 0:
        if _credit(
            db, user.id, PointsSource.MOCK_CORRECT, correct * cfg.mock_correct,
            "mock_attempt", attempt.id, local_date,
        ):
            result["base_credited"] = True

    bonus = cfg.mock_bonus.get(correct)
    if bonus and attempt.passed and _mock_bonuses_today(db, user.id, local_date) < cfg.max_mock_bonus_per_day:
        if _credit(
            db, user.id, PointsSource.MOCK_BONUS, bonus,
            "mock_attempt", attempt.id, local_date,
        ):
            result["bonus_credited"] = True
            result["bonus_points"] = bonus

    credit_daily_consistency(db, user, local_date=local_date)
    return result


def credit_daily_consistency(db: Session, user: User, *, local_date: date | None = None) -> bool:
    """+5 once per active day (met daily goal or >= active_day_min_answers)."""
    cfg = get_ranking_config()
    day = local_date or stats.local_date_for(user)
    if not stats.is_active_day(db, user, day):
        return False
    return _credit(
        db, user.id, PointsSource.DAILY_CONSISTENCY, cfg.daily_consistency,
        "day", day.isoformat(), day,
    )


# --------------------------------------------------------------------------- #
# Aggregation / leaderboard
# --------------------------------------------------------------------------- #
def _range_start(range_key: str, today: date) -> date | None:
    if range_key == "week":
        return today - timedelta(days=today.weekday())  # Monday of this week
    if range_key == "month":
        return today.replace(day=1)
    return None  # all-time


def _totals_by_user(db: Session, since: date | None) -> dict[str, int]:
    q = select(UserPointsLedger.user_id, func.sum(UserPointsLedger.points))
    if since is not None:
        q = q.where(UserPointsLedger.local_date >= since)
    q = q.group_by(UserPointsLedger.user_id)
    return {row[0]: int(row[1] or 0) for row in db.execute(q).all()}


def user_total(db: Session, user: User, range_key: str) -> int:
    since = _range_start(range_key, stats.local_date_for(user))
    q = select(func.coalesce(func.sum(UserPointsLedger.points), 0)).where(
        UserPointsLedger.user_id == user.id
    )
    if since is not None:
        q = q.where(UserPointsLedger.local_date >= since)
    return int(db.scalar(q) or 0)


def _display_name(profile: StudentProfile | None, fallback: str) -> str:
    if profile is not None:
        if profile.ranking_name:
            return profile.ranking_name
        if profile.display_name:
            return profile.display_name
    return fallback


def leaderboard(db: Session, user: User, range_key: str = "all", limit: int = 50) -> dict:
    """Public board (opted-in users only) + the requesting user's own position
    (always shown, even outside the visible top list, even if opted out)."""
    cfg = get_ranking_config()
    limit = max(1, min(limit, cfg.leaderboard_max_limit))
    today = stats.local_date_for(user)
    since = _range_start(range_key, today)

    totals = _totals_by_user(db, since)

    # Resolve profiles for everyone with points (opt-out filtering + names).
    profiles = {
        p.user_id: p
        for p in db.scalars(
            select(StudentProfile).where(StudentProfile.user_id.in_(list(totals.keys())))
        )
    } if totals else {}

    ranked_public: list[tuple[str, int]] = []
    for uid, pts in totals.items():
        prof = profiles.get(uid)
        if prof is not None and prof.show_on_ranking is False:
            continue  # opted out -> absent from the public board
        ranked_public.append((uid, pts))
    # Stable ordering: points desc, then user_id for determinism.
    ranked_public.sort(key=lambda t: (-t[1], t[0]))

    entries: list[dict] = []
    own_uid = user.id
    own_position: int | None = None
    # Only hydrate the User row for the visible top-`limit` entries (avoid an N+1
    # over the whole board); the internal user_id UUID is never exposed publicly.
    for idx, (uid, pts) in enumerate(ranked_public, start=1):
        if uid == own_uid:
            own_position = idx
        if idx <= limit:
            u = db.get(User, uid)
            entries.append(
                {
                    "position": idx,
                    "name": _display_name(
                        profiles.get(uid), (u.first_name if u else None) or "—"
                    ),
                    "points": pts,
                    "is_self": uid == own_uid,
                }
            )
        elif own_position is not None:
            # Past the visible list and own position already resolved -> stop scanning.
            break

    # The requesting user always sees their own row/position, even if outside the
    # top list or opted out of the public board.
    own_points = user_total(db, user, range_key)
    own_prof = user.profile
    if own_position is None:
        # Not on the public board (opted out or below cutoff): compute their rank
        # among opted-in users, then present a self-only row.
        higher = sum(1 for _, pts in ranked_public if pts > own_points)
        own_position = higher + 1 if own_points > 0 else higher + 1
    own_row = {
        "position": own_position,
        "user_id": own_uid,
        "name": _display_name(own_prof, (user.first_name or "Siz")),
        "points": own_points,
        "is_self": True,
        "show_on_ranking": bool(own_prof.show_on_ranking) if own_prof else True,
    }

    return {
        "range": range_key if range_key in {"week", "month", "all"} else "all",
        "entries": entries,
        "own": own_row,
    }
