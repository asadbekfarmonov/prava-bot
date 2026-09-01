"""Bulk import (docs/spec/08 bulk operations).

CSV/JSON -> preview + validation -> commit. Imported rows land as DRAFT versions and
NEVER auto-publish. Invalid rows are REJECTED with reasons (not silently skipped).
"""

from __future__ import annotations

import csv
import io
import json

from sqlalchemy.orm import Session

from app.domain.enums import Category, Topic
from app.domain.exam_config import ANSWER_OPTIONS_MAX, ANSWER_OPTIONS_MIN
from app.domain.models import Rule, User
from app.services.audit import record_audit
from app.services.authoring import (
    OptionInput,
    QuestionContentInput,
    SourceInput,
    create_question,
)
from sqlalchemy import select


class ImportParseError(ValueError):
    pass


def parse_rows(content: str, fmt: str) -> list[dict]:
    fmt = (fmt or "").lower()
    if fmt == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ImportParseError(f"JSON parse xatosi: {exc}") from exc
        if isinstance(data, dict) and "rows" in data:
            data = data["rows"]
        if not isinstance(data, list):
            raise ImportParseError("JSON ildizi ro'yxat bo'lishi kerak.")
        return data
    if fmt == "csv":
        rows: list[dict] = []
        reader = csv.DictReader(io.StringIO(content))
        for raw in reader:
            options = []
            for i in range(1, ANSWER_OPTIONS_MAX + 1):
                text = (raw.get(f"option{i}") or "").strip()
                if not text:
                    continue
                options.append(
                    {
                        "text": text,
                        "explanation": (raw.get(f"explanation{i}") or "").strip(),
                        "is_correct": str(raw.get("correct_index", "")).strip() == str(i),
                    }
                )
            rows.append(
                {
                    "external_id": (raw.get("external_id") or "").strip() or None,
                    "category": (raw.get("category") or "B").strip(),
                    "topic": (raw.get("topic") or "").strip(),
                    "prompt": (raw.get("prompt") or "").strip(),
                    "short_explanation": (raw.get("short_explanation") or "").strip(),
                    "difficulty": int(raw["difficulty"]) if (raw.get("difficulty") or "").strip() else 1,
                    "rule_codes": [c.strip() for c in (raw.get("rule_code") or "").split(";") if c.strip()],
                    "options": options,
                }
            )
        return rows
    raise ImportParseError("Qo'llab-quvvatlanmaydigan format (json yoki csv).")


def _validate_row(db: Session, row: dict) -> tuple[QuestionContentInput | None, list[str]]:
    errors: list[str] = []
    try:
        category = Category(row.get("category", "B"))
    except (ValueError, TypeError):
        category = None
        errors.append(f"Noto'g'ri kategoriya: {row.get('category')!r}")
    try:
        topic = Topic(row.get("topic"))
    except (ValueError, TypeError):
        topic = None
        errors.append(f"Noto'g'ri mavzu: {row.get('topic')!r}")

    prompt = (row.get("prompt") or "").strip()
    if not prompt:
        errors.append("Savol matni bo'sh.")
    short_explanation = (row.get("short_explanation") or "").strip()
    if not short_explanation:
        errors.append("Qisqa izoh bo'sh.")

    raw_options = row.get("options") or []
    if not (ANSWER_OPTIONS_MIN <= len(raw_options) <= ANSWER_OPTIONS_MAX):
        errors.append(f"Variantlar soni {ANSWER_OPTIONS_MIN}-{ANSWER_OPTIONS_MAX} bo'lishi kerak.")
    options: list[OptionInput] = []
    correct = 0
    for o in raw_options:
        text = (o.get("text") or "").strip()
        expl = (o.get("explanation") or "").strip()
        is_correct = bool(o.get("is_correct"))
        if not text:
            errors.append("Variant matni bo'sh.")
        if not expl:
            errors.append("Variant izohi bo'sh.")
        if is_correct:
            correct += 1
        options.append(OptionInput(text=text, explanation=expl, is_correct=is_correct))
    if correct != 1:
        errors.append("Aynan bitta to'g'ri variant bo'lishi kerak.")

    rule_codes = row.get("rule_codes") or ([row["rule_code"]] if row.get("rule_code") else [])
    if not rule_codes:
        errors.append("Kamida bitta qoida kodi kerak.")
    for code in rule_codes:
        if db.scalar(select(Rule).where(Rule.code == code)) is None:
            errors.append(f"Qoida topilmadi: {code}")

    if errors or category is None or topic is None:
        return None, errors

    sources = [SourceInput(url=s.get("url", ""), note=s.get("note"), kind=s.get("kind", "reference"))
               for s in (row.get("sources") or [])]
    data = QuestionContentInput(
        category=category,
        topic=topic,
        prompt=prompt,
        short_explanation=short_explanation,
        options=options,
        rule_codes=list(rule_codes),
        subtopic=row.get("subtopic"),
        is_sign_question=bool(row.get("is_sign_question", False)),
        difficulty=int(row.get("difficulty", 1) or 1),
        ai_assisted=bool(row.get("ai_assisted", False)),
        sources=sources,
    )
    return data, []


def run_import(
    db: Session, author: User, *, content: str, fmt: str, commit: bool
) -> dict:
    """Preview (commit=False) or commit (commit=True). Valid rows land as DRAFT."""
    rows = parse_rows(content, fmt)
    valid: list[QuestionContentInput] = []
    row_results: list[dict] = []
    for index, row in enumerate(rows):
        data, errors = _validate_row(db, row)
        row_results.append(
            {
                "index": index,
                "external_id": row.get("external_id"),
                "valid": not errors,
                "errors": errors,
            }
        )
        if data is not None and not errors:
            valid.append(data)

    created_ids: list[str] = []
    if commit:
        for data in valid:
            version = create_question(db, author, data)  # lands as DRAFT
            created_ids.append(version.id)
        record_audit(
            db, author, "content.import", "import", None,
            detail={"created": len(created_ids), "rejected": len(rows) - len(valid), "fmt": fmt},
        )
        db.commit()

    return {
        "total_rows": len(rows),
        "valid_rows": len(valid),
        "rejected_rows": len(rows) - len(valid),
        "committed": commit,
        "created_version_ids": created_ids,
        "rows": row_results,
    }
