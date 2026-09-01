import pytest

from app.domain.enums import Topic
from app.services.content_source import OptionDraft, QuestionDraft
from app.services.content_sources.seed import SeedContentSource
from app.services.ingestion import ContentValidationError, _validate_draft
from tests.seed_helper import seed_demo_bank


def test_seed_covers_all_15_topics_and_publishes(client):
    n = seed_demo_bank()
    assert n >= 15
    source = SeedContentSource()
    topics = {q.topic for q in source.questions()}
    assert topics == set(Topic)  # all 15 topics represented

    # Every demo question: 2-4 options, exactly one correct, per-option explanations,
    # a linked rule, a short_explanation, and marked as demo (ai_assisted).
    for q in source.questions():
        assert 2 <= len(q.options) <= 4
        assert sum(o.is_correct for o in q.options) == 1
        assert all(o.explanation.strip() for o in q.options)
        assert q.rule_code
        assert q.short_explanation.strip()
        assert q.ai_assisted is True


def test_ingestion_rejects_zero_correct():
    from app.domain.enums import Category

    draft = QuestionDraft(
        category=Category.B,
        topic=Topic.GENERAL_RULES,
        prompt="p",
        short_explanation="s",
        rule_code="YHQ:2.1",
        options=[
            OptionDraft(text="a", is_correct=False, explanation="e"),
            OptionDraft(text="b", is_correct=False, explanation="e"),
        ],
    )
    with pytest.raises(ContentValidationError):
        _validate_draft(draft)


def test_ingestion_rejects_empty_explanation():
    from app.domain.enums import Category

    draft = QuestionDraft(
        category=Category.B,
        topic=Topic.GENERAL_RULES,
        prompt="p",
        short_explanation="s",
        rule_code="YHQ:2.1",
        options=[
            OptionDraft(text="a", is_correct=True, explanation=""),
            OptionDraft(text="b", is_correct=False, explanation="e"),
        ],
    )
    with pytest.raises(ContentValidationError):
        _validate_draft(draft)
