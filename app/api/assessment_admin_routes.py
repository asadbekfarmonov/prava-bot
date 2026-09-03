from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.admin_deps import require_role
from app.api.deps import DbSession
from app.domain.enums import AdminRole, AssessmentStatus
from app.domain.models import Assessment, User
from app.services import assessments as svc
from app.services.assessments import AssessmentError
from app.services.audit import record_audit

AuthorUser = Annotated[User, Depends(require_role(AdminRole.CONTENT_AUTHOR))]
ReviewerUser = Annotated[User, Depends(require_role(AdminRole.CONTENT_REVIEWER))]
AdminUser = Annotated[User, Depends(require_role(AdminRole.ADMIN))]

router = APIRouter(prefix="/api/admin/assessments", tags=["admin-assessments"])


class AssessmentCreateIn(BaseModel):
    type: str
    title: str
    description: str | None = None


class AssessmentUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    selection_mode: str | None = None
    time_limit_seconds: int | None = None
    pass_correct: int | None = None
    show_explanations_after: str | None = None
    randomize_order: bool | None = None
    topic_filters: list[str] | None = None
    difficulty_filters: list[int] | None = None
    question_count: int | None = None
    question_ids: list[str] | None = None

    model_config = {"extra": "ignore"}


def _422(exc: AssessmentError):
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("")
def list_assessments(user: AuthorUser, db: DbSession) -> dict:
    rows = db.scalars(select(Assessment).order_by(Assessment.created_at.desc())).all()
    return {"assessments": [svc.assessment_admin_out(db, a) for a in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_assessment(payload: AssessmentCreateIn, user: AuthorUser, db: DbSession) -> dict:
    try:
        a = svc.create_assessment(db, user, type=payload.type, title=payload.title, description=payload.description)
    except AssessmentError as exc:
        raise _422(exc)
    record_audit(db, user, "assessment.create", "assessment", a.id, detail={"type": payload.type})
    db.commit()
    return svc.assessment_admin_out(db, a)


@router.get("/{assessment_id}")
def get_assessment(assessment_id: str, user: AuthorUser, db: DbSession) -> dict:
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test topilmadi")
    return svc.assessment_admin_out(db, a)


@router.put("/{assessment_id}")
def update_assessment(assessment_id: str, payload: AssessmentUpdateIn, user: AuthorUser, db: DbSession) -> dict:
    try:
        svc.update_assessment(db, user, assessment_id, payload.model_dump(exclude_unset=True))
    except AssessmentError as exc:
        raise _422(exc)
    a = db.get(Assessment, assessment_id)
    record_audit(db, user, "assessment.update", "assessment", assessment_id)
    db.commit()
    return svc.assessment_admin_out(db, a)


@router.get("/{assessment_id}/eligible-count")
def eligible_count(assessment_id: str, user: AuthorUser, db: DbSession) -> dict:
    a = db.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test topilmadi")
    version = svc._latest_version(db, a)
    count = svc.eligible_count(db, version) if version else 0
    return {"eligible_count": count, "question_count": version.question_count if version else 0}


@router.post("/{assessment_id}/publish")
def publish_assessment(assessment_id: str, user: ReviewerUser, db: DbSession) -> dict:
    try:
        a = svc.publish_assessment(db, user, assessment_id)
    except AssessmentError as exc:
        raise _422(exc)
    record_audit(db, user, "assessment.publish", "assessment", assessment_id)
    db.commit()
    return svc.assessment_admin_out(db, a)


@router.delete("/{assessment_id}")
def delete_assessment(assessment_id: str, user: AdminUser, db: DbSession) -> dict:
    a = svc.archive_assessment(db, user, assessment_id)
    record_audit(db, user, "assessment.archive", "assessment", assessment_id)
    db.commit()
    return {"id": a.id, "status": AssessmentStatus.ARCHIVED.value}
