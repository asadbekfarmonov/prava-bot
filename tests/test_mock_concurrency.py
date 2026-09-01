"""Slice 2 — DB-level integrity guard: at most one in-progress mock attempt per user.

Complements the API-level 409 test by proving the partial unique index actually
rejects a second in-progress row (the race the app-level check alone cannot close).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.enums import Category, Language, MockStatus
from app.domain.models import MockAttempt, User
from app.storage.db import get_session_factory
from tests.seed_helper import seed_demo_bank


def _login(client, telegram_id=1001, name="Dilnoza"):
    assert client.post("/api/dev/login", json={"telegram_id": telegram_id, "first_name": name}).status_code == 200


def _onboard(client, name="Dilnoza"):
    assert client.put("/api/profile", json={"display_name": name, "category": "B", "language": "uz"}).status_code == 200


def _make_attempt(user_id: str, status: MockStatus) -> MockAttempt:
    now = datetime.now(timezone.utc)
    return MockAttempt(
        user_id=user_id,
        category=Category.B,
        language=Language.UZ,
        status=status,
        started_at=now,
        expires_at=now + timedelta(seconds=1500),
        exam_config_version=1,
        question_count=20,
        time_limit_seconds=1500,
        pass_correct=18,
    )


def test_partial_unique_index_blocks_second_in_progress_attempt(client):
    seed_demo_bank()
    _login(client)
    _onboard(client)
    sf = get_session_factory()
    with sf() as db:
        user = db.scalar(select(User).where(User.telegram_id == "1001"))
        db.add(_make_attempt(user.id, MockStatus.IN_PROGRESS))
        db.commit()
        # A SECOND in-progress attempt for the same user must violate the index.
        db.add(_make_attempt(user.id, MockStatus.IN_PROGRESS))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_partial_index_allows_new_attempt_after_completion(client):
    seed_demo_bank()
    _login(client)
    _onboard(client)
    sf = get_session_factory()
    with sf() as db:
        user = db.scalar(select(User).where(User.telegram_id == "1001"))
        first = _make_attempt(user.id, MockStatus.IN_PROGRESS)
        db.add(first)
        db.commit()
        # Completing the first frees the partial-unique slot for a new in-progress attempt.
        first.status = MockStatus.COMPLETED
        db.commit()
        db.add(_make_attempt(user.id, MockStatus.IN_PROGRESS))
        db.commit()  # must NOT raise
        count = len(list(db.scalars(select(MockAttempt).where(MockAttempt.user_id == user.id))))
        assert count == 2
