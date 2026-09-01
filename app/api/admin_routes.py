"""Admin studio API (docs/spec/08). EVERY endpoint enforces a role server-side via
``require_role``; hiding frontend routes is not a control. Every mutating action is
audited (in the service layer)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.admin_deps import require_role
from app.api.admin_schemas import (
    DuplicateCheckIn,
    ImportIn,
    QuestionIn,
    ReportResolveIn,
    RoleAssignIn,
    RuleCreateIn,
    RuleSupersedeIn,
    RuleTranslationIn,
)
from app.api.deps import DbSession
from app.domain.enums import AdminRole, Category, RuleStatus, Topic
from app.domain.models import User
from app.services import (
    admin_dashboard,
    authoring,
    bulk_import,
    duplicates,
    qa,
    reports,
    rules_admin,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/api/admin")

AuthorUser = Annotated[User, Depends(require_role(AdminRole.CONTENT_AUTHOR))]
ReviewerUser = Annotated[User, Depends(require_role(AdminRole.CONTENT_REVIEWER))]
AdminUserDep = Annotated[User, Depends(require_role(AdminRole.ADMIN))]
SuperadminUser = Annotated[User, Depends(require_role(AdminRole.SUPERADMIN))]


def _parse_topic(value: str) -> Topic:
    try:
        return Topic(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum mavzu") from exc


def _to_content(payload: QuestionIn) -> authoring.QuestionContentInput:
    return authoring.QuestionContentInput(
        category=Category(payload.category),
        topic=_parse_topic(payload.topic),
        prompt=payload.prompt,
        short_explanation=payload.short_explanation,
        options=[
            authoring.OptionInput(text=o.text, explanation=o.explanation, is_correct=o.is_correct)
            for o in payload.options
        ],
        rule_codes=list(payload.rule_codes),
        subtopic=payload.subtopic,
        is_sign_question=payload.is_sign_question,
        difficulty=payload.difficulty,
        ai_assisted=payload.ai_assisted,
        media_id=payload.media_id,
        sources=[
            authoring.SourceInput(url=s.url, note=s.note, kind=s.kind) for s in payload.sources
        ],
    )


def _version_out(version) -> dict:
    return {
        "id": version.id,
        "question_id": version.question_id,
        "version": version.version,
        "status": version.status.value,
        "difficulty": version.difficulty,
        "ai_assisted": version.ai_assisted,
        "media_id": version.media_id,
        "authored_by_user_id": version.authored_by_user_id,
        "reviewed_by_user_id": version.reviewed_by_user_id,
        "approved_by_user_id": version.approved_by_user_id,
    }


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("/overview")
def overview(user: ReviewerUser, db: DbSession) -> dict:
    return admin_dashboard.build_overview(db)


# --------------------------------------------------------------------------- #
# Question authoring
# --------------------------------------------------------------------------- #
@router.get("/questions")
def list_questions(
    user: AuthorUser,
    db: DbSession,
    q: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    has_media: bool | None = Query(default=None),
    is_sign: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return authoring.list_questions(
        db,
        q=q,
        topic=topic,
        status_filter=status_filter,
        has_media=has_media,
        is_sign=is_sign,
        limit=limit,
        offset=offset,
    )


@router.post("/questions", status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionIn, user: AuthorUser, db: DbSession) -> dict:
    try:
        version = authoring.create_question(db, user, _to_content(payload))
    except authoring.AuthoringError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _version_out(version)


@router.put("/questions/{question_id}")
def edit_question(question_id: str, payload: QuestionIn, user: AuthorUser, db: DbSession) -> dict:
    try:
        version = authoring.edit_question(db, user, question_id, _to_content(payload))
    except authoring.AuthoringError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _version_out(version)


@router.post("/questions/{question_id}/archive")
def archive_question(question_id: str, user: AdminUserDep, db: DbSession) -> dict:
    question = authoring.archive_question(db, user, question_id)
    return {"id": question.id, "lifecycle_status": question.lifecycle_status.value}


@router.post("/versions/{version_id}/submit-review")
def submit_review(version_id: str, user: AuthorUser, db: DbSession) -> dict:
    return _version_out(authoring.submit_for_review(db, user, version_id))


@router.post("/versions/{version_id}/review")
def review_version(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(authoring.mark_reviewed(db, user, version_id))


@router.post("/versions/{version_id}/publish")
def publish_version(version_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return _version_out(authoring.publish_version(db, user, version_id))


@router.get("/questions/{question_id}/qa")
def question_qa(question_id: str, user: ReviewerUser, db: DbSession) -> dict:
    return qa.build_qa(db, question_id)


@router.post("/duplicates/check")
def duplicate_check(payload: DuplicateCheckIn, user: AuthorUser, db: DbSession) -> dict:
    hits = duplicates.find_duplicates(
        db,
        prompt=payload.prompt,
        option_texts=payload.option_texts,
        exclude_question_id=payload.exclude_question_id,
    )
    return {"duplicates": hits}


# --------------------------------------------------------------------------- #
# Rule catalog + searchable picker
# --------------------------------------------------------------------------- #
@router.get("/rules")
def list_rules(user: AuthorUser, db: DbSession, q: str | None = Query(default=None)) -> dict:
    return {"rules": rules_admin.search_rules(db, q)}


@router.post("/rules", status_code=status.HTTP_201_CREATED)
def create_rule(payload: RuleCreateIn, user: AdminUserDep, db: DbSession) -> dict:
    rule = rules_admin.create_rule(
        db,
        user,
        code=payload.code,
        text=payload.text,
        title=payload.title,
        source_url=payload.source_url,
        source_document=payload.source_document,
        verified_at=payload.verified_at,
    )
    return rules_admin.rule_out(db, rule)


@router.put("/rules/{rule_id}")
def edit_rule(rule_id: str, payload: RuleTranslationIn, user: AdminUserDep, db: DbSession) -> dict:
    rule = rules_admin.update_rule_translation(db, user, rule_id, text=payload.text, title=payload.title)
    return rules_admin.rule_out(db, rule)


@router.post("/rules/{rule_id}/supersede")
def supersede_rule(rule_id: str, payload: RuleSupersedeIn, user: AdminUserDep, db: DbSession) -> dict:
    return rules_admin.supersede_rule(
        db, user, rule_id, new_status=RuleStatus(payload.new_status)
    )


# --------------------------------------------------------------------------- #
# Reports queue
# --------------------------------------------------------------------------- #
@router.get("/reports")
def report_queue(user: ReviewerUser, db: DbSession, status_filter: str | None = Query(default=None, alias="status")) -> dict:
    return {"reports": reports.list_reports(db, status_filter=status_filter)}


@router.post("/reports/{report_id}/resolve")
def resolve_report(report_id: str, payload: ReportResolveIn, user: ReviewerUser, db: DbSession) -> dict:
    report = reports.resolve_report(db, user, report_id, action=payload.action, note=payload.note)
    return {"id": report.id, "status": report.status.value}


# --------------------------------------------------------------------------- #
# Bulk import (preview + validate; never auto-publish)
# --------------------------------------------------------------------------- #
@router.post("/import")
def import_content(payload: ImportIn, user: AdminUserDep, db: DbSession) -> dict:
    try:
        return bulk_import.run_import(
            db, user, content=payload.content, fmt=payload.format, commit=payload.commit
        )
    except bulk_import.ImportParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# --------------------------------------------------------------------------- #
# Role management (superadmin only; a user can never set their own role via a body)
# --------------------------------------------------------------------------- #
@router.post("/users/{user_id}/role")
def assign_role(user_id: str, payload: RoleAssignIn, user: SuperadminUser, db: DbSession) -> dict:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foydalanuvchi topilmadi")
    target.admin_role = AdminRole(payload.role) if payload.role else None
    record_audit(
        db, user, "user.assign_role", "user", target.id,
        detail={"role": payload.role},
    )
    db.commit()
    return {"user_id": target.id, "admin_role": target.admin_role.value if target.admin_role else None}
