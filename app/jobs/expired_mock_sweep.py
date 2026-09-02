"""Railway Cron job: expired-mock sweep (cleanup/backstop only — every 15 min).

Correctness is NEVER dependent on this job. The authoritative rule is request-time:
every endpoint touching an in-progress attempt runs ``mock.finalize_if_expired`` first
(docs/spec/05 "Mock timer & integrity", docs/spec/13 "Mock expiry on Railway"). This
sweep only finalizes attempts that expired and were then never reopened.

Idempotent: ``finalize_if_expired`` no-ops on already-completed attempts, so running
this repeatedly is safe. Grading logic is NOT duplicated here — we reuse the service.

Run:  python -m app.jobs.expired_mock_sweep
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import MockStatus
from app.domain.models import MockAttempt
from app.observability.logging import configure_logging, log_event
from app.services import mock
from app.storage.db import session_scope


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run(db: Session) -> dict:
    """Finalize every in-progress attempt whose deadline has passed. Returns a summary."""
    now = _now()
    attempts = list(
        db.scalars(select(MockAttempt).where(MockAttempt.status == MockStatus.IN_PROGRESS))
    )
    scanned = len(attempts)
    finalized = 0
    for attempt in attempts:
        before = attempt.status
        # Reuse the single grading authority; it grades as of expires_at, not "now",
        # so a late sweep cannot extend or alter the deadline.
        mock.finalize_if_expired(db, attempt)
        if before == MockStatus.IN_PROGRESS and attempt.status == MockStatus.COMPLETED:
            finalized += 1
    summary = {"scanned_in_progress": scanned, "finalized": finalized}
    log_event("expired_mock_sweep_completed", **summary)
    return summary


def main() -> dict:
    configure_logging()
    with session_scope() as db:
        return run(db)


if __name__ == "__main__":
    main()
