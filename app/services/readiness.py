"""Readiness scoring (docs/spec/07-readiness.md — implemented EXACTLY).

Three display states (insufficient_data / initial / ready_estimate), four weighted
components (mock .40, topic mastery .30, mistake recovery .20, consistency .10), a
mandatory curriculum-coverage gate (every v1 Topic must reach
``gate_min_answers_per_topic`` before ready/badge), and an advisory "exam ready" gate.

All thresholds/weights come from ``app/domain/exam_config`` (domain config, never env).
Diagnostic output is NOT readiness and must never be labelled ``Imtihonga tayyorlik``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import MockStatus, ReadinessState, Topic
from app.domain.exam_config import get_exam_config, get_readiness_config
from app.domain.models import (
    MistakeEntry,
    MockAnswer,
    MockAttempt,
    PracticeAnswer,
    PracticeSession,
    Question,
    QuestionVersion,
    ReadinessSnapshot,
    StudentDailyStat,
    User,
)
from app.services import stats

_TOPIC_LABELS_UZ: dict[str, str] = {
    Topic.GENERAL_RULES.value: "Umumiy qoidalar",
    Topic.ROAD_SIGNS.value: "Yo'l belgilari",
    Topic.ROAD_MARKINGS.value: "Yo'l belgilanishlari",
    Topic.SIGNALS.value: "Svetofor va signallar",
    Topic.INTERSECTIONS.value: "Chorrahalar",
    Topic.MANOEUVRING.value: "Manevr qilish",
    Topic.SPEED_DISTANCE.value: "Tezlik va masofa",
    Topic.OVERTAKING.value: "Quvib o'tish",
    Topic.STOPPING_PARKING.value: "To'xtash va to'xtab turish",
    Topic.VULNERABLE_USERS.value: "Piyodalar va zaif ishtirokchilar",
    Topic.RAILWAY_CROSSINGS.value: "Temir yo'l kesishmalari",
    Topic.MOTORWAYS_SPECIAL.value: "Avtomagistrallar",
    Topic.VEHICLE_CONDITION.value: "Transport holati",
    Topic.TRANSPORT_OF_PEOPLE_CARGO.value: "Yo'lovchi va yuk tashish",
    Topic.EMERGENCIES_FIRST_AID.value: "Favqulodda holat va birinchi yordam",
}


def topic_label(topic_value: str) -> str:
    return _TOPIC_LABELS_UZ.get(topic_value, topic_value)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


@dataclass
class _AnswerRec:
    question_id: str
    topic: str
    is_correct: bool
    when: datetime | None


def _gather_answers(db: Session, user: User) -> list[_AnswerRec]:
    """All answered practice + mock answers with resolved question_id + topic."""
    recs: list[_AnswerRec] = []

    practice = db.execute(
        select(
            Question.id,
            Question.topic,
            PracticeAnswer.is_correct,
            PracticeAnswer.attempted_at,
        )
        .join(QuestionVersion, QuestionVersion.id == PracticeAnswer.question_version_id)
        .join(Question, Question.id == QuestionVersion.question_id)
        .join(PracticeSession, PracticeSession.id == PracticeAnswer.practice_session_id)
        .where(PracticeSession.user_id == user.id)
    ).all()
    for qid, topic, is_correct, when in practice:
        recs.append(_AnswerRec(qid, topic.value, bool(is_correct), _as_aware(when)))

    mock = db.execute(
        select(
            Question.id,
            Question.topic,
            MockAnswer.is_correct,
            MockAnswer.answered_at,
        )
        .join(QuestionVersion, QuestionVersion.id == MockAnswer.question_version_id)
        .join(Question, Question.id == QuestionVersion.question_id)
        .join(MockAttempt, MockAttempt.id == MockAnswer.mock_attempt_id)
        .where(
            MockAttempt.user_id == user.id,
            MockAnswer.selected_option_id.is_not(None),
        )
    ).all()
    for qid, topic, is_correct, when in mock:
        recs.append(_AnswerRec(qid, topic.value, bool(is_correct), _as_aware(when)))

    return recs


def compute(db: Session, user: User) -> dict:
    cfg = get_readiness_config()
    exam = get_exam_config(user.profile.category if user.profile else None) \
        if user.profile else get_exam_config()
    now = _now()
    window_start = now - timedelta(days=cfg.recent_window_days)

    recs = _gather_answers(db, user)

    # unique questions attempted (all-time, distinct question_id)
    unique_ids = {r.question_id for r in recs}
    unique_count = len(unique_ids)

    # per-topic all-time answer counts (for coverage + weak-topics display)
    topic_all: dict[str, dict[str, int]] = {}
    for r in recs:
        b = topic_all.setdefault(r.topic, {"answered": 0, "correct": 0})
        b["answered"] += 1
        if r.is_correct:
            b["correct"] += 1

    # per-topic windowed counts (for mastery component + gate_major_topic_min)
    topic_win: dict[str, dict[str, int]] = {}
    for r in recs:
        if r.when is not None and r.when >= window_start:
            b = topic_win.setdefault(r.topic, {"answered": 0, "correct": 0})
            b["answered"] += 1
            if r.is_correct:
                b["correct"] += 1

    # ---- completed mocks (all-time, newest first) ---- #
    completed = list(
        db.scalars(
            select(MockAttempt)
            .where(MockAttempt.user_id == user.id, MockAttempt.status == MockStatus.COMPLETED)
            .order_by(MockAttempt.started_at.desc())
        )
    )
    mocks_completed = len(completed)

    # ---- 1. mock performance (.40) ---- #
    recent = [
        m for m in completed
        if (_as_aware(m.completed_at) or now) >= window_start
    ][: cfg.recent_mock_count]
    if recent:
        n = len(recent)
        num = 0.0
        den = 0.0
        for i, m in enumerate(recent):  # newest first -> highest weight
            weight = n - i
            ratio = (m.correct_count or 0) / (m.question_count or exam.questions)
            num += weight * ratio
            den += weight
        mock_performance = num / den if den else 0.0
    else:
        mock_performance = 0.0

    # ---- 2. topic mastery (.30) ---- #
    counted_masteries: dict[str, float] = {}
    for topic_value, b in topic_win.items():
        if b["answered"] >= cfg.topic_min_answers:
            counted_masteries[topic_value] = b["correct"] / b["answered"]
    topic_mastery = (
        sum(counted_masteries.values()) / len(counted_masteries)
        if counted_masteries else 0.0
    )

    # ---- 3. mistake recovery (.20) ---- #
    total_mistakes = int(
        db.scalar(select(func.count(MistakeEntry.id)).where(
            MistakeEntry.user_id == user.id)) or 0
    )
    resolved_mistakes = int(
        db.scalar(select(func.count(MistakeEntry.id)).where(
            MistakeEntry.user_id == user.id, MistakeEntry.resolved.is_(True))) or 0
    )
    if total_mistakes == 0:
        mistake_recovery = 1.0
    else:
        mistake_recovery = resolved_mistakes / total_mistakes
    mistakes_low_confidence = total_mistakes < cfg.mistakes_min_sample

    # ---- 4. consistency / recency (.10) ---- #
    seven_ago = stats.local_date_for(user) - timedelta(days=6)
    active_dates = list(
        db.scalars(
            select(StudentDailyStat.stat_date).where(
                StudentDailyStat.user_id == user.id,
                StudentDailyStat.answers_count > 0,
                StudentDailyStat.stat_date >= seven_ago,
            )
        )
    )
    active_days_7 = len(set(active_dates))
    consistency = min(1.0, active_days_7 / 4.0)
    last_active = db.scalar(
        select(func.max(StudentDailyStat.stat_date)).where(
            StudentDailyStat.user_id == user.id
        )
    )
    idle_days = (stats.local_date_for(user) - last_active).days if last_active else 9999
    recency_factor = 1.0
    if idle_days > 7:
        recency_factor = 0.25
    elif idle_days > 3:
        recency_factor = 0.5
    consistency_recency = consistency * recency_factor

    # ---- curriculum coverage gate (every v1 topic >= gate_min_answers_per_topic) ---- #
    remaining_coverage: list[dict] = []
    for topic in Topic:
        answered = topic_all.get(topic.value, {}).get("answered", 0)
        if answered < cfg.gate_min_answers_per_topic:
            remaining_coverage.append(
                {
                    "topic": topic.value,
                    "label": topic_label(topic.value),
                    "answered": answered,
                    "needed": cfg.gate_min_answers_per_topic,
                }
            )
    coverage_met = len(remaining_coverage) == 0

    # ---- score ---- #
    raw = (
        cfg.weight_mock_performance * mock_performance
        + cfg.weight_topic_mastery * topic_mastery
        + cfg.weight_mistake_recovery * mistake_recovery
        + cfg.weight_consistency_recency * consistency_recency
    )
    score = round(100 * raw)

    # ---- state resolution ---- #
    if unique_count < cfg.min_unique_questions_for_display or mocks_completed == 0:
        state = ReadinessState.INSUFFICIENT_DATA
    elif (
        mocks_completed < cfg.min_mocks_for_full
        or unique_count < cfg.min_unique_questions_for_full
        or not coverage_met
    ):
        state = ReadinessState.INITIAL
    else:
        state = ReadinessState.READY_ESTIMATE

    # ---- advisory "exam ready" gate ---- #
    last_n = completed[: cfg.gate_last_n_mocks]
    passes = sum(1 for m in last_n if (m.correct_count or 0) >= exam.minimum_correct)
    no_weak_counted = all(
        m >= cfg.gate_major_topic_min for m in counted_masteries.values()
    ) if counted_masteries else False
    gate_passed = (
        mocks_completed >= cfg.gate_last_n_mocks
        and passes >= cfg.gate_required_passes
        and coverage_met
        and no_weak_counted
        and unique_count >= cfg.gate_min_unique_questions
    )
    exam_ready = bool(gate_passed and state == ReadinessState.READY_ESTIMATE)

    # ---- label (score null unless initial/ready_estimate) ---- #
    if state == ReadinessState.INSUFFICIENT_DATA:
        label = "Ma'lumot yetarli emas"
        out_score: int | None = None
    elif state == ReadinessState.INITIAL:
        label = f"Boshlang'ich daraja: {score}%"
        out_score = score
    else:
        label = f"Imtihonga tayyorlik: {score}%"
        out_score = score

    # ---- weak topics (lowest mastery first; under-sampled flagged) ---- #
    weak_topics = []
    for topic_value, b in topic_all.items():
        answered = b["answered"]
        mastery = b["correct"] / answered if answered else 0.0
        weak_topics.append(
            {
                "topic": topic_value,
                "label": topic_label(topic_value),
                "answered": answered,
                "mastery": round(mastery, 3),
                "needs_more_practice": answered < cfg.topic_min_answers,
            }
        )
    weak_topics.sort(key=lambda t: (t["mastery"], -t["answered"]))

    return {
        "state": state.value,
        "label": label,
        "score": out_score,
        "exam_ready": exam_ready,
        "unique_questions_attempted": unique_count,
        "mocks_completed": mocks_completed,
        "coverage_met": coverage_met,
        "remaining_coverage": remaining_coverage,
        "components": {
            "mock_performance": {
                "value": round(mock_performance, 3),
                "weight": cfg.weight_mock_performance,
                "recent_mocks": len(recent),
            },
            "topic_mastery": {
                "value": round(topic_mastery, 3),
                "weight": cfg.weight_topic_mastery,
                "counted_topics": len(counted_masteries),
            },
            "mistake_recovery": {
                "value": round(mistake_recovery, 3),
                "weight": cfg.weight_mistake_recovery,
                "total": total_mistakes,
                "resolved": resolved_mistakes,
                "low_confidence": mistakes_low_confidence,
            },
            "consistency_recency": {
                "value": round(consistency_recency, 3),
                "weight": cfg.weight_consistency_recency,
                "active_days_7": active_days_7,
                "idle_days": idle_days if last_active else None,
            },
        },
        "weak_topics": weak_topics,
    }


def recompute_and_cache(db: Session, user: User) -> dict:
    """Compute readiness and upsert the optional ReadinessSnapshot cache."""
    payload = compute(db, user)
    snap = db.scalar(select(ReadinessSnapshot).where(ReadinessSnapshot.user_id == user.id))
    if snap is None:
        snap = ReadinessSnapshot(user_id=user.id)
        db.add(snap)
    snap.state = ReadinessState(payload["state"])
    snap.score = payload["score"]
    snap.exam_ready = payload["exam_ready"]
    snap.payload_json = payload
    snap.computed_at = _now()
    db.flush()
    return payload
