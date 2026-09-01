"""Admin Rule catalog: CRUD, searchable picker, and rule-change propagation
(docs/spec/02 rule-change propagation, 08 rule picker)."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.enums import Language, RuleStatus, VersionStatus
from app.domain.models import (
    Rule,
    RuleTranslation,
    QuestionVersion,
    QuestionVersionRule,
    User,
)
from app.services.audit import record_audit

_LANG = Language.UZ


def _uz_translation(db: Session, rule_id: str) -> RuleTranslation | None:
    return db.scalar(
        select(RuleTranslation).where(
            RuleTranslation.rule_id == rule_id, RuleTranslation.language == _LANG
        )
    )


def rule_out(db: Session, rule: Rule) -> dict:
    tr = _uz_translation(db, rule.id)
    return {
        "id": rule.id,
        "code": rule.code,
        "title": tr.title if tr else None,
        "text": tr.text if tr else "",
        "version": rule.version,
        "source_url": rule.source_url,
        "source_document": rule.source_document,
        "status": rule.status.value,
        "verified_at": rule.verified_at.isoformat() if rule.verified_at else None,
    }


def search_rules(db: Session, q: str | None, limit: int = 50) -> list[dict]:
    """Searchable picker: match on code and uz title/text. Flags superseded rules."""
    limit = max(1, min(limit, 100))
    stmt = select(Rule)
    if q:
        like = f"%{q.strip()}%"
        stmt = (
            select(Rule)
            .outerjoin(RuleTranslation, RuleTranslation.rule_id == Rule.id)
            .where(
                or_(
                    Rule.code.ilike(like),
                    RuleTranslation.title.ilike(like),
                    RuleTranslation.text.ilike(like),
                )
            )
            .distinct()
        )
    stmt = stmt.order_by(Rule.code).limit(limit)
    return [rule_out(db, r) for r in db.scalars(stmt)]


def create_rule(
    db: Session,
    actor: User,
    *,
    code: str,
    text: str,
    title: str | None = None,
    source_url: str = "",
    source_document: str | None = None,
    verified_at: date | None = None,
) -> Rule:
    if db.scalar(select(Rule).where(Rule.code == code)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu kodli qoida allaqachon mavjud")
    rule = Rule(
        code=code,
        source_url=source_url,
        source_document=source_document,
        verified_at=verified_at,
        version=1,
        status=RuleStatus.ACTIVE,
    )
    db.add(rule)
    db.flush()
    db.add(RuleTranslation(rule_id=rule.id, language=_LANG, title=title, text=text))
    record_audit(db, actor, "rule.create", "rule", rule.id, version=rule.version)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule_translation(
    db: Session, actor: User, rule_id: str, *, text: str, title: str | None = None
) -> Rule:
    """Edit the uz translation text/title of a rule (does not bump the legal version)."""
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Qoida topilmadi")
    tr = _uz_translation(db, rule.id)
    if tr is None:
        db.add(RuleTranslation(rule_id=rule.id, language=_LANG, title=title, text=text))
    else:
        tr.text = text
        tr.title = title
    record_audit(db, actor, "rule.edit", "rule", rule.id, version=rule.version)
    db.commit()
    db.refresh(rule)
    return rule


def supersede_rule(
    db: Session,
    actor: User,
    rule_id: str,
    *,
    new_status: RuleStatus = RuleStatus.SUPERSEDED,
) -> dict:
    """Bump the rule version + change status, then flip every QuestionVersion linked to
    an OLDER rule_version to ``needs_reverification`` (docs/spec/02 propagation)."""
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Qoida topilmadi")

    rule.version = rule.version + 1
    rule.status = new_status
    db.flush()

    # Every version linked to an older rule_version needs re-verification.
    affected_links = list(
        db.scalars(
            select(QuestionVersionRule).where(
                QuestionVersionRule.rule_id == rule.id,
                QuestionVersionRule.rule_version < rule.version,
            )
        )
    )
    flipped: list[str] = []
    for link in affected_links:
        version = db.get(QuestionVersion, link.question_version_id)
        if version is None:
            continue
        if version.status in (VersionStatus.PUBLISHED, VersionStatus.REVIEWED, VersionStatus.NEEDS_REVIEW):
            version.status = VersionStatus.NEEDS_REVERIFICATION
            version.question.lifecycle_status = VersionStatus.NEEDS_REVERIFICATION
            flipped.append(version.id)

    record_audit(
        db, actor, "rule.supersede", "rule", rule.id, version=rule.version,
        detail={"flipped_versions": flipped, "new_status": new_status.value},
    )
    db.commit()
    return {"rule": rule_out(db, rule), "flipped_version_ids": flipped}
