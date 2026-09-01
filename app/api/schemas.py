from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

# v1 is category B + Uzbek only; schema is translation/category ready.
CategoryValue = Literal["B"]
LanguageValue = Literal["uz"]


class TelegramLoginRequest(BaseModel):
    init_data: str


class DevLoginRequest(BaseModel):
    telegram_id: int = 1001
    username: str | None = "dev_student"
    first_name: str | None = "Dev"
    last_name: str | None = "Student"


class ProfileIn(BaseModel):
    """Minimal onboarding. Strict schema: unknown fields (e.g. admin_role) are ignored."""

    model_config = {"extra": "ignore"}

    display_name: str = Field(min_length=1, max_length=255)
    category: CategoryValue = "B"
    language: LanguageValue = "uz"
    target_exam_date: date | None = None
    daily_goal: int | None = Field(default=None, ge=1, le=200)
    timezone: str = "Asia/Tashkent"
    ranking_name: str | None = Field(default=None, max_length=255)
    show_on_ranking: bool = True


class PracticeSessionIn(BaseModel):
    model_config = {"extra": "ignore"}
    topic: str | None = None


class PracticeAnswerIn(BaseModel):
    model_config = {"extra": "ignore"}

    practice_session_id: str
    question_id: str
    selected_option_id: str | None = None
    time_spent_seconds: int | None = Field(default=None, ge=0)


class MockAnswerIn(BaseModel):
    """Autosave one mock answer. Strict: client-supplied is_correct/correct_count/
    passed (mass-assignment) are ignored; grading is server-side only."""

    model_config = {"extra": "ignore"}

    question_version_id: str
    selected_option_id: str | None = None
    marked_for_review: bool = False
