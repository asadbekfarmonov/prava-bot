"""slice7 admin training assessments (docs/spec/20 Phase 7)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-03 21:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = dict(server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        # Circular pointer to the published version; FK added after that table exists.
        sa.Column("current_version_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), **_TS),
        sa.Column("updated_at", sa.DateTime(timezone=True), **_TS),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("slug", name="uq_assessments_slug"),
    )
    op.create_index("ix_assessments_slug", "assessments", ["slug"])
    op.create_index("ix_assessments_status", "assessments", ["status"])

    op.create_table(
        "assessment_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("assessment_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("selection_mode", sa.String(length=16), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=True),
        sa.Column("pass_correct", sa.Integer(), nullable=True),
        sa.Column("show_explanations_after", sa.String(length=16), nullable=False),
        sa.Column("topic_filters_json", sa.JSON(), nullable=True),
        sa.Column("difficulty_filters_json", sa.JSON(), nullable=True),
        sa.Column("randomize_order", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("authored_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), **_TS),
        sa.Column("updated_at", sa.DateTime(timezone=True), **_TS),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"]),
        sa.ForeignKeyConstraint(["authored_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("assessment_id", "version", name="uq_assessment_version"),
    )
    op.create_index("ix_assessment_versions_assessment_id", "assessment_versions", ["assessment_id"])

    op.create_table(
        "assessment_questions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("assessment_version_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), **_TS),
        sa.Column("updated_at", sa.DateTime(timezone=True), **_TS),
        sa.ForeignKeyConstraint(["assessment_version_id"], ["assessment_versions.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.UniqueConstraint("assessment_version_id", "question_id", name="uq_assessment_q_question"),
        sa.UniqueConstraint("assessment_version_id", "position", name="uq_assessment_q_position"),
    )
    op.create_index("ix_assessment_questions_version", "assessment_questions", ["assessment_version_id"])

    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("assessment_version_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), **_TS),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), **_TS),
        sa.Column("updated_at", sa.DateTime(timezone=True), **_TS),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["assessment_version_id"], ["assessment_versions.id"]),
    )
    op.create_index("ix_assessment_attempts_user", "assessment_attempts", ["user_id"])
    op.create_index("ix_assessment_attempts_version", "assessment_attempts", ["assessment_version_id"])
    op.create_index("ix_assessment_attempts_status", "assessment_attempts", ["status"])

    op.create_table(
        "assessment_attempt_questions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("assessment_attempt_id", sa.String(length=36), nullable=False),
        sa.Column("question_version_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), **_TS),
        sa.Column("updated_at", sa.DateTime(timezone=True), **_TS),
        sa.ForeignKeyConstraint(["assessment_attempt_id"], ["assessment_attempts.id"]),
        sa.ForeignKeyConstraint(["question_version_id"], ["question_versions.id"]),
        sa.UniqueConstraint("assessment_attempt_id", "question_version_id", name="uq_aaq_version"),
        sa.UniqueConstraint("assessment_attempt_id", "position", name="uq_aaq_position"),
    )
    op.create_index("ix_aaq_attempt", "assessment_attempt_questions", ["assessment_attempt_id"])

    op.create_table(
        "assessment_answers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("assessment_attempt_id", sa.String(length=36), nullable=False),
        sa.Column("question_version_id", sa.String(length=36), nullable=False),
        sa.Column("selected_option_id", sa.String(length=36), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), **_TS),
        sa.Column("updated_at", sa.DateTime(timezone=True), **_TS),
        sa.ForeignKeyConstraint(["assessment_attempt_id"], ["assessment_attempts.id"]),
        sa.ForeignKeyConstraint(["question_version_id"], ["question_versions.id"]),
        sa.ForeignKeyConstraint(["selected_option_id"], ["answer_options.id"]),
        sa.UniqueConstraint("assessment_attempt_id", "question_version_id", name="uq_aa_answer_version"),
    )
    op.create_index("ix_aa_answer_attempt", "assessment_answers", ["assessment_attempt_id"])

    # Circular FK now that assessment_versions exists.
    with op.batch_alter_table("assessments") as batch:
        batch.create_foreign_key(
            "fk_assessment_current_version", "assessment_versions", ["current_version_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("assessments") as batch:
        batch.drop_constraint("fk_assessment_current_version", type_="foreignkey")
    op.drop_table("assessment_answers")
    op.drop_table("assessment_attempt_questions")
    op.drop_table("assessment_attempts")
    op.drop_table("assessment_questions")
    op.drop_table("assessment_versions")
    op.drop_table("assessments")
