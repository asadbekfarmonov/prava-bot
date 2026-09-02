"""Slice 5 QA gap coverage (review_tests): webhook enable-gating + startup registration.

These extend tests/test_slice5_deployment.py with two properties the spec requires but
that were not directly asserted:

  1. docs/spec/13 "Production uses webhooks, not long polling ... On startup the app
     registers the webhook only when TELEGRAM_WEBHOOK_ENABLED is true": when disabled,
     the /telegram/webhook route must NOT be registered and no bot is built (so startup
     never calls set_webhook / couples deploy to Telegram reachability).
  2. docs/spec/13 + 09: when enabled, startup must register the webhook to
     {MINI_APP_URL}/telegram/webhook WITH the secret_token and set the menu-button to
     MINI_APP_URL. No network — aiogram Bot calls are monkeypatched and their args captured.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.domain.base import Base
from app.storage.db import get_engine, reset_engine_state
from app.storage.media_storage import set_media_storage


def _base_env(tmp_path) -> dict:
    return {
        "DATABASE_URL": f"sqlite:///{tmp_path / 'webhook_gap.db'}",
        "ADMIN_TELEGRAM_IDS": "9001",
        "BOT_TOKEN": "123456:test-token",
        "TELEGRAM_INIT_DATA_MAX_AGE_SECONDS": "3600",
        "MINI_APP_URL": "https://app.prava.uz",
    }


def _build_app(env: dict):
    for k, v in env.items():
        os.environ[k] = v
    get_settings.cache_clear()
    reset_engine_state()
    set_media_storage(None)
    from app.main import create_app

    Base.metadata.create_all(bind=get_engine())
    return create_app()


@pytest.fixture()
def _clean_env():
    saved = dict(os.environ)
    for k in ("APP_ENV", "APP_DEBUG", "SESSION_SECRET", "DEV_AUTH_ENABLED",
              "TELEGRAM_WEBHOOK_ENABLED", "TELEGRAM_WEBHOOK_SECRET"):
        os.environ.pop(k, None)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()
    reset_engine_state()
    set_media_storage(None)


def test_webhook_route_absent_when_disabled(tmp_path, _clean_env):
    """Disabled webhook => no /telegram/webhook route and no bot => startup never
    calls Telegram (docs/spec/13: register 'only when enabled')."""
    env = _base_env(tmp_path)
    env.update(
        {
            "APP_ENV": "production",
            "APP_DEBUG": "false",
            "SESSION_SECRET": "prod-session-secret-that-is-long-enough-1234567890",
            "DEV_AUTH_ENABLED": "false",
            "TELEGRAM_WEBHOOK_ENABLED": "false",
            "TELEGRAM_WEBHOOK_SECRET": "",
        }
    )
    app = _build_app(env)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/telegram/webhook" not in paths
    assert getattr(app.state, "telegram_bot", None) is None
    # A POST to the (unregistered) webhook path must NOT be processed as a webhook.
    with TestClient(app) as c:
        r = c.post("/telegram/webhook", json={"update_id": 1})
    assert r.status_code != 200


def test_webhook_registered_on_startup_with_secret_and_url(tmp_path, _clean_env, monkeypatch):
    """Enabled webhook => startup sets the menu-button to MINI_APP_URL and registers the
    webhook to {MINI_APP_URL}/telegram/webhook WITH secret_token (docs/spec/13, 09)."""
    set_webhook_calls: list[dict] = []
    menu_calls: list[dict] = []

    async def _capture_set_webhook(self, url, *args, **kwargs):
        set_webhook_calls.append({"url": url, "kwargs": kwargs})
        return True

    async def _capture_menu(self, *args, **kwargs):
        menu_calls.append(kwargs)
        return True

    async def _sclose(*args, **kwargs):
        return None

    monkeypatch.setattr("aiogram.Bot.set_webhook", _capture_set_webhook)
    monkeypatch.setattr("aiogram.Bot.set_chat_menu_button", _capture_menu)
    # aiogram's module-level handlers router can attach to only one Dispatcher per
    # process (the webhook_app test in test_slice5_deployment already uses it). We only
    # assert the startup registration args here, so build a bare dispatcher.
    from aiogram import Dispatcher

    monkeypatch.setattr("app.bot.bootstrap.create_dispatcher", lambda: Dispatcher())

    env = _base_env(tmp_path)
    env.update(
        {
            "APP_ENV": "production",
            "APP_DEBUG": "false",
            "SESSION_SECRET": "prod-session-secret-that-is-long-enough-1234567890",
            "DEV_AUTH_ENABLED": "false",
            "TELEGRAM_WEBHOOK_ENABLED": "true",
            "TELEGRAM_WEBHOOK_SECRET": "webhook-secret-differs-from-session-000",
        }
    )
    app = _build_app(env)
    monkeypatch.setattr(app.state.telegram_bot.session, "close", _sclose)

    # Entering the TestClient context manager runs the lifespan startup.
    with TestClient(app):
        pass

    assert len(set_webhook_calls) == 1, "webhook must be registered exactly once on startup"
    call = set_webhook_calls[0]
    assert call["url"] == "https://app.prava.uz/telegram/webhook"
    assert call["kwargs"].get("secret_token") == "webhook-secret-differs-from-session-000"
    assert call["kwargs"].get("allowed_updates") == ["message"]
    assert len(menu_calls) == 1, "menu-button must be set on startup"
