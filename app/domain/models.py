from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base
from app.domain.enums import (
    AssessmentAttemptStatus,
    AssessmentRevealMode,
    AssessmentSelectionMode,
    AssessmentStatus,
    AssessmentType,
    AdminRole,
    Category,
    Language,
    MediaType,
    MockStatus,
    PointsSource,
    PracticeSource,
    ReadinessState,
    ReportReason,
    ReportStatus,
    RoadMarkingGroup,
    RoadSignFamily,
    RuleStatus,
    SourceKind,
    TheoryArticleKind,
    TheoryBlockType,
    TheoryProgressState,
    TheoryTargetType,
    Topic,
    TrafficLightKind,
    VersionStatus,
)


def _uuid() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# --------------------------------------------------------------------------- #
# Users, roles, profiles
# --------------------------------------------------------------------------- #
class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    telegram_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    photo_url: Mapped[str | None] = mapped_column(String(1000))
    # null for ordinary students; set for staff (allowlist-gated + resolved server-side).
    admin_role: Mapped[AdminRole | None] = mapped_column(Enum(AdminRole, native_enum=False, length=32))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class StudentProfile(TimestampMixin, Base):
    __tablename__ = "student_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    ranking_name: Mapped[str | None] = mapped_column(String(255))
    show_on_ranking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category: Mapped[Category] = mapped_column(
        Enum(Category, native_enum=False, length=8), default=Category.B, nullable=False
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), default=Language.UZ, nullable=False
    )
    target_exam_date: Mapped[date | None] = mapped_column(Date)
    daily_goal: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Tashkent", nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="profile")


# --------------------------------------------------------------------------- #
# Question container + immutable versions
# --------------------------------------------------------------------------- #
class Question(TimestampMixin, Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    category: Mapped[Category] = mapped_column(
        Enum(Category, native_enum=False, length=8), nullable=False, index=True
    )
    topic: Mapped[Topic] = mapped_column(
        Enum(Topic, native_enum=False, length=48), nullable=False, index=True
    )
    subtopic: Mapped[str | None] = mapped_column(String(255))
    is_sign_question: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # The published version served to learners. Circular FK -> resolved with use_alter.
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("question_versions.id", use_alter=True, name="fk_question_current_version"),
        nullable=True,
    )
    lifecycle_status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    current_version: Mapped["QuestionVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    versions: Mapped[list["QuestionVersion"]] = relationship(
        back_populates="question",
        foreign_keys="QuestionVersion.question_id",
        cascade="all, delete-orphan",
    )


class QuestionVersion(TimestampMixin, Base):
    """Immutable once published or referenced by any attempt."""

    __tablename__ = "question_versions"
    __table_args__ = (UniqueConstraint("question_id", "version", name="uq_question_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )
    media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    difficulty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1..3
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    authored_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    question: Mapped[Question] = relationship(
        back_populates="versions", foreign_keys=[question_id]
    )
    media: Mapped["QuestionMedia | None"] = relationship()
    translations: Mapped[list["QuestionVersionTranslation"]] = relationship(
        back_populates="question_version", cascade="all, delete-orphan"
    )
    options: Mapped[list["AnswerOption"]] = relationship(
        back_populates="question_version", cascade="all, delete-orphan"
    )
    rule_links: Mapped[list["QuestionVersionRule"]] = relationship(
        back_populates="question_version", cascade="all, delete-orphan"
    )
    sources: Mapped[list["QuestionVersionSource"]] = relationship(
        back_populates="question_version", cascade="all, delete-orphan"
    )


class QuestionVersionTranslation(TimestampMixin, Base):
    __tablename__ = "question_version_translations"
    __table_args__ = (
        UniqueConstraint("question_version_id", "language", name="uq_qv_translation_lang"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    short_explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)

    question_version: Mapped[QuestionVersion] = relationship(back_populates="translations")


class AnswerOption(TimestampMixin, Base):
    __tablename__ = "answer_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..5
    # Language-neutral; never sent to the client mid-mock.
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    question_version: Mapped[QuestionVersion] = relationship(back_populates="options")
    translations: Mapped[list["AnswerOptionTranslation"]] = relationship(
        back_populates="answer_option", cascade="all, delete-orphan"
    )


class AnswerOptionTranslation(TimestampMixin, Base):
    __tablename__ = "answer_option_translations"
    __table_args__ = (
        UniqueConstraint("answer_option_id", "language", name="uq_option_translation_lang"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    answer_option_id: Mapped[str] = mapped_column(
        ForeignKey("answer_options.id"), nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)

    answer_option: Mapped[AnswerOption] = relationship(back_populates="translations")


# --------------------------------------------------------------------------- #
# Rule model (translation-ready legal provenance)
# --------------------------------------------------------------------------- #
class Rule(TimestampMixin, Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # e.g. "YHQ:13.9"
    source_url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    source_document: Mapped[str | None] = mapped_column(String(255))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[RuleStatus] = mapped_column(
        Enum(RuleStatus, native_enum=False, length=16), default=RuleStatus.ACTIVE, nullable=False
    )

    translations: Mapped[list["RuleTranslation"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )


class RuleTranslation(TimestampMixin, Base):
    __tablename__ = "rule_translations"
    __table_args__ = (UniqueConstraint("rule_id", "language", name="uq_rule_translation_lang"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    rule: Mapped[Rule] = relationship(back_populates="translations")


class QuestionVersionRule(TimestampMixin, Base):
    """Snapshot of which rule (and which rule version) a version relies on."""

    __tablename__ = "question_version_rules"
    __table_args__ = (
        UniqueConstraint("question_version_id", "rule_id", name="uq_qv_rule"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)  # snapshot at authoring

    question_version: Mapped[QuestionVersion] = relationship(back_populates="rule_links")
    rule: Mapped[Rule] = relationship()


class QuestionVersionSource(TimestampMixin, Base):
    """Supporting provenance/research, distinct from the legal basis (Rule)."""

    __tablename__ = "question_version_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[SourceKind] = mapped_column(
        Enum(SourceKind, native_enum=False, length=32), default=SourceKind.REFERENCE, nullable=False
    )

    question_version: Mapped[QuestionVersion] = relationship(back_populates="sources")


# --------------------------------------------------------------------------- #
# Media (content-addressed, immutable; metadata only — no bytes in DB)
# --------------------------------------------------------------------------- #
class QuestionMedia(TimestampMixin, Base):
    __tablename__ = "question_media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType, native_enum=False, length=16), nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    poster_storage_key: Mapped[str | None] = mapped_column(String(512))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)

    translations: Mapped[list["QuestionMediaTranslation"]] = relationship(
        back_populates="media", cascade="all, delete-orphan"
    )


class QuestionMediaTranslation(TimestampMixin, Base):
    __tablename__ = "question_media_translations"
    __table_args__ = (UniqueConstraint("media_id", "language", name="uq_media_translation_lang"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    media_id: Mapped[str] = mapped_column(
        ForeignKey("question_media.id"), nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    alt_text: Mapped[str] = mapped_column(Text, nullable=False)

    media: Mapped[QuestionMedia] = relationship(back_populates="translations")


# --------------------------------------------------------------------------- #
# Practice (repeatable attempts, version-pinned)
# --------------------------------------------------------------------------- #
class PracticeSession(TimestampMixin, Base):
    __tablename__ = "practice_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[Category] = mapped_column(
        Enum(Category, native_enum=False, length=8), default=Category.B, nullable=False
    )
    topic: Mapped[Topic | None] = mapped_column(Enum(Topic, native_enum=False, length=48))
    source: Mapped[PracticeSource] = mapped_column(
        Enum(PracticeSource, native_enum=False, length=32),
        default=PracticeSource.TOPIC,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()
    answers: Mapped[list["PracticeAnswer"]] = relationship(
        back_populates="practice_session", cascade="all, delete-orphan"
    )


class PracticeAnswer(TimestampMixin, Base):
    __tablename__ = "practice_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    practice_session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_sessions.id"), nullable=False, index=True
    )
    # Exact content the user saw (version-pinned). No global (user, question) uniqueness.
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
    selected_option_id: Mapped[str | None] = mapped_column(ForeignKey("answer_options.id"))
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    practice_session: Mapped[PracticeSession] = relationship(back_populates="answers")
    question_version: Mapped[QuestionVersion] = relationship()


# --------------------------------------------------------------------------- #
# Mock exam (self-contained, version-pinned snapshot)
# --------------------------------------------------------------------------- #
class MockAttempt(TimestampMixin, Base):
    __tablename__ = "mock_attempts"

    # Atomic guarantee of at most one in-progress attempt per user (DB-enforced,
    # complementing the application check which alone is racy). Status persists by
    # member NAME (native_enum=False), so the predicate matches 'IN_PROGRESS'.
    __table_args__ = (
        Index(
            "uq_mock_one_in_progress_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'IN_PROGRESS'"),
            postgresql_where=text("status = 'IN_PROGRESS'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[Category] = mapped_column(
        Enum(Category, native_enum=False, length=8), default=Category.B, nullable=False
    )
    # Snapshot of the user's language at start (v1: uz).
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), default=Language.UZ, nullable=False
    )
    status: Mapped[MockStatus] = mapped_column(
        Enum(MockStatus, native_enum=False, length=16),
        default=MockStatus.IN_PROGRESS,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # = started_at + time_limit_seconds; the SINGLE server-authoritative deadline.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Snapshot of the single exam config at start (docs/spec/01, 05).
    exam_config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    pass_correct: Mapped[int] = mapped_column(Integer, nullable=False)
    # Graded server-side at submit/expiry.
    correct_count: Mapped[int | None] = mapped_column(Integer)
    answered_count: Mapped[int | None] = mapped_column(Integer)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    # per-topic breakdown, missed list, avg answer time.
    result_json: Mapped[dict | None] = mapped_column(JSON)

    user: Mapped[User] = relationship()
    questions: Mapped[list["MockQuestion"]] = relationship(
        back_populates="mock_attempt", cascade="all, delete-orphan"
    )
    answers: Mapped[list["MockAnswer"]] = relationship(
        back_populates="mock_attempt", cascade="all, delete-orphan"
    )


class MockQuestion(TimestampMixin, Base):
    __tablename__ = "mock_questions"
    __table_args__ = (
        UniqueConstraint("mock_attempt_id", "question_version_id", name="uq_mock_question_version"),
        UniqueConstraint("mock_attempt_id", "position", name="uq_mock_question_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mock_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("mock_attempts.id"), nullable=False, index=True
    )
    # PINNED to the immutable version at start; never a live question.
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    mock_attempt: Mapped[MockAttempt] = relationship(back_populates="questions")
    question_version: Mapped[QuestionVersion] = relationship()


class MockAnswer(TimestampMixin, Base):
    __tablename__ = "mock_answers"
    __table_args__ = (
        UniqueConstraint("mock_attempt_id", "question_version_id", name="uq_mock_answer_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mock_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("mock_attempts.id"), nullable=False, index=True
    )
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
    selected_option_id: Mapped[str | None] = mapped_column(ForeignKey("answer_options.id"))
    # Graded server-side at submit; never trusted from the client.
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    mock_attempt: Mapped[MockAttempt] = relationship(back_populates="answers")
    question_version: Mapped[QuestionVersion] = relationship()


# --------------------------------------------------------------------------- #
# Content reports (user-filed; feed the admin queue)
# --------------------------------------------------------------------------- #
class ContentReport(TimestampMixin, Base):
    __tablename__ = "content_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # The EXACT version the reporter saw (never the mutable container). Nullable so the
    # same queue can also hold Theory-content reports (docs/spec/14) keyed by target.
    question_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_versions.id"), nullable=True, index=True
    )
    # Optional Theory target (section/article/sign/marking/gesture/light/rule).
    theory_target_type: Mapped[str | None] = mapped_column(String(32), index=True)
    theory_target_id: Mapped[str | None] = mapped_column(String(36), index=True)
    reason: Mapped[ReportReason] = mapped_column(
        Enum(ReportReason, native_enum=False, length=32), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, native_enum=False, length=16),
        default=ReportStatus.OPEN,
        nullable=False,
        index=True,
    )
    resolved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    question_version: Mapped[QuestionVersion] = relationship()


# --------------------------------------------------------------------------- #
# Admin audit trail (every create/edit/review/publish/supersede/archive/import/
# report-resolve is recorded — docs/spec/08 + 09)
# --------------------------------------------------------------------------- #
class AdminAuditEvent(TimestampMixin, Base):
    __tablename__ = "admin_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    version: Mapped[int | None] = mapped_column(Integer)
    # Human/machine-readable extra context (never PII payloads).
    detail: Mapped[dict | None] = mapped_column(JSON)
    warning: Mapped[str | None] = mapped_column(Text)

    actor: Mapped[User | None] = relationship(foreign_keys=[actor_user_id])


# --------------------------------------------------------------------------- #
# Slice 4 — Mistakes, ranking ledger, readiness cache, daily stats/streak
# (docs/spec/02 domain-model, 07 readiness, 10 ranking)
# --------------------------------------------------------------------------- #
class MistakeEntry(TimestampMixin, Base):
    """One row per (user, question) that was ever missed. Mistakes track the
    *question container*, not a version — re-practice uses the current version.
    v1 resolves on the first correct re-answer (spaced repetition is v2)."""

    __tablename__ = "mistake_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_mistake_user_question"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id"), nullable=False, index=True
    )
    first_missed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_missed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    miss_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    last_result: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship()
    question: Mapped[Question] = relationship()


class UserPointsLedger(TimestampMixin, Base):
    """Append-only, idempotent points ledger (docs/spec/10). Points are computed
    server-side from stored facts; the client never submits points. The UNIQUE
    constraint makes crediting idempotent under retries/concurrency."""

    __tablename__ = "user_points_ledger"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "source", "ref_type", "ref_id", name="uq_ledger_idempotent"
        ),
        Index("ix_ledger_user_local_date", "user_id", "local_date"),
        Index("ix_ledger_local_date", "local_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source: Mapped[PointsSource] = mapped_column(
        Enum(PointsSource, native_enum=False, length=32), nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_type: Mapped[str] = mapped_column(String(32), nullable=False)  # question|mock_attempt|...
    ref_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)  # daily caps + aggregation

    user: Mapped[User] = relationship()


class ReadinessSnapshot(TimestampMixin, Base):
    """Optional cache of the computed readiness (docs/spec/07). One row per user,
    recomputed after each mock completion or on demand."""

    __tablename__ = "readiness_snapshots"
    __table_args__ = (UniqueConstraint("user_id", name="uq_readiness_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    state: Mapped[ReadinessState] = mapped_column(
        Enum(ReadinessState, native_enum=False, length=32), nullable=False
    )
    score: Mapped[int | None] = mapped_column(Integer)  # null unless initial/ready_estimate
    exam_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON)  # full breakdown for the dashboard
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()


class StudentDailyStat(TimestampMixin, Base):
    """Per-day activity roll-up (kept from SATStudy; feeds streaks + ranking
    consistency). One row per (user, local date)."""

    __tablename__ = "student_daily_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "stat_date", name="uq_daily_stat_user_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    answers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship()


class Streak(TimestampMixin, Base):
    """Current/longest active-day streak (kept from SATStudy). One row per user."""

    __tablename__ = "streaks"
    __table_args__ = (UniqueConstraint("user_id", name="uq_streak_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_active_date: Mapped[date | None] = mapped_column(Date)

    user: Mapped[User] = relationship()


# --------------------------------------------------------------------------- #
# Theory / YHQ Handbook (docs/spec/14) — sections, articles (immutable versions),
# structured content blocks, rule/question links, progress, favorites.
# Reuses: Rule/RuleTranslation, QuestionMedia, Question, the immutable-version +
# review lifecycle (VersionStatus), and the i18n translation-table pattern.
# --------------------------------------------------------------------------- #
class TheorySection(TimestampMixin, Base):
    __tablename__ = "theory_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    topic: Mapped[Topic | None] = mapped_column(Enum(Topic, native_enum=False, length=48))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    icon_media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )

    translations: Mapped[list["TheorySectionTranslation"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )
    articles: Mapped[list["TheoryArticle"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )
    icon_media: Mapped["QuestionMedia | None"] = relationship()


class TheorySectionTranslation(TimestampMixin, Base):
    __tablename__ = "theory_section_translations"
    __table_args__ = (
        UniqueConstraint("section_id", "language", name="uq_theory_section_translation_lang"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    section_id: Mapped[str] = mapped_column(
        ForeignKey("theory_sections.id"), nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    subtitle: Mapped[str] = mapped_column(Text, default="", nullable=False)

    section: Mapped[TheorySection] = relationship(back_populates="translations")


class TheoryArticle(TimestampMixin, Base):
    """Stable container + classification; shown content lives in immutable versions."""

    __tablename__ = "theory_articles"
    __table_args__ = (
        UniqueConstraint("section_id", "slug", name="uq_theory_article_slug_in_section"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    section_id: Mapped[str] = mapped_column(
        ForeignKey("theory_sections.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    kind: Mapped[TheoryArticleKind] = mapped_column(
        Enum(TheoryArticleKind, native_enum=False, length=32),
        default=TheoryArticleKind.LESSON,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "theory_article_versions.id",
            use_alter=True,
            name="fk_theory_article_current_version",
        ),
        nullable=True,
    )
    lifecycle_status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )

    section: Mapped[TheorySection] = relationship(back_populates="articles")
    current_version: Mapped["TheoryArticleVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    versions: Mapped[list["TheoryArticleVersion"]] = relationship(
        back_populates="article",
        foreign_keys="TheoryArticleVersion.article_id",
        cascade="all, delete-orphan",
    )
    question_links: Mapped[list["TheoryArticleQuestionLink"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class TheoryArticleVersion(TimestampMixin, Base):
    """Immutable once published/used (published_at is not None => locked)."""

    __tablename__ = "theory_article_versions"
    __table_args__ = (
        UniqueConstraint("article_id", "version", name="uq_theory_article_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    article_id: Mapped[str] = mapped_column(
        ForeignKey("theory_articles.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )
    hero_media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    authored_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    article: Mapped[TheoryArticle] = relationship(
        back_populates="versions", foreign_keys=[article_id]
    )
    hero_media: Mapped["QuestionMedia | None"] = relationship()
    translations: Mapped[list["TheoryArticleTranslation"]] = relationship(
        back_populates="article_version", cascade="all, delete-orphan"
    )
    blocks: Mapped[list["TheoryContentBlock"]] = relationship(
        back_populates="article_version", cascade="all, delete-orphan"
    )
    rule_links: Mapped[list["TheoryArticleRule"]] = relationship(
        back_populates="article_version", cascade="all, delete-orphan"
    )


class TheoryArticleTranslation(TimestampMixin, Base):
    __tablename__ = "theory_article_translations"
    __table_args__ = (
        UniqueConstraint(
            "article_version_id", "language", name="uq_theory_article_translation_lang"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    article_version_id: Mapped[str] = mapped_column(
        ForeignKey("theory_article_versions.id"), nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    article_version: Mapped[TheoryArticleVersion] = relationship(back_populates="translations")


class TheoryContentBlock(TimestampMixin, Base):
    """Ordered structured block (no raw HTML). data_json holds structured payloads
    (table cells, comparison pairs); human text lives in the translation."""

    __tablename__ = "theory_content_blocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    article_version_id: Mapped[str] = mapped_column(
        ForeignKey("theory_article_versions.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    type: Mapped[TheoryBlockType] = mapped_column(
        Enum(TheoryBlockType, native_enum=False, length=32), nullable=False
    )
    media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    rule_id: Mapped[str | None] = mapped_column(ForeignKey("rules.id"))
    ref_question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"))
    data_json: Mapped[dict | None] = mapped_column(JSON)

    article_version: Mapped[TheoryArticleVersion] = relationship(back_populates="blocks")
    translations: Mapped[list["TheoryContentBlockTranslation"]] = relationship(
        back_populates="block", cascade="all, delete-orphan"
    )
    media: Mapped["QuestionMedia | None"] = relationship()


class TheoryContentBlockTranslation(TimestampMixin, Base):
    __tablename__ = "theory_content_block_translations"
    __table_args__ = (
        UniqueConstraint("block_id", "language", name="uq_theory_block_translation_lang"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    block_id: Mapped[str] = mapped_column(
        ForeignKey("theory_content_blocks.id"), nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)

    block: Mapped[TheoryContentBlock] = relationship(back_populates="translations")


class TheoryArticleRule(TimestampMixin, Base):
    """Article version -> Rule(s), snapshotting the rule_version at authoring time."""

    __tablename__ = "theory_article_rules"
    __table_args__ = (
        UniqueConstraint("article_version_id", "rule_id", name="uq_theory_article_rule"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    article_version_id: Mapped[str] = mapped_column(
        ForeignKey("theory_article_versions.id"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)

    article_version: Mapped[TheoryArticleVersion] = relationship(back_populates="rule_links")
    rule: Mapped[Rule] = relationship()


class TheoryArticleQuestionLink(TimestampMixin, Base):
    """Theory -> Practice: which questions drill this article."""

    __tablename__ = "theory_article_question_links"
    __table_args__ = (
        UniqueConstraint("article_id", "question_id", name="uq_theory_article_question"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    article_id: Mapped[str] = mapped_column(
        ForeignKey("theory_articles.id"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id"), nullable=False, index=True
    )

    article: Mapped[TheoryArticle] = relationship(back_populates="question_links")
    question: Mapped[Question] = relationship()


class TheoryProgress(TimestampMixin, Base):
    """Per-user learning progress on a theory target. 'viewed' set on open; 'practised'
    and 'mastered' are DERIVED server-side from linked-question performance. UNIQUE per
    (user, target)."""

    __tablename__ = "theory_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "target_type", "target_id", name="uq_theory_progress_target"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    target_type: Mapped[TheoryTargetType] = mapped_column(
        Enum(TheoryTargetType, native_enum=False, length=16), nullable=False
    )
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    state: Mapped[TheoryProgressState] = mapped_column(
        Enum(TheoryProgressState, native_enum=False, length=16),
        default=TheoryProgressState.VIEWED,
        nullable=False,
    )

    user: Mapped[User] = relationship()


class TheoryFavorite(TimestampMixin, Base):
    """Saved sign/rule/lesson/marking/gesture. UNIQUE per (user, target)."""

    __tablename__ = "theory_favorites"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "target_type", "target_id", name="uq_theory_favorite_target"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    target_type: Mapped[TheoryTargetType] = mapped_column(
        Enum(TheoryTargetType, native_enum=False, length=16), nullable=False
    )
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)

    user: Mapped[User] = relationship()


# --------------------------------------------------------------------------- #
# Catalogue entities (docs/spec/15) — structured, searchable, versioned, and
# linked to Rule(s). Each: base identity + immutable version + translation + rule
# link (and, for signs, a question link driving 'Mashq qilish').
# --------------------------------------------------------------------------- #
class RoadSign(TimestampMixin, Base):
    __tablename__ = "road_signs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    official_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    family: Mapped[RoadSignFamily] = mapped_column(
        Enum(RoadSignFamily, native_enum=False, length=32), nullable=False, index=True
    )
    media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("road_sign_versions.id", use_alter=True, name="fk_road_sign_current_version"),
        nullable=True,
    )
    lifecycle_status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )

    current_version: Mapped["RoadSignVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    versions: Mapped[list["RoadSignVersion"]] = relationship(
        back_populates="road_sign",
        foreign_keys="RoadSignVersion.road_sign_id",
        cascade="all, delete-orphan",
    )
    media: Mapped["QuestionMedia | None"] = relationship()
    question_links: Mapped[list["RoadSignQuestionLink"]] = relationship(
        back_populates="road_sign", cascade="all, delete-orphan"
    )


class RoadSignVersion(TimestampMixin, Base):
    __tablename__ = "road_sign_versions"
    __table_args__ = (UniqueConstraint("road_sign_id", "version", name="uq_road_sign_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    road_sign_id: Mapped[str] = mapped_column(
        ForeignKey("road_signs.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )
    media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    authored_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    road_sign: Mapped[RoadSign] = relationship(
        back_populates="versions", foreign_keys=[road_sign_id]
    )
    media: Mapped["QuestionMedia | None"] = relationship()
    translations: Mapped[list["RoadSignTranslation"]] = relationship(
        back_populates="road_sign_version", cascade="all, delete-orphan"
    )
    rule_links: Mapped[list["RoadSignRule"]] = relationship(
        back_populates="road_sign_version", cascade="all, delete-orphan"
    )


class RoadSignTranslation(TimestampMixin, Base):
    __tablename__ = "road_sign_translations"
    __table_args__ = (
        UniqueConstraint("road_sign_version_id", "language", name="uq_road_sign_translation_lang"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    road_sign_version_id: Mapped[str] = mapped_column(
        ForeignKey("road_sign_versions.id"), nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, default="", nullable=False)
    meaning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    driver_action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    important: Mapped[str | None] = mapped_column(Text)
    exam_trap: Mapped[str | None] = mapped_column(Text)
    memory_tip: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[str | None] = mapped_column(Text)

    road_sign_version: Mapped[RoadSignVersion] = relationship(back_populates="translations")


class RoadSignRule(TimestampMixin, Base):
    __tablename__ = "road_sign_rules"
    __table_args__ = (
        UniqueConstraint("road_sign_version_id", "rule_id", name="uq_road_sign_rule"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    road_sign_version_id: Mapped[str] = mapped_column(
        ForeignKey("road_sign_versions.id"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)

    road_sign_version: Mapped[RoadSignVersion] = relationship(back_populates="rule_links")
    rule: Mapped[Rule] = relationship()


class RoadSignQuestionLink(TimestampMixin, Base):
    __tablename__ = "road_sign_question_links"
    __table_args__ = (
        UniqueConstraint("road_sign_id", "question_id", name="uq_road_sign_question"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    road_sign_id: Mapped[str] = mapped_column(
        ForeignKey("road_signs.id"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id"), nullable=False, index=True
    )

    road_sign: Mapped[RoadSign] = relationship(back_populates="question_links")
    question: Mapped[Question] = relationship()


class RoadMarking(TimestampMixin, Base):
    __tablename__ = "road_markings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str | None] = mapped_column(String(32), index=True)
    marking_group: Mapped[RoadMarkingGroup] = mapped_column(
        Enum(RoadMarkingGroup, native_enum=False, length=16), nullable=False, index=True
    )
    media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "road_marking_versions.id", use_alter=True, name="fk_road_marking_current_version"
        ),
        nullable=True,
    )
    lifecycle_status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )

    current_version: Mapped["RoadMarkingVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    versions: Mapped[list["RoadMarkingVersion"]] = relationship(
        back_populates="road_marking",
        foreign_keys="RoadMarkingVersion.road_marking_id",
        cascade="all, delete-orphan",
    )
    media: Mapped["QuestionMedia | None"] = relationship()


class RoadMarkingVersion(TimestampMixin, Base):
    __tablename__ = "road_marking_versions"
    __table_args__ = (
        UniqueConstraint("road_marking_id", "version", name="uq_road_marking_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    road_marking_id: Mapped[str] = mapped_column(
        ForeignKey("road_markings.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )
    media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    authored_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    road_marking: Mapped[RoadMarking] = relationship(
        back_populates="versions", foreign_keys=[road_marking_id]
    )
    media: Mapped["QuestionMedia | None"] = relationship()
    translations: Mapped[list["RoadMarkingTranslation"]] = relationship(
        back_populates="road_marking_version", cascade="all, delete-orphan"
    )
    rule_links: Mapped[list["RoadMarkingRule"]] = relationship(
        back_populates="road_marking_version", cascade="all, delete-orphan"
    )


class RoadMarkingTranslation(TimestampMixin, Base):
    __tablename__ = "road_marking_translations"
    __table_args__ = (
        UniqueConstraint(
            "road_marking_version_id", "language", name="uq_road_marking_translation_lang"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    road_marking_version_id: Mapped[str] = mapped_column(
        ForeignKey("road_marking_versions.id"), nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, default="", nullable=False)
    meaning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    can_cross: Mapped[str | None] = mapped_column(Text)
    can_stop_park: Mapped[str | None] = mapped_column(Text)
    conflict_rule: Mapped[str | None] = mapped_column(Text)
    exam_trap: Mapped[str | None] = mapped_column(Text)
    memory_tip: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[str | None] = mapped_column(Text)

    road_marking_version: Mapped[RoadMarkingVersion] = relationship(back_populates="translations")


class RoadMarkingRule(TimestampMixin, Base):
    __tablename__ = "road_marking_rules"
    __table_args__ = (
        UniqueConstraint("road_marking_version_id", "rule_id", name="uq_road_marking_rule"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    road_marking_version_id: Mapped[str] = mapped_column(
        ForeignKey("road_marking_versions.id"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)

    road_marking_version: Mapped[RoadMarkingVersion] = relationship(back_populates="rule_links")
    rule: Mapped[Rule] = relationship()


class ControllerGesture(TimestampMixin, Base):
    __tablename__ = "controller_gestures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str | None] = mapped_column(String(32), index=True)
    media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    animation_media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "controller_gesture_versions.id",
            use_alter=True,
            name="fk_controller_gesture_current_version",
        ),
        nullable=True,
    )
    lifecycle_status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )

    current_version: Mapped["ControllerGestureVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    versions: Mapped[list["ControllerGestureVersion"]] = relationship(
        back_populates="gesture",
        foreign_keys="ControllerGestureVersion.gesture_id",
        cascade="all, delete-orphan",
    )
    media: Mapped["QuestionMedia | None"] = relationship(foreign_keys=[media_id])
    animation_media: Mapped["QuestionMedia | None"] = relationship(
        foreign_keys=[animation_media_id]
    )


class ControllerGestureVersion(TimestampMixin, Base):
    __tablename__ = "controller_gesture_versions"
    __table_args__ = (
        UniqueConstraint("gesture_id", "version", name="uq_controller_gesture_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    gesture_id: Mapped[str] = mapped_column(
        ForeignKey("controller_gestures.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )
    media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    animation_media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    authored_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    gesture: Mapped[ControllerGesture] = relationship(
        back_populates="versions", foreign_keys=[gesture_id]
    )
    media: Mapped["QuestionMedia | None"] = relationship(foreign_keys=[media_id])
    animation_media: Mapped["QuestionMedia | None"] = relationship(
        foreign_keys=[animation_media_id]
    )
    translations: Mapped[list["ControllerGestureTranslation"]] = relationship(
        back_populates="gesture_version", cascade="all, delete-orphan"
    )
    rule_links: Mapped[list["ControllerGestureRule"]] = relationship(
        back_populates="gesture_version", cascade="all, delete-orphan"
    )


class ControllerGestureTranslation(TimestampMixin, Base):
    __tablename__ = "controller_gesture_translations"
    __table_args__ = (
        UniqueConstraint(
            "gesture_version_id", "language", name="uq_controller_gesture_translation_lang"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    gesture_version_id: Mapped[str] = mapped_column(
        ForeignKey("controller_gesture_versions.id"), nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, default="", nullable=False)
    position_desc: Mapped[str] = mapped_column(Text, default="", nullable=False)
    allowed: Mapped[str] = mapped_column(Text, default="", nullable=False)
    forbidden: Mapped[str] = mapped_column(Text, default="", nullable=False)
    memory_tip: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[str | None] = mapped_column(Text)

    gesture_version: Mapped[ControllerGestureVersion] = relationship(back_populates="translations")


class ControllerGestureRule(TimestampMixin, Base):
    __tablename__ = "controller_gesture_rules"
    __table_args__ = (
        UniqueConstraint("gesture_version_id", "rule_id", name="uq_controller_gesture_rule"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    gesture_version_id: Mapped[str] = mapped_column(
        ForeignKey("controller_gesture_versions.id"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)

    gesture_version: Mapped[ControllerGestureVersion] = relationship(back_populates="rule_links")
    rule: Mapped[Rule] = relationship()


class TrafficLightState(TimestampMixin, Base):
    __tablename__ = "traffic_light_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[TrafficLightKind] = mapped_column(
        Enum(TrafficLightKind, native_enum=False, length=32), nullable=False, index=True
    )
    media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "traffic_light_state_versions.id",
            use_alter=True,
            name="fk_traffic_light_current_version",
        ),
        nullable=True,
    )
    lifecycle_status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )

    current_version: Mapped["TrafficLightStateVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    versions: Mapped[list["TrafficLightStateVersion"]] = relationship(
        back_populates="light",
        foreign_keys="TrafficLightStateVersion.light_id",
        cascade="all, delete-orphan",
    )
    media: Mapped["QuestionMedia | None"] = relationship()


class TrafficLightStateVersion(TimestampMixin, Base):
    __tablename__ = "traffic_light_state_versions"
    __table_args__ = (
        UniqueConstraint("light_id", "version", name="uq_traffic_light_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    light_id: Mapped[str] = mapped_column(
        ForeignKey("traffic_light_states.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT,
        nullable=False,
    )
    media_id: Mapped[str | None] = mapped_column(ForeignKey("question_media.id"))
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    authored_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    light: Mapped[TrafficLightState] = relationship(
        back_populates="versions", foreign_keys=[light_id]
    )
    media: Mapped["QuestionMedia | None"] = relationship()
    translations: Mapped[list["TrafficLightStateTranslation"]] = relationship(
        back_populates="light_version", cascade="all, delete-orphan"
    )
    rule_links: Mapped[list["TrafficLightStateRule"]] = relationship(
        back_populates="light_version", cascade="all, delete-orphan"
    )


class TrafficLightStateTranslation(TimestampMixin, Base):
    __tablename__ = "traffic_light_state_translations"
    __table_args__ = (
        UniqueConstraint(
            "light_version_id", "language", name="uq_traffic_light_translation_lang"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    light_version_id: Mapped[str] = mapped_column(
        ForeignKey("traffic_light_state_versions.id"), nullable=False, index=True
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, native_enum=False, length=8), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    meaning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    movement_permitted: Mapped[str | None] = mapped_column(Text)
    direction_permitted: Mapped[str | None] = mapped_column(Text)
    exceptions: Mapped[str | None] = mapped_column(Text)
    typical_exam_situation: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[str | None] = mapped_column(Text)

    light_version: Mapped[TrafficLightStateVersion] = relationship(back_populates="translations")


class TrafficLightStateRule(TimestampMixin, Base):
    __tablename__ = "traffic_light_state_rules"
    __table_args__ = (
        UniqueConstraint("light_version_id", "rule_id", name="uq_traffic_light_rule"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    light_version_id: Mapped[str] = mapped_column(
        ForeignKey("traffic_light_state_versions.id"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)

    light_version: Mapped[TrafficLightStateVersion] = relationship(back_populates="rule_links")
    rule: Mapped[Rule] = relationship()


# --------------------------------------------------------------------------- #
# Training assessments (docs/spec/20 Phase 7). Separate from the official
# MockTemplate/MockAttempt system; ExamConfig is never touched by these.
# --------------------------------------------------------------------------- #
class Assessment(TimestampMixin, Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    type: Mapped["AssessmentType"] = mapped_column(
        Enum(AssessmentType, native_enum=False, length=32), nullable=False
    )
    status: Mapped["AssessmentStatus"] = mapped_column(
        Enum(AssessmentStatus, native_enum=False, length=16),
        default=AssessmentStatus.DRAFT, nullable=False, index=True,
    )
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assessment_versions.id", use_alter=True, name="fk_assessment_current_version"),
        nullable=True,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    current_version: Mapped["AssessmentVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    versions: Mapped[list["AssessmentVersion"]] = relationship(
        back_populates="assessment", foreign_keys="AssessmentVersion.assessment_id",
        cascade="all, delete-orphan",
    )


class AssessmentVersion(TimestampMixin, Base):
    __tablename__ = "assessment_versions"
    __table_args__ = (UniqueConstraint("assessment_id", "version", name="uq_assessment_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    selection_mode: Mapped["AssessmentSelectionMode"] = mapped_column(
        Enum(AssessmentSelectionMode, native_enum=False, length=16), nullable=False
    )
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer)
    pass_correct: Mapped[int | None] = mapped_column(Integer)
    show_explanations_after: Mapped["AssessmentRevealMode"] = mapped_column(
        Enum(AssessmentRevealMode, native_enum=False, length=16),
        default=AssessmentRevealMode.EACH_ANSWER, nullable=False,
    )
    topic_filters_json: Mapped[dict | None] = mapped_column(JSON)
    difficulty_filters_json: Mapped[dict | None] = mapped_column(JSON)
    randomize_order: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped["VersionStatus"] = mapped_column(
        Enum(VersionStatus, native_enum=False, length=32),
        default=VersionStatus.DRAFT, nullable=False,
    )
    authored_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assessment: Mapped[Assessment] = relationship(
        back_populates="versions", foreign_keys=[assessment_id]
    )
    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        back_populates="assessment_version", cascade="all, delete-orphan",
        order_by="AssessmentQuestion.position",
    )


class AssessmentQuestion(TimestampMixin, Base):
    __tablename__ = "assessment_questions"
    __table_args__ = (
        UniqueConstraint("assessment_version_id", "question_id", name="uq_assessment_q_question"),
        UniqueConstraint("assessment_version_id", "position", name="uq_assessment_q_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_versions.id"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    assessment_version: Mapped[AssessmentVersion] = relationship(back_populates="questions")


class AssessmentAttempt(TimestampMixin, Base):
    __tablename__ = "assessment_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    assessment_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_versions.id"), nullable=False, index=True
    )
    status: Mapped["AssessmentAttemptStatus"] = mapped_column(
        Enum(AssessmentAttemptStatus, native_enum=False, length=16),
        default=AssessmentAttemptStatus.IN_PROGRESS, nullable=False, index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed: Mapped[bool | None] = mapped_column(Boolean)

    questions: Mapped[list["AssessmentAttemptQuestion"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan",
        order_by="AssessmentAttemptQuestion.position",
    )
    answers: Mapped[list["AssessmentAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan",
    )


class AssessmentAttemptQuestion(TimestampMixin, Base):
    __tablename__ = "assessment_attempt_questions"
    __table_args__ = (
        UniqueConstraint("assessment_attempt_id", "question_version_id", name="uq_aaq_version"),
        UniqueConstraint("assessment_attempt_id", "position", name="uq_aaq_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.id"), nullable=False, index=True
    )
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    attempt: Mapped[AssessmentAttempt] = relationship(back_populates="questions")


class AssessmentAnswer(TimestampMixin, Base):
    __tablename__ = "assessment_answers"
    __table_args__ = (
        UniqueConstraint("assessment_attempt_id", "question_version_id", name="uq_aa_answer_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.id"), nullable=False, index=True
    )
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False
    )
    selected_option_id: Mapped[str | None] = mapped_column(ForeignKey("answer_options.id"))
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    attempt: Mapped[AssessmentAttempt] = relationship(back_populates="answers")
