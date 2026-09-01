"""QA reviewer boundary tests (Slice 1).

Closes boundary/validation gaps not covered by the developer suite:
- ingestion option-count boundaries (2 and 5 accepted; 1 and 6 rejected);
- two-correct-options rejected (only zero-correct was tested);
- empty prompt / short_explanation / rule_code rejected;
- production security validator rejects weak SESSION_SECRET and APP_DEBUG=true;
- initData max-age boundary (just-expired rejected; just-within accepted).
"""

import os
import time

import pytest

from app.domain.enums import Category, Topic
from app.services.content_source import OptionDraft, QuestionDraft
from app.services.ingestion import ContentValidationError, _validate_draft


def _opts(n_correct, n_total):
    opts = []
    for i in range(n_total):
        opts.append(
            OptionDraft(text=f"opt{i}", is_correct=(i < n_correct), explanation=f"exp{i}")
        )
    return opts


def _draft(options, prompt="p", short="s", rule="YHQ:2.1"):
    return QuestionDraft(
        category=Category.B,
        topic=Topic.GENERAL_RULES,
        prompt=prompt,
        short_explanation=short,
        rule_code=rule,
        options=options,
    )


# --------------------------------------------------------------------------- #
# Option-count boundaries: 2..5 valid; 1 and 6 invalid (exam_config bounds).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n_total", [2, 3, 4, 5])
def test_option_count_within_bounds_accepted(n_total):
    _validate_draft(_draft(_opts(1, n_total)))  # must not raise


@pytest.mark.parametrize("n_total", [1, 6, 7])
def test_option_count_out_of_bounds_rejected(n_total):
    with pytest.raises(ContentValidationError):
        _validate_draft(_draft(_opts(1, n_total)))


# --------------------------------------------------------------------------- #
# Exactly one correct: zero AND more-than-one both rejected.
# --------------------------------------------------------------------------- #
def test_two_correct_options_rejected():
    with pytest.raises(ContentValidationError):
        _validate_draft(_draft(_opts(2, 4)))


def test_all_correct_options_rejected():
    with pytest.raises(ContentValidationError):
        _validate_draft(_draft(_opts(3, 3)))


# --------------------------------------------------------------------------- #
# Required-field emptiness rejected.
# --------------------------------------------------------------------------- #
def test_empty_prompt_rejected():
    with pytest.raises(ContentValidationError):
        _validate_draft(_draft(_opts(1, 3), prompt="   "))


def test_empty_short_explanation_rejected():
    with pytest.raises(ContentValidationError):
        _validate_draft(_draft(_opts(1, 3), short=""))


def test_missing_rule_rejected():
    with pytest.raises(ContentValidationError):
        _validate_draft(_draft(_opts(1, 3), rule="   "))


def test_empty_option_text_rejected():
    opts = [
        OptionDraft(text="", is_correct=True, explanation="e"),
        OptionDraft(text="b", is_correct=False, explanation="e"),
    ]
    with pytest.raises(ContentValidationError):
        _validate_draft(_draft(opts))


# --------------------------------------------------------------------------- #
# Production security validator (docs/spec/09 secrets & debug hardening).
# --------------------------------------------------------------------------- #
def _reset():
    from app.config.settings import get_settings
    get_settings.cache_clear()


def test_production_rejects_weak_session_secret(tmp_path):
    env_backup = dict(os.environ)
    try:
        os.environ["APP_ENV"] = "production"
        os.environ["APP_DEBUG"] = "false"
        os.environ["SESSION_SECRET"] = "short"  # < 32 chars
        os.environ["MINI_APP_URL"] = "https://app.prava.uz"
        os.environ["BOT_TOKEN"] = "1:tok"
        from app.config.settings import Settings
        with pytest.raises(ValueError):
            Settings()
    finally:
        os.environ.clear()
        os.environ.update(env_backup)
        _reset()


def test_production_rejects_debug_true(tmp_path):
    env_backup = dict(os.environ)
    try:
        os.environ["APP_ENV"] = "production"
        os.environ["APP_DEBUG"] = "true"
        os.environ["SESSION_SECRET"] = "x" * 40
        os.environ["MINI_APP_URL"] = "https://app.prava.uz"
        os.environ["BOT_TOKEN"] = "1:tok"
        from app.config.settings import Settings
        with pytest.raises(ValueError):
            Settings()
    finally:
        os.environ.clear()
        os.environ.update(env_backup)
        _reset()


def test_webhook_secret_must_differ_from_session_secret(tmp_path):
    env_backup = dict(os.environ)
    try:
        os.environ["APP_ENV"] = "development"
        os.environ["SESSION_SECRET"] = "same-secret-value-1234567890"
        os.environ["TELEGRAM_WEBHOOK_ENABLED"] = "true"
        os.environ["TELEGRAM_WEBHOOK_SECRET"] = "same-secret-value-1234567890"
        from app.config.settings import Settings
        with pytest.raises(ValueError):
            Settings()
    finally:
        os.environ.clear()
        os.environ.update(env_backup)
        _reset()


# --------------------------------------------------------------------------- #
# initData max-age boundary: just past max-age rejected (max-age is 3600 in conftest env).
# --------------------------------------------------------------------------- #
def test_init_data_just_past_max_age_rejected(client):
    from tests.conftest import BOT_TOKEN
    from tests.test_auth import signed_init_data

    stale = signed_init_data(BOT_TOKEN, {"id": 610, "first_name": "X"}, auth_date=int(time.time()) - 3601)
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": stale})
    assert r.status_code == 401


def test_init_data_within_max_age_accepted(client):
    from tests.conftest import BOT_TOKEN
    from tests.test_auth import signed_init_data

    fresh = signed_init_data(BOT_TOKEN, {"id": 611, "first_name": "X"}, auth_date=int(time.time()) - 1800)
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": fresh})
    assert r.status_code == 200
