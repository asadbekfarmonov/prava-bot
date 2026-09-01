from __future__ import annotations

from app.domain.enums import AdminRole
from app.domain.models import User
from app.services.content_sources.seed import SeedContentSource
from app.services.ingestion import ingest_source
from app.storage.db import session_scope


def seed_demo_bank() -> int:
    with session_scope() as db:
        author = User(telegram_id="0", first_name="Seed", admin_role=AdminRole.CONTENT_AUTHOR)
        db.add(author)
        db.flush()
        return ingest_source(db, SeedContentSource(), author)
