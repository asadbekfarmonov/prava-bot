"""One validated ingestion path: ContentSource drafts -> published QuestionVersion.

Every content source (manual authoring, CSV/JSON import, licensed-bank importer)
funnels through here so publish validation is enforced identically regardless of
source (docs/spec/06 explanation-quality standard, docs/spec/11 ingestion abstraction).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import Language, VersionStatus
from app.domain.exam_config import ANSWER_OPTIONS_MAX, ANSWER_OPTIONS_MIN
from app.domain.models import (
    AnswerOption,
    AnswerOptionTranslation,
    Question,
    QuestionVersion,
    QuestionVersionRule,
    QuestionVersionSource,
    QuestionVersionTranslation,
    Rule,
    RuleTranslation,
    User,
)
from app.services.content_source import ContentSource, QuestionDraft, RuleDraft


class ContentValidationError(ValueError):
    pass


def _validate_draft(draft: QuestionDraft) -> None:
    n = len(draft.options)
    if not (ANSWER_OPTIONS_MIN <= n <= ANSWER_OPTIONS_MAX):
        raise ContentValidationError(
            f"Question must have {ANSWER_OPTIONS_MIN}-{ANSWER_OPTIONS_MAX} options, got {n}."
        )
    correct = [o for o in draft.options if o.is_correct]
    if len(correct) != 1:
        raise ContentValidationError("Exactly one option must be correct.")
    for o in draft.options:
        if not o.text.strip():
            raise ContentValidationError("Option text must not be empty.")
        if not o.explanation.strip():
            raise ContentValidationError("Every option requires an explanation (no empty explanations).")
    if not draft.prompt.strip():
        raise ContentValidationError("Prompt must not be empty.")
    if not draft.short_explanation.strip():
        raise ContentValidationError("A short 'remember this' explanation is required.")
    if not draft.rule_code.strip():
        raise ContentValidationError("A linked rule is required for publish.")


def upsert_rule(db: Session, draft: RuleDraft) -> Rule:
    rule = db.scalar(select(Rule).where(Rule.code == draft.code))
    if rule is None:
        rule = Rule(code=draft.code)
        db.add(rule)
    rule.source_url = draft.source_url
    rule.source_document = draft.source_document
    rule.verified_at = draft.verified_at
    rule.version = draft.version
    db.flush()
    existing = db.scalar(
        select(RuleTranslation).where(
            RuleTranslation.rule_id == rule.id, RuleTranslation.language == draft.language
        )
    )
    if existing is None:
        db.add(
            RuleTranslation(
                rule_id=rule.id, language=draft.language, title=draft.title, text=draft.text
            )
        )
    else:
        existing.title = draft.title
        existing.text = draft.text
    db.flush()
    return rule


def publish_question(db: Session, draft: QuestionDraft, author: User) -> Question:
    """Validate a draft and persist it as a published (immutable) version 1.

    Returns the ``Question`` container with ``current_version_id`` pointing at the
    published version. Rules must already exist (call :func:`upsert_rule` first).
    """
    _validate_draft(draft)

    rule = db.scalar(select(Rule).where(Rule.code == draft.rule_code))
    if rule is None:
        raise ContentValidationError(f"Rule {draft.rule_code!r} not found; ingest rules first.")

    now = datetime.now(timezone.utc)

    question = Question(
        category=draft.category,
        topic=draft.topic,
        subtopic=draft.subtopic,
        is_sign_question=draft.is_sign_question,
        lifecycle_status=VersionStatus.PUBLISHED,
        created_by_user_id=author.id,
    )
    db.add(question)
    db.flush()

    version = QuestionVersion(
        question_id=question.id,
        version=1,
        status=VersionStatus.PUBLISHED,
        difficulty=draft.difficulty,
        ai_assisted=draft.ai_assisted,
        authored_by_user_id=author.id,
        reviewed_by_user_id=author.id,
        approved_by_user_id=author.id,
        published_at=now,
        verified_at=now,
    )
    db.add(version)
    db.flush()

    db.add(
        QuestionVersionTranslation(
            question_version_id=version.id,
            language=draft.language,
            prompt=draft.prompt,
            short_explanation=draft.short_explanation,
        )
    )

    for position, opt in enumerate(draft.options, start=1):
        option = AnswerOption(
            question_version_id=version.id, position=position, is_correct=opt.is_correct
        )
        db.add(option)
        db.flush()
        db.add(
            AnswerOptionTranslation(
                answer_option_id=option.id,
                language=opt.language,
                text=opt.text,
                explanation=opt.explanation,
            )
        )

    db.add(
        QuestionVersionRule(
            question_version_id=version.id, rule_id=rule.id, rule_version=rule.version
        )
    )

    for src in draft.sources:
        db.add(
            QuestionVersionSource(
                question_version_id=version.id, url=src.url, note=src.note, kind=src.kind
            )
        )

    question.current_version_id = version.id
    db.flush()
    return question


def ingest_source(db: Session, source: ContentSource, author: User) -> int:
    """Ingest every rule + question from a ContentSource. Returns #questions published."""
    for rule_draft in source.rules():
        upsert_rule(db, rule_draft)
    count = 0
    for q_draft in source.questions():
        publish_question(db, q_draft, author)
        count += 1
    db.commit()
    return count
