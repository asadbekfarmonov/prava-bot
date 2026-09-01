"""Admin dashboard summary (docs/spec/08 admin dashboard)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import ReportStatus, Topic, VersionStatus
from app.domain.models import (
    ContentReport,
    Question,
    QuestionMedia,
    QuestionVersion,
)

# Topics where a visual is usually expected (docs/spec/08 coverage hint).
_MEDIA_LIKELY_TOPICS = {Topic.ROAD_SIGNS, Topic.INTERSECTIONS, Topic.ROAD_MARKINGS}
_STALE_MONTHS = 6


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def build_overview(db: Session) -> dict:
    status_counts: dict[str, int] = {}
    for st in VersionStatus:
        status_counts[st.value] = _count(
            db, select(func.count(Question.id)).where(Question.lifecycle_status == st)
        )

    # Stale: published questions whose current version lacks a recent verified_at.
    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=_STALE_MONTHS * 30)
    stale = 0
    published_questions = db.scalars(
        select(Question).where(Question.lifecycle_status == VersionStatus.PUBLISHED)
    )
    coverage: dict[str, int] = {t.value: 0 for t in Topic}
    missing_media_where_likely: list[str] = []
    for q in published_questions:
        coverage[q.topic.value] = coverage.get(q.topic.value, 0) + 1
        version = db.get(QuestionVersion, q.current_version_id) if q.current_version_id else None
        if version is not None:
            verified = version.verified_at
            if verified is None:
                stale += 1
            else:
                if verified.tzinfo is None:
                    verified = verified.replace(tzinfo=timezone.utc)
                if verified < stale_cutoff:
                    stale += 1
            if q.topic in _MEDIA_LIKELY_TOPICS and version.media_id is None:
                missing_media_where_likely.append(q.id)

    open_reports = _count(
        db,
        select(func.count(ContentReport.id)).where(
            ContentReport.status.in_([ReportStatus.OPEN, ReportStatus.TRIAGED])
        ),
    )

    media_count = _count(db, select(func.count(QuestionMedia.id)))
    media_bytes = int(db.scalar(select(func.coalesce(func.sum(QuestionMedia.byte_size), 0))) or 0)

    return {
        "counts": {
            "published": status_counts.get(VersionStatus.PUBLISHED.value, 0),
            "draft": status_counts.get(VersionStatus.DRAFT.value, 0),
            "needs_review": status_counts.get(VersionStatus.NEEDS_REVIEW.value, 0),
            "reviewed": status_counts.get(VersionStatus.REVIEWED.value, 0),
            "needs_reverification": status_counts.get(VersionStatus.NEEDS_REVERIFICATION.value, 0),
            "superseded": status_counts.get(VersionStatus.SUPERSEDED.value, 0),
            "archived": status_counts.get(VersionStatus.ARCHIVED.value, 0),
            "stale": stale,
        },
        "topic_coverage": coverage,
        "questions_without_media_where_likely_needed": missing_media_where_likely,
        "open_reports": open_reports,
        "media_storage": {"object_count": media_count, "total_bytes": media_bytes},
    }
