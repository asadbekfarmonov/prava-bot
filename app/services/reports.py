"""Content reports (docs/spec/02, 08): user-filed reports keyed to the EXACT
question_version_id, plus the admin resolve/reject queue."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ReportReason, ReportStatus
from app.domain.models import ContentReport, QuestionVersion, User
from app.services.audit import record_audit


def create_report(
    db: Session, user: User, *, question_version_id: str, reason: str, note: str | None
) -> ContentReport:
    if db.get(QuestionVersion, question_version_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol versiyasi topilmadi")
    try:
        reason_enum = ReportReason(reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noto'g'ri sabab") from exc

    report = ContentReport(
        user_id=user.id,
        question_version_id=question_version_id,
        reason=reason_enum,
        note=note,
        status=ReportStatus.OPEN,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def create_theory_report(
    db: Session, user: User, *, target_type: str, target_id: str, reason: str, note: str | None
) -> ContentReport:
    """Theory-content report (docs/spec/14) keyed by target_type + target_id. Reuses the
    same ContentReport queue (question_version_id stays NULL for theory reports)."""
    from app.domain.enums import TheoryTargetType

    try:
        tt = TheoryTargetType(target_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum nishon turi") from exc
    try:
        reason_enum = ReportReason(reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noto'g'ri sabab") from exc

    report = ContentReport(
        user_id=user.id,
        question_version_id=None,
        theory_target_type=tt.value,
        theory_target_id=target_id,
        reason=reason_enum,
        note=note,
        status=ReportStatus.OPEN,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def _report_out(report: ContentReport) -> dict:
    return {
        "id": report.id,
        "question_version_id": report.question_version_id,
        "theory_target_type": report.theory_target_type,
        "theory_target_id": report.theory_target_id,
        "reason": report.reason.value,
        "note": report.note,
        "status": report.status.value,
        "user_id": report.user_id,
        "resolved_by_user_id": report.resolved_by_user_id,
        "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def list_reports(db: Session, *, status_filter: str | None = None, limit: int = 100) -> list[dict]:
    limit = max(1, min(limit, 200))
    stmt = select(ContentReport)
    if status_filter:
        try:
            stmt = stmt.where(ContentReport.status == ReportStatus(status_filter))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noto'g'ri holat") from exc
    stmt = stmt.order_by(ContentReport.created_at.desc()).limit(limit)
    return [_report_out(r) for r in db.scalars(stmt)]


def resolve_report(
    db: Session, resolver: User, report_id: str, *, action: str, note: str | None = None
) -> ContentReport:
    report = db.get(ContentReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hisobot topilmadi")
    if action == "resolve":
        report.status = ReportStatus.RESOLVED
    elif action == "reject":
        report.status = ReportStatus.REJECTED
    elif action == "triage":
        report.status = ReportStatus.TRIAGED
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noto'g'ri amal")
    if action in ("resolve", "reject"):
        report.resolved_by_user_id = resolver.id
        report.resolved_at = datetime.now(timezone.utc)
    if note:
        report.note = (report.note + "\n---\n" + note) if report.note else note
    record_audit(
        db, resolver, f"report.{action}", "content_report", report.id,
        detail={"status": report.status.value},
    )
    db.commit()
    db.refresh(report)
    return report
