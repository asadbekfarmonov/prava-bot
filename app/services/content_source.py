"""Content ingestion abstraction (docs/spec/11 — content-source-agnostic build).

All content enters through ONE validated path into ``Question`` + immutable
``QuestionVersion``. The choice of source (original/demo authoring, CSV/JSON import,
or a future licensed-bank importer) must not change the application architecture — it
only changes which rows a ``ContentSource`` yields. Every source funnels through the
same publish validation in ``app/services/ingestion.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

from app.domain.enums import Category, Language, SourceKind, Topic


@dataclass(frozen=True)
class RuleDraft:
    code: str
    text: str
    title: str | None = None
    source_url: str = ""
    source_document: str | None = None
    verified_at: date | None = None
    version: int = 1
    language: Language = Language.UZ


@dataclass(frozen=True)
class OptionDraft:
    text: str
    is_correct: bool
    explanation: str
    language: Language = Language.UZ


@dataclass(frozen=True)
class SourceRefDraft:
    url: str = ""
    note: str | None = None
    kind: SourceKind = SourceKind.REFERENCE


@dataclass(frozen=True)
class QuestionDraft:
    category: Category
    topic: Topic
    prompt: str
    short_explanation: str
    options: list[OptionDraft]
    rule_code: str
    is_sign_question: bool = False
    difficulty: int = 1
    subtopic: str | None = None
    ai_assisted: bool = False
    language: Language = Language.UZ
    sources: list[SourceRefDraft] = field(default_factory=list)


class ContentSource(ABC):
    """A replaceable adapter that yields validated-shape drafts for ingestion."""

    name: str = "abstract"

    @abstractmethod
    def rules(self) -> list[RuleDraft]:
        """Rules referenced by the questions this source produces."""

    @abstractmethod
    def questions(self) -> list[QuestionDraft]:
        """The question drafts to ingest (all land as DRAFT then published)."""
