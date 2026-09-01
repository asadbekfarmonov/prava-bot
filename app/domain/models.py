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
    AdminRole,
    Category,
    Language,
    MediaType,
    MockStatus,
    PracticeSource,
    ReportReason,
    ReportStatus,
    RuleStatus,
    SourceKind,
    Topic,
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
    # The EXACT version the reporter saw (never the mutable container).
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
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
