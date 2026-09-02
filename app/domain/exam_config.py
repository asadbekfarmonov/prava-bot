"""Single source of truth for legal exam rules and learning thresholds.

These are **domain configuration**, not deployment configuration. They must never
be read from environment variables (see docs/spec/01-exam-and-rules.md and
docs/spec/05-architecture.md). Each configuration carries a ``version`` so that a
``MockAttempt`` can snapshot the applicable values at start; historical attempts
stay interpretable if the rules later change.

Slice 1 does not implement the mock, but the exam config already lives here so the
mock slice snapshots from a single authority and never from scattered literals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.enums import Topic

from dataclasses import dataclass, field
from datetime import date

from app.domain.enums import Category


@dataclass(frozen=True)
class ExamConfig:
    version: int
    category: Category
    last_verified: date
    questions: int
    time_limit_seconds: int
    minimum_correct: int
    maximum_mistakes: int
    answer_options_min: int
    answer_options_max: int
    correct_options_per_question: int
    result_validity_months: int  # informational (process), not enforced in v1


# Category B, exam config v1 (verified 2026-08-31).
EXAM_CONFIG_B_V1 = ExamConfig(
    version=1,
    category=Category.B,
    last_verified=date(2026, 8, 31),
    questions=20,
    time_limit_seconds=1500,  # 25 minutes, single global timer
    minimum_correct=18,       # pass threshold
    maximum_mistakes=2,
    answer_options_min=2,
    answer_options_max=5,
    correct_options_per_question=1,
    result_validity_months=2,
)

# The current exam config per category. A1/C/D are reserved and intentionally absent in v1.
EXAM_CONFIGS: dict[Category, ExamConfig] = {
    Category.B: EXAM_CONFIG_B_V1,
}


def get_exam_config(category: Category = Category.B) -> ExamConfig:
    try:
        return EXAM_CONFIGS[category]
    except KeyError as exc:
        raise ValueError(f"No exam configuration for category {category!r} in v1.") from exc


# --------------------------------------------------------------------------- #
# Readiness configuration (docs/spec/07-readiness.md — the exact algorithm).
# All thresholds/weights are DOMAIN config; never env vars. Tuning them must not
# require code changes elsewhere.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ReadinessConfig:
    version: int = 1
    # state gating
    min_unique_questions_for_display: int = 40
    min_unique_questions_for_full: int = 100
    min_mocks_for_full: int = 3
    # component windows / samples
    recent_mock_count: int = 5
    recent_window_days: int = 30
    topic_min_answers: int = 5      # answers needed for a topic to COUNT in mastery
    mistakes_min_sample: int = 5
    # curriculum coverage (closes the "only studied signs & parking" gap)
    gate_min_answers_per_topic: int = 5
    # advisory "exam ready" gate
    gate_last_n_mocks: int = 3
    gate_required_passes: int = 2
    gate_major_topic_min: float = 0.70
    gate_min_unique_questions: int = 100
    # weights (sum = 1.0)
    weight_mock_performance: float = 0.40
    weight_topic_mastery: float = 0.30
    weight_mistake_recovery: float = 0.20
    weight_consistency_recency: float = 0.10


READINESS_CONFIG = ReadinessConfig()


def get_readiness_config() -> ReadinessConfig:
    """Return the current readiness config (module global; monkeypatchable in tests)."""
    return READINESS_CONFIG


# Backwards-compatible alias (older code/tests may import this name).
ReadinessThresholds = ReadinessConfig
READINESS_THRESHOLDS = READINESS_CONFIG


# --------------------------------------------------------------------------- #
# Ranking configuration (docs/spec/10-ranking.md — learning-weighted points).
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RankingConfig:
    version: int = 1
    practice_unique_correct: int = 1
    mistake_recovery: int = 2
    mock_correct: int = 1
    # highest pass bonus (only one per mock; keyed by server-graded correct_count)
    mock_bonus: dict[int, int] = field(default_factory=lambda: {18: 10, 19: 20, 20: 35})
    daily_consistency: int = 5
    daily_practice_cap: int = 50
    min_answer_seconds: int = 2         # answers faster than this earn 0 (anti-bot)
    max_mock_bonus_per_day: int = 3     # only N mock bonuses count per day
    # an "active day" = met the daily goal OR answered at least this many questions
    active_day_min_answers: int = 10
    # server max page size for leaderboard reads
    leaderboard_max_limit: int = 100


RANKING_CONFIG = RankingConfig()


def get_ranking_config() -> RankingConfig:
    """Return the current ranking config (module global; monkeypatchable in tests)."""
    return RANKING_CONFIG


# The v1 curriculum topics that the coverage gate requires (all 15 YHQ groups).
def all_v1_topics() -> list["Topic"]:
    from app.domain.enums import Topic

    return list(Topic)


# Answer-option bounds exposed for validation helpers (single source).
ANSWER_OPTIONS_MIN: int = EXAM_CONFIG_B_V1.answer_options_min
ANSWER_OPTIONS_MAX: int = EXAM_CONFIG_B_V1.answer_options_max
CORRECT_OPTIONS_PER_QUESTION: int = EXAM_CONFIG_B_V1.correct_options_per_question


# --------------------------------------------------------------------------- #
# Personalized practice ("Siz uchun") selector configuration (docs/spec/17 §A).
# DOMAIN config (never env). The selector reuses stored PracticeAnswer / MockAnswer
# / MistakeEntry facts and picks a next question from weighted buckets, in this
# priority intent: unresolved mistakes -> weak topics -> unseen -> stale.
# Weights are relative and only applied across NON-EMPTY buckets.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PersonalizedPracticeConfig:
    version: int = 1
    # relative selection weights across non-empty buckets
    weight_mistakes: int = 40
    weight_weak_topic: int = 30
    weight_unseen: int = 20
    weight_stale: int = 10
    # a topic is "weak" when it has >= min_answers answered AND mastery < max_mastery
    weak_topic_min_answers: int = 5
    weak_topic_max_mastery: float = 0.75
    # a previously-seen question is "stale" if not answered in the last N days
    stale_days: int = 14
    # how many unique questions must be unseen before the unseen bucket is preferred
    unseen_min_pool: int = 1


PERSONALIZED_PRACTICE_CONFIG = PersonalizedPracticeConfig()


def get_personalized_practice_config() -> PersonalizedPracticeConfig:
    """Return the current personalized-practice config (monkeypatchable in tests)."""
    return PERSONALIZED_PRACTICE_CONFIG


# --------------------------------------------------------------------------- #
# Theory / YHQ Handbook configuration (docs/spec/14). DOMAIN config, never env.
# 'mastered' is derived server-side from question performance on linked questions,
# NOT from opening a page. These thresholds gate that derivation.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TheoryConfig:
    version: int = 1
    # A target counts as 'practised' after at least this many answered linked questions.
    practised_min_answers: int = 1
    # 'mastered' needs at least this many answered linked questions AND
    # recent accuracy >= mastery_accuracy over the most recent window.
    mastered_min_answers: int = 4
    mastered_accuracy: float = 0.80
    # Only the most-recent N answers per linked question set feed the accuracy window.
    mastery_recent_window: int = 20


THEORY_CONFIG = TheoryConfig()


def get_theory_config() -> TheoryConfig:
    """Return the current theory config (module global; monkeypatchable in tests)."""
    return THEORY_CONFIG
