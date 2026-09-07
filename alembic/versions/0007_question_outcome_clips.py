"""per-question animated outcome clips (success/fail media on question_versions)

Adds two nullable FK columns to ``question_versions`` pointing at ``question_media``:
``success_media_id`` and ``fail_media_id``. Per-version (immutable) so historical
attempts keep their pinned clips. Revealed only post-answer (practice result / mock
review) — never in any pre-answer or live payload (docs/spec/09 no-answer-leak).

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-07 18:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("question_versions") as batch:
        batch.add_column(sa.Column("success_media_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("fail_media_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_qv_success_media", "question_media", ["success_media_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_qv_fail_media", "question_media", ["fail_media_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("question_versions") as batch:
        batch.drop_constraint("fk_qv_fail_media", type_="foreignkey")
        batch.drop_constraint("fk_qv_success_media", type_="foreignkey")
        batch.drop_column("fail_media_id")
        batch.drop_column("success_media_id")
