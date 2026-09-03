from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CompletedOnboardingUser, DbSession
from app.domain.enums import AssessmentAttemptStatus, AssessmentRevealMode, AssessmentStatus
from app.domain.models import Assessment, AssessmentAttempt, AssessmentVersion
from app.services import assessments as svc
from app.services.assessments import AssessmentError

router = APIRouter(prefix="/api", tags=["assessments"])


class AnswerIn(BaseModel):
    question_version_id: str
    selected_option_id: str | None = None


def _422(exc: AssessmentError):
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/assessments")
def list_published(user: CompletedOnboardingUser, db: DbSession) -> dict:
    rows = db.scalars(select(Assessment).where(Assessment.status == AssessmentStatus.PUBLISHED)).all()
    out = []
    for a in rows:
        if a.current_version_id is None:
            continue
        v = db.get(AssessmentVersion, a.current_version_id)
        if v:
            out.append(svc.assessment_public_out(a, v))
    return {"assessments": out}


@router.get("/assessments/{slug}")
def get_published(slug: str, user: CompletedOnboardingUser, db: DbSession) -> dict:
    a = db.scalar(select(Assessment).where(Assessment.slug == slug))
    if a is None or a.status != AssessmentStatus.PUBLISHED or a.current_version_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test topilmadi")
    v = db.get(AssessmentVersion, a.current_version_id)
    return svc.assessment_public_out(a, v)


@router.post("/assessments/{slug}/attempts", status_code=status.HTTP_201_CREATED)
def start_attempt(slug: str, user: CompletedOnboardingUser, db: DbSession) -> dict:
    try:
        attempt = svc.start_attempt(db, user, slug)
    except AssessmentError as exc:
        raise _422(exc)
    db.commit()
    return svc.attempt_out(db, attempt, reveal=False)


@router.get("/assessment-attempts/{attempt_id}")
def get_attempt(attempt_id: str, user: CompletedOnboardingUser, db: DbSession) -> dict:
    attempt = svc._load_attempt(db, user, attempt_id)
    # Live attempt never reveals correctness/explanations (docs/spec/20 Phase 7).
    return svc.attempt_out(db, attempt, reveal=False)


@router.post("/assessment-attempts/{attempt_id}/answers")
def answer(attempt_id: str, payload: AnswerIn, user: CompletedOnboardingUser, db: DbSession) -> dict:
    try:
        ans = svc.submit_answer(db, user, attempt_id, payload.question_version_id, payload.selected_option_id)
    except AssessmentError as exc:
        raise _422(exc)
    attempt = svc._load_attempt(db, user, attempt_id)
    version = db.get(AssessmentVersion, attempt.assessment_version_id)
    reveal_each = version and version.show_explanations_after == AssessmentRevealMode.EACH_ANSWER
    db.commit()
    return {
        "question_version_id": ans.question_version_id,
        "selected_option_id": ans.selected_option_id,
        # Per-answer correctness only when the assessment reveals after each answer.
        "is_correct": ans.is_correct if reveal_each else None,
    }


@router.post("/assessment-attempts/{attempt_id}/submit")
def submit(attempt_id: str, user: CompletedOnboardingUser, db: DbSession) -> dict:
    attempt = svc.submit_attempt(db, user, attempt_id)
    db.commit()
    return svc.attempt_out(db, attempt, reveal=True)


@router.get("/assessment-attempts/{attempt_id}/review")
def review(attempt_id: str, user: CompletedOnboardingUser, db: DbSession) -> dict:
    attempt = svc._load_attempt(db, user, attempt_id)
    if attempt.status != AssessmentAttemptStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Urinish yakunlanmagan")
    return svc.attempt_out(db, attempt, reveal=True)
