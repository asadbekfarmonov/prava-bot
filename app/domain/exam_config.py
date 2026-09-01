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


@dataclass(frozen=True)
class ReadinessThresholds:
    """Readiness/ranking thresholds also live in domain config (docs/spec/07)."""

    version: int = 1
    minimum_answers_for_estimate: int = 100
    minimum_topics_covered: int = 15  # curriculum-coverage gate: all 15 topics
    ready_estimate_accuracy: float = 0.85


READINESS_THRESHOLDS = ReadinessThresholds()

# Answer-option bounds exposed for validation helpers (single source).
ANSWER_OPTIONS_MIN: int = EXAM_CONFIG_B_V1.answer_options_min
ANSWER_OPTIONS_MAX: int = EXAM_CONFIG_B_V1.answer_options_max
CORRECT_OPTIONS_PER_QUESTION: int = EXAM_CONFIG_B_V1.correct_options_per_question
