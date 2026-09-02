"""Railway Cron job: orphan-media cleanup (cleanup only — daily).

Deletes ``QuestionMedia`` rows + their storage objects that are NOT referenced by any
question version, and only after a 30-day grace period (docs/spec/13 "Backups &
retention", docs/spec/09 "Object storage"). Referenced media is NEVER hard-deleted.

Grace period: media is immutable/content-addressed and rows are created at upload time;
we use ``created_at`` as a conservative floor for "how long it has existed unreferenced",
so freshly-uploaded media that has not yet been attached to a version is not reaped.
(A precise ``dereferenced_at`` timestamp could tighten this later; using ``created_at``
only ever waits longer, never shorter — it can never delete something too early.)

Storage is accessed only through the ``MediaStorage`` port, so tests inject the
in-memory fake and never touch the network. Idempotent: once rows/objects are gone a
re-run finds nothing.

Run:  python -m app.jobs.orphan_media_cleanup
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import QuestionMedia, QuestionVersion
from app.observability.logging import configure_logging, log_event
from app.storage.db import session_scope
from app.storage.media_storage import MediaStorage, get_media_storage

GRACE_PERIOD_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def run(db: Session, storage: MediaStorage | None = None, *, now: datetime | None = None) -> dict:
    """Delete unreferenced media past the grace period. Returns a summary.

    Never deletes media referenced by any ``QuestionVersion.media_id``.
    """
    storage = storage or get_media_storage()
    now = now or _now()
    cutoff = now - timedelta(days=GRACE_PERIOD_DAYS)

    referenced_ids = set(
        db.scalars(
            select(QuestionVersion.media_id).where(QuestionVersion.media_id.is_not(None))
        )
    )

    all_media = list(db.scalars(select(QuestionMedia)))
    scanned = len(all_media)
    deleted_rows = 0
    deleted_objects = 0
    skipped_referenced = 0
    within_grace = 0

    for media in all_media:
        if media.id in referenced_ids:
            # Never hard-delete media still referenced by a version.
            skipped_referenced += 1
            continue
        if _as_aware(media.created_at) > cutoff:
            # Unreferenced but still inside the 30-day grace window.
            within_grace += 1
            continue
        # Delete storage objects first (best-effort, idempotent), then the DB row.
        for key in (media.storage_key, media.poster_storage_key):
            if key:
                storage.delete(key)
                deleted_objects += 1
        db.delete(media)
        deleted_rows += 1

    db.commit()
    summary = {
        "scanned": scanned,
        "deleted_rows": deleted_rows,
        "deleted_objects": deleted_objects,
        "skipped_referenced": skipped_referenced,
        "within_grace": within_grace,
        "grace_period_days": GRACE_PERIOD_DAYS,
    }
    log_event("orphan_media_cleanup_completed", **summary)
    return summary


def main() -> dict:
    configure_logging()
    # Unit tests call run(db, storage) directly; main() wires the real session + storage.
    with session_scope() as db:
        return run(db)


if __name__ == "__main__":
    main()
