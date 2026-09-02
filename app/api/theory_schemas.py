"""Strict input schemas for Theory endpoints (mass-assignment protection). No schema
accepts a progress 'mastered' state or admin_role from the client body."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Progress input: the client can only mark a target 'viewed' (opening). 'practised' and
# 'mastered' are DERIVED server-side from question performance — never client-settable.
_TargetType = Literal["section", "article", "sign", "marking", "gesture", "light", "rule"]


class ProgressIn(BaseModel):
    model_config = {"extra": "ignore"}
    target_type: _TargetType
    target_id: str = Field(min_length=1, max_length=64)


class FavoriteIn(BaseModel):
    model_config = {"extra": "ignore"}
    target_type: _TargetType
    target_id: str = Field(min_length=1, max_length=64)


class TheoryPracticeStartIn(BaseModel):
    model_config = {"extra": "ignore"}
    target_type: Literal["article", "sign"]
    target_id: str = Field(min_length=1, max_length=64)


class TheoryReportIn(BaseModel):
    model_config = {"extra": "ignore"}
    target_type: _TargetType
    target_id: str = Field(min_length=1, max_length=64)
    reason: Literal[
        "wrong_answer", "unclear_explanation", "image_problem", "outdated_rule", "typo", "other"
    ]
    note: str | None = Field(default=None, max_length=2000)


# --------------------------------------------------------------------------- #
# Admin Theory studio input schemas (role-gated at the route layer). No schema ever
# accepts admin_role / lifecycle status forcing — publish goes through the workflow.
# --------------------------------------------------------------------------- #
class SectionCreateIn(BaseModel):
    model_config = {"extra": "ignore"}
    slug: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=500)
    subtitle: str = Field(default="", max_length=1000)
    topic: str | None = Field(default=None, max_length=48)
    position: int = Field(default=0, ge=0, le=100000)
    icon_media_id: str | None = None


class SectionTranslationIn(BaseModel):
    model_config = {"extra": "ignore"}
    language: str = Field(default="uz", max_length=8)
    title: str = Field(min_length=1, max_length=500)
    subtitle: str = Field(default="", max_length=1000)


class ArticleCreateIn(BaseModel):
    model_config = {"extra": "ignore"}
    section_id: str
    slug: str = Field(min_length=1, max_length=160)
    kind: Literal["lesson", "reference", "quick_ref", "common_mistake"] = "lesson"
    position: int = Field(default=0, ge=0, le=100000)


class BlockIn(BaseModel):
    model_config = {"extra": "ignore"}
    type: Literal[
        "text", "rule_callout", "image", "animation", "diagram", "comparison",
        "warning", "memory_tip", "table", "example", "practice_link",
    ]
    body: str = Field(default="", max_length=8000)
    media_id: str | None = None
    rule_code: str | None = Field(default=None, max_length=64)
    ref_question_id: str | None = None
    data: dict | None = None


class ArticleContentIn(BaseModel):
    model_config = {"extra": "ignore"}
    title: str = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=2000)
    hero_media_id: str | None = None
    ai_assisted: bool = False
    blocks: list[BlockIn] = Field(default_factory=list, max_length=100)
    rule_codes: list[str] = Field(default_factory=list, max_length=30)
    question_ids: list[str] = Field(default_factory=list, max_length=100)


class SignCreateIn(BaseModel):
    model_config = {"extra": "ignore"}
    official_code: str = Field(min_length=1, max_length=32)
    family: Literal[
        "warning", "priority", "prohibitory", "mandatory", "information", "service",
        "additional_plate",
    ]
    media_id: str | None = None
    position: int = Field(default=0, ge=0, le=100000)


class SignContentIn(BaseModel):
    model_config = {"extra": "ignore"}
    name: str = Field(default="", max_length=500)
    meaning: str = Field(default="", max_length=4000)
    driver_action: str = Field(default="", max_length=4000)
    important: str | None = Field(default=None, max_length=4000)
    exam_trap: str | None = Field(default=None, max_length=4000)
    memory_tip: str | None = Field(default=None, max_length=4000)
    keywords: str | None = Field(default=None, max_length=2000)
    media_id: str | None = None
    ai_assisted: bool = False
    rule_codes: list[str] = Field(default_factory=list, max_length=30)
    question_ids: list[str] = Field(default_factory=list, max_length=100)


class MarkingCreateIn(BaseModel):
    model_config = {"extra": "ignore"}
    group: Literal["horizontal", "vertical", "temporary"]
    code: str | None = Field(default=None, max_length=32)
    media_id: str | None = None
    position: int = Field(default=0, ge=0, le=100000)


class MarkingContentIn(BaseModel):
    model_config = {"extra": "ignore"}
    name: str = Field(default="", max_length=500)
    meaning: str = Field(default="", max_length=4000)
    can_cross: str | None = Field(default=None, max_length=2000)
    can_stop_park: str | None = Field(default=None, max_length=2000)
    conflict_rule: str | None = Field(default=None, max_length=2000)
    exam_trap: str | None = Field(default=None, max_length=4000)
    memory_tip: str | None = Field(default=None, max_length=4000)
    keywords: str | None = Field(default=None, max_length=2000)
    media_id: str | None = None
    ai_assisted: bool = False
    rule_codes: list[str] = Field(default_factory=list, max_length=30)


class GestureCreateIn(BaseModel):
    model_config = {"extra": "ignore"}
    code: str | None = Field(default=None, max_length=32)
    media_id: str | None = None
    animation_media_id: str | None = None
    position: int = Field(default=0, ge=0, le=100000)


class GestureContentIn(BaseModel):
    model_config = {"extra": "ignore"}
    name: str = Field(default="", max_length=500)
    position_desc: str = Field(default="", max_length=4000)
    allowed: str = Field(default="", max_length=4000)
    forbidden: str = Field(default="", max_length=4000)
    memory_tip: str | None = Field(default=None, max_length=4000)
    keywords: str | None = Field(default=None, max_length=2000)
    media_id: str | None = None
    animation_media_id: str | None = None
    ai_assisted: bool = False
    rule_codes: list[str] = Field(default_factory=list, max_length=30)


class LightCreateIn(BaseModel):
    model_config = {"extra": "ignore"}
    kind: Literal["main", "arrow_section", "flashing", "pedestrian", "railway", "special"]
    media_id: str | None = None
    position: int = Field(default=0, ge=0, le=100000)


class LightContentIn(BaseModel):
    model_config = {"extra": "ignore"}
    title: str = Field(default="", max_length=500)
    meaning: str = Field(default="", max_length=4000)
    movement_permitted: str | None = Field(default=None, max_length=2000)
    direction_permitted: str | None = Field(default=None, max_length=2000)
    exceptions: str | None = Field(default=None, max_length=2000)
    typical_exam_situation: str | None = Field(default=None, max_length=4000)
    keywords: str | None = Field(default=None, max_length=2000)
    media_id: str | None = None
    ai_assisted: bool = False
    rule_codes: list[str] = Field(default_factory=list, max_length=30)
