"""Seed the shared question bank with ORIGINAL demo questions.

Usage:
    python -m app.scripts.seed_demo

Idempotent-ish: it creates a dedicated seed author user and only ingests the demo
source if the bank is empty, so re-running does not duplicate the bank.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.domain.enums import AdminRole
from app.domain.models import Question, User
from app.observability.logging import configure_logging, log_event
from app.services.content_sources.seed import SeedContentSource
from app.services.ingestion import ingest_source
from app.storage.db import session_scope

SEED_AUTHOR_TELEGRAM_ID = "0"


def ensure_seed_author(db) -> User:
    author = db.scalar(select(User).where(User.telegram_id == SEED_AUTHOR_TELEGRAM_ID))
    if author is None:
        author = User(
            telegram_id=SEED_AUTHOR_TELEGRAM_ID,
            first_name="Seed",
            last_name="Author",
            admin_role=AdminRole.CONTENT_AUTHOR,
        )
        db.add(author)
        db.flush()
    return author


def run() -> int:
    configure_logging()
    with session_scope() as db:
        existing = db.scalar(select(func.count(Question.id)))
        if existing:
            log_event("seed_demo_skipped", reason="bank_not_empty", questions=existing)
            return existing
        author = ensure_seed_author(db)
        count = ingest_source(db, SeedContentSource(), author)
        log_event("seed_demo_completed", questions=count)
        return count


if __name__ == "__main__":
    n = run()
    print(f"Seeded {n} demo questions.")
