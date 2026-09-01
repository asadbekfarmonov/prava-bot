"""Strict input schemas for admin endpoints (mass-assignment protection).

Admin authoring legitimately sets ``is_correct`` on options, but no admin schema ever
accepts ``admin_role`` from a content body — role changes go only through the
superadmin role-assignment endpoint.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

CategoryValue = Literal["B"]


class OptionIn(BaseModel):
    model_config = {"extra": "ignore"}
    text: str = Field(min_length=1, max_length=2000)
    explanation: str = Field(default="", max_length=4000)
    is_correct: bool = False


class SourceIn(BaseModel):
    model_config = {"extra": "ignore"}
    url: str = Field(default="", max_length=1000)
    note: str | None = Field(default=None, max_length=2000)
    kind: str = "reference"


class QuestionIn(BaseModel):
    model_config = {"extra": "ignore"}
    category: CategoryValue = "B"
    topic: str
    prompt: str = Field(default="", max_length=4000)
    short_explanation: str = Field(default="", max_length=4000)
    options: list[OptionIn] = Field(min_length=1, max_length=5)
    rule_codes: list[str] = Field(default_factory=list, max_length=20)
    subtopic: str | None = Field(default=None, max_length=255)
    is_sign_question: bool = False
    difficulty: int = Field(default=1, ge=1, le=3)
    ai_assisted: bool = False
    media_id: str | None = None
    sources: list[SourceIn] = Field(default_factory=list, max_length=20)


class RuleCreateIn(BaseModel):
    model_config = {"extra": "ignore"}
    code: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=8000)
    title: str | None = Field(default=None, max_length=500)
    source_url: str = Field(default="", max_length=1000)
    source_document: str | None = Field(default=None, max_length=255)
    verified_at: date | None = None


class RuleTranslationIn(BaseModel):
    model_config = {"extra": "ignore"}
    text: str = Field(min_length=1, max_length=8000)
    title: str | None = Field(default=None, max_length=500)


class RuleSupersedeIn(BaseModel):
    model_config = {"extra": "ignore"}
    new_status: Literal["superseded", "repealed"] = "superseded"


class ReportIn(BaseModel):
    model_config = {"extra": "ignore"}
    question_version_id: str
    reason: Literal[
        "wrong_answer", "unclear_explanation", "image_problem", "outdated_rule", "typo", "other"
    ]
    note: str | None = Field(default=None, max_length=2000)


class ReportResolveIn(BaseModel):
    model_config = {"extra": "ignore"}
    action: Literal["resolve", "reject", "triage"]
    note: str | None = Field(default=None, max_length=2000)


class RoleAssignIn(BaseModel):
    model_config = {"extra": "ignore"}
    role: Literal["content_author", "content_reviewer", "admin", "superadmin"] | None = None


class ImportIn(BaseModel):
    model_config = {"extra": "ignore"}
    format: Literal["json", "csv"]
    content: str = Field(max_length=5_000_000)
    commit: bool = False


class DuplicateCheckIn(BaseModel):
    model_config = {"extra": "ignore"}
    prompt: str = ""
    option_texts: list[str] = Field(default_factory=list)
    exclude_question_id: str | None = None
