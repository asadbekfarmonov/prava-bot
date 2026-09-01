"""Assistive duplicate detection (docs/spec/08). NEVER auto-deletes; only hints.

- Normalized exact match (whitespace/case/punctuation-insensitive on prompt + option set).
- Option-set Jaccard similarity on normalized option texts.
(Semantic/embedding similarity is optional and skipped in v1 — it would need network.)
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import Language, VersionStatus
from app.domain.models import (
    AnswerOption,
    AnswerOptionTranslation,
    Question,
    QuestionVersion,
    QuestionVersionTranslation,
)

_LANG = Language.UZ
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+", re.UNICODE)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.casefold()
    text = _PUNCT.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text


def _option_texts(db: Session, version_id: str) -> list[str]:
    rows = db.scalars(
        select(AnswerOptionTranslation.text)
        .join(AnswerOption, AnswerOption.id == AnswerOptionTranslation.answer_option_id)
        .where(
            AnswerOption.question_version_id == version_id,
            AnswerOptionTranslation.language == _LANG,
        )
    )
    return [r for r in rows]


def _normalized_option_set(texts: list[str]) -> frozenset[str]:
    return frozenset(normalize_text(t) for t in texts if t and t.strip())


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def find_duplicates(
    db: Session,
    *,
    prompt: str,
    option_texts: list[str],
    exclude_question_id: str | None = None,
    jaccard_threshold: float = 0.8,
    limit: int = 10,
) -> list[dict]:
    """Return candidate duplicates (exact and/or high-Jaccard). Assistive hint only."""
    norm_prompt = normalize_text(prompt)
    norm_opts = _normalized_option_set(option_texts)

    candidates: list[dict] = []
    # Compare against current (non-archived) versions of other questions.
    versions = db.scalars(
        select(QuestionVersion).where(
            QuestionVersion.status.in_(
                [
                    VersionStatus.DRAFT,
                    VersionStatus.NEEDS_REVIEW,
                    VersionStatus.REVIEWED,
                    VersionStatus.PUBLISHED,
                    VersionStatus.NEEDS_REVERIFICATION,
                ]
            )
        )
    )
    seen_questions: set[str] = set()
    for version in versions:
        question = db.get(Question, version.question_id)
        if question is None:
            continue
        if exclude_question_id and question.id == exclude_question_id:
            continue
        if question.id in seen_questions:
            continue
        tr = db.scalar(
            select(QuestionVersionTranslation).where(
                QuestionVersionTranslation.question_version_id == version.id,
                QuestionVersionTranslation.language == _LANG,
            )
        )
        cand_prompt = normalize_text(tr.prompt) if tr else ""
        cand_opts = _normalized_option_set(_option_texts(db, version.id))

        exact = cand_prompt == norm_prompt and cand_opts == norm_opts and bool(norm_prompt)
        similarity = _jaccard(norm_opts, cand_opts)
        if exact or similarity >= jaccard_threshold:
            seen_questions.add(question.id)
            candidates.append(
                {
                    "question_id": question.id,
                    "question_version_id": version.id,
                    "prompt": tr.prompt if tr else "",
                    "exact_match": exact,
                    "option_jaccard": round(similarity, 3),
                }
            )
        if len(candidates) >= limit:
            break
    candidates.sort(key=lambda c: (not c["exact_match"], -c["option_jaccard"]))
    return candidates
