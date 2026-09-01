"""Pre-publish QA (docs/spec/08 pre-publish QA view).

GET /api/admin/questions/{id}/qa returns the consolidated view + an automated
checklist, plus a practice-preview and an exam-preview. The exam-preview reuses the
no-answer-leak principle (docs/spec/09): it exposes only {id, position, text} options
and NO is_correct/explanation/rule.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import Language, RuleStatus, VersionStatus
from app.domain.models import (
    AnswerOption,
    AnswerOptionTranslation,
    ContentReport,
    Question,
    QuestionMedia,
    QuestionVersion,
    QuestionVersionRule,
    QuestionVersionTranslation,
    Rule,
    RuleTranslation,
)
from app.config import get_settings
from app.domain.enums import ReportStatus
from app.services.duplicates import find_duplicates

_LANG = Language.UZ


def _working_version(db: Session, question: Question) -> QuestionVersion | None:
    """The version QA operates on: prefer the highest non-archived version."""
    return db.scalar(
        select(QuestionVersion)
        .where(
            QuestionVersion.question_id == question.id,
            QuestionVersion.status != VersionStatus.ARCHIVED,
        )
        .order_by(QuestionVersion.version.desc())
    )


def _uz(db: Session, version_id: str) -> QuestionVersionTranslation | None:
    return db.scalar(
        select(QuestionVersionTranslation).where(
            QuestionVersionTranslation.question_version_id == version_id,
            QuestionVersionTranslation.language == _LANG,
        )
    )


def _options(db: Session, version_id: str) -> list[AnswerOption]:
    return list(
        db.scalars(
            select(AnswerOption)
            .where(AnswerOption.question_version_id == version_id)
            .order_by(AnswerOption.position)
        )
    )


def _otr(db: Session, option_id: str) -> AnswerOptionTranslation | None:
    return db.scalar(
        select(AnswerOptionTranslation).where(
            AnswerOptionTranslation.answer_option_id == option_id,
            AnswerOptionTranslation.language == _LANG,
        )
    )


def _rules(db: Session, version_id: str) -> list[dict]:
    links = db.scalars(
        select(QuestionVersionRule).where(QuestionVersionRule.question_version_id == version_id)
    )
    out = []
    for link in links:
        rule = db.get(Rule, link.rule_id)
        if rule is None:
            continue
        tr = db.scalar(
            select(RuleTranslation).where(
                RuleTranslation.rule_id == rule.id, RuleTranslation.language == _LANG
            )
        )
        out.append(
            {
                "code": rule.code,
                "title": tr.title if tr else None,
                "text": tr.text if tr else "",
                "source_url": rule.source_url,
                "rule_version": link.rule_version,
                "current_rule_version": rule.version,
                "status": rule.status.value,
                "superseded": rule.status != RuleStatus.ACTIVE or rule.version != link.rule_version,
            }
        )
    return out


def _check(key: str, passed: bool, detail: str = "") -> dict:
    return {"key": key, "passed": bool(passed), "detail": detail}


def build_checklist(db: Session, version: QuestionVersion) -> list[dict]:
    options = _options(db, version.id)
    tr = _uz(db, version.id)
    correct = [o for o in options if o.is_correct]
    settings = get_settings()

    checks: list[dict] = []
    checks.append(_check("exactly_one_correct", len(correct) == 1, "Aynan bitta to'g'ri variant"))
    checks.append(_check("option_count_2_5", 2 <= len(options) <= 5, f"{len(options)} ta variant"))

    rules = _rules(db, version.id)
    has_current_rule = any(not r["superseded"] for r in rules)
    checks.append(_check("current_rule_linked", has_current_rule, "Amaldagi (eskirmagan) qoida bog'langan"))

    all_opt_expl = all((_otr(db, o.id) and _otr(db, o.id).explanation.strip()) for o in options) if options else False
    checks.append(_check("explanation_per_option", all_opt_expl, "Har bir variant izohi"))

    correct_reasoning = bool(correct) and bool(_otr(db, correct[0].id) and _otr(db, correct[0].id).explanation.strip())
    checks.append(_check("correct_answer_reasoning", correct_reasoning, "To'g'ri javob asosi"))

    checks.append(_check("short_explanation_present", bool(tr and tr.short_explanation.strip()), "Qisqa izoh (eslab qoling)"))

    all_opt_text = all((_otr(db, o.id) and _otr(db, o.id).text.strip()) for o in options) if options else False
    uz_complete = bool(tr and tr.prompt.strip()) and all_opt_text and all_opt_expl
    checks.append(_check("uz_translation_complete", uz_complete, "To'liq uz tarjimasi"))

    if version.media_id:
        media = db.get(QuestionMedia, version.media_id)
        media_ok = False
        if media is not None:
            from app.storage.media_storage import get_media_storage

            media_ok = get_media_storage().exists(media.storage_key)
        checks.append(_check("media_accessible", media_ok, "Media obyekt xotirasidan yuklanadi"))
    else:
        checks.append(_check("media_accessible", True, "Media biriktirilmagan (ixtiyoriy)"))

    # No unresolved duplicate.
    dups = find_duplicates(
        db,
        prompt=tr.prompt if tr else "",
        option_texts=[(_otr(db, o.id).text if _otr(db, o.id) else "") for o in options],
        exclude_question_id=version.question_id,
    )
    checks.append(_check("no_unresolved_duplicate", len(dups) == 0, f"{len(dups)} ta shubhali dublikat"))

    # Reviewer approved (and, if configured, reviewer != sole author).
    reviewer_ok = version.reviewed_by_user_id is not None
    if settings.require_second_reviewer:
        reviewer_ok = reviewer_ok and version.reviewed_by_user_id != version.authored_by_user_id
    checks.append(_check("reviewer_approved", reviewer_ok, "Ko'rikchi tasdiqlagan"))

    return checks


def practice_preview(db: Session, version: QuestionVersion) -> dict:
    """Post-answer (practice) rendering: explanations + rule revealed."""
    tr = _uz(db, version.id)
    options = _options(db, version.id)
    correct = next((o for o in options if o.is_correct), None)
    return {
        "question_version_id": version.id,
        "prompt": tr.prompt if tr else "",
        "media_id": version.media_id,
        "short_explanation": tr.short_explanation if tr else "",
        "correct_option_id": correct.id if correct else None,
        "options": [
            {
                "id": o.id,
                "position": o.position,
                "text": (_otr(db, o.id).text if _otr(db, o.id) else ""),
                "is_correct": o.is_correct,
                "explanation": (_otr(db, o.id).explanation if _otr(db, o.id) else ""),
            }
            for o in options
        ],
        "rules": _rules(db, version.id),
    }


def exam_preview(db: Session, version: QuestionVersion) -> dict:
    """Exam-mode rendering with NO answer leak (docs/spec/09): only {id, position,
    text}. NO is_correct / explanation / rule / short_explanation."""
    tr = _uz(db, version.id)
    options = _options(db, version.id)
    return {
        "question_version_id": version.id,
        "prompt": tr.prompt if tr else "",
        "media_id": version.media_id,
        "options": [
            {"id": o.id, "position": o.position, "text": (_otr(db, o.id).text if _otr(db, o.id) else "")}
            for o in options
        ],
    }


def build_qa(db: Session, question_id: str) -> dict:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    version = _working_version(db, question)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Versiya topilmadi")

    checklist = build_checklist(db, version)
    open_reports_count = len(
        list(
            db.scalars(
                select(ContentReport.id).where(
                    ContentReport.question_version_id == version.id,
                    ContentReport.status.in_([ReportStatus.OPEN, ReportStatus.TRIAGED]),
                )
            )
        )
    )

    return {
        "question": {
            "id": question.id,
            "category": question.category.value,
            "topic": question.topic.value,
            "subtopic": question.subtopic,
            "is_sign_question": question.is_sign_question,
            "lifecycle_status": question.lifecycle_status.value,
            "current_version_id": question.current_version_id,
        },
        "version": {
            "id": version.id,
            "version": version.version,
            "status": version.status.value,
            "difficulty": version.difficulty,
            "ai_assisted": version.ai_assisted,
            "authored_by_user_id": version.authored_by_user_id,
            "reviewed_by_user_id": version.reviewed_by_user_id,
            "approved_by_user_id": version.approved_by_user_id,
        },
        "checklist": checklist,
        "all_passed": all(c["passed"] for c in checklist),
        "open_reports": open_reports_count,
        "practice_preview": practice_preview(db, version),
        "exam_preview": exam_preview(db, version),
    }
