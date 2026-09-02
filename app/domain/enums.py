from enum import StrEnum

# --------------------------------------------------------------------------- #
# Carried follow-up (Slice 5): enum ``values_callable`` — DELIBERATELY SKIPPED.
#
# These are StrEnums whose ``.value`` is the lowercase form the spec documents
# (e.g. MockStatus.IN_PROGRESS.value == "in_progress"). SQLAlchemy's non-native
# ``Enum`` columns in app/domain/models.py currently persist by member *name*
# (verified: a MockAttempt.status row stores "IN_PROGRESS", not "in_progress").
#
# Switching those columns to ``values_callable=lambda e: [m.value for m in e]``
# would change the on-disk representation for ~15 enum columns across every table.
# Migrations 0001-0004 and all existing rows/fixtures were written with the *name*
# form, so the change would require a data migration (UPDATE every enum column) and
# would silently break reads of any already-persisted data — high risk, broad blast
# radius, for a Slice-5 (production wiring) change.
#
# There is no user-facing correctness gap: the API already emits the lowercase
# ``.value`` at the boundary (e.g. mock._attempt_meta returns ``status.value``), and
# comparisons use the Python enum objects, not the stored string. Per the task's
# explicit allowance, this follow-up is skipped and documented rather than applied.
# --------------------------------------------------------------------------- #


class Category(StrEnum):
    """Driving-licence category. v1 ships B only; the rest are reserved."""

    B = "B"
    A = "A"
    A1 = "A1"
    C = "C"
    D = "D"


class Topic(StrEnum):
    """The 15 YHQ learning topics (docs/spec/06-content-plan.md).

    Used for learning organisation and readiness coverage only — NOT a claimed
    exam blueprint.
    """

    GENERAL_RULES = "general_rules"
    ROAD_SIGNS = "road_signs"
    ROAD_MARKINGS = "road_markings"
    SIGNALS = "signals"
    INTERSECTIONS = "intersections"
    MANOEUVRING = "manoeuvring"
    SPEED_DISTANCE = "speed_distance"
    OVERTAKING = "overtaking"
    STOPPING_PARKING = "stopping_parking"
    VULNERABLE_USERS = "vulnerable_users"
    RAILWAY_CROSSINGS = "railway_crossings"
    MOTORWAYS_SPECIAL = "motorways_special"
    VEHICLE_CONDITION = "vehicle_condition"
    TRANSPORT_OF_PEOPLE_CARGO = "transport_of_people_cargo"
    EMERGENCIES_FIRST_AID = "emergencies_first_aid"


class Language(StrEnum):
    """Content/UI language. v1 writes only ``uz``; ``ru`` reserved for v2."""

    UZ = "uz"
    RU = "ru"


class MediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    GIF = "gif"


class VersionStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    REVIEWED = "reviewed"
    PUBLISHED = "published"
    NEEDS_REVERIFICATION = "needs_reverification"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class AdminRole(StrEnum):
    CONTENT_AUTHOR = "content_author"
    CONTENT_REVIEWER = "content_reviewer"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class MockStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class RuleStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REPEALED = "repealed"


class PracticeSource(StrEnum):
    TOPIC = "topic"
    MIXED = "mixed"
    MISTAKES = "mistakes"
    SIGN_TRAINER = "sign_trainer"
    DIAGNOSTIC = "diagnostic"


class SourceKind(StrEnum):
    REFERENCE = "reference"
    DIAGRAM_SOURCE = "diagram_source"
    MEDIA_SOURCE = "media_source"
    OTHER = "other"


class ReportReason(StrEnum):
    WRONG_ANSWER = "wrong_answer"
    UNCLEAR_EXPLANATION = "unclear_explanation"
    IMAGE_PROBLEM = "image_problem"
    OUTDATED_RULE = "outdated_rule"
    TYPO = "typo"
    OTHER = "other"


class ReportStatus(StrEnum):
    OPEN = "open"
    TRIAGED = "triaged"
    RESOLVED = "resolved"
    REJECTED = "rejected"


# Admin role capability ordering (low -> high). Used by require_role(min_role).
ADMIN_ROLE_ORDER: dict[AdminRole, int] = {
    AdminRole.CONTENT_AUTHOR: 1,
    AdminRole.CONTENT_REVIEWER: 2,
    AdminRole.ADMIN: 3,
    AdminRole.SUPERADMIN: 4,
}


def role_rank(role: "AdminRole | None") -> int:
    """Numeric capability rank; ``None`` (ordinary student) is 0."""
    if role is None:
        return 0
    return ADMIN_ROLE_ORDER.get(role, 0)


class PointsSource(StrEnum):
    """Ledger point sources (docs/spec/10-ranking.md)."""

    PRACTICE_UNIQUE = "practice_unique"
    MISTAKE_RECOVERY = "mistake_recovery"
    MOCK_CORRECT = "mock_correct"
    MOCK_BONUS = "mock_bonus"
    DAILY_CONSISTENCY = "daily_consistency"


class ReadinessState(StrEnum):
    """Readiness display states (docs/spec/07-readiness.md)."""

    INSUFFICIENT_DATA = "insufficient_data"
    INITIAL = "initial"
    READY_ESTIMATE = "ready_estimate"
