"""Slice 5 — production deployment wiring tests (docs/spec/13, 09, 05).

Covers: /health, Telegram webhook secret verification, production settings validators,
dev-login unavailable in production, CORS localhost gating, and the two Railway Cron
job entrypoints (expired-mock sweep + orphan-media cleanup). No network: the webhook
bot's Telegram calls are monkeypatched and jobs use the in-memory MediaStorage fake.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config.settings import Settings, get_settings
from app.domain.base import Base
from app.domain.enums import Category, MediaType, MockStatus, Topic, VersionStatus
from app.domain.models import MockAttempt, Question, QuestionMedia, QuestionVersion
from app.storage.db import get_engine, reset_engine_state, session_scope
from app.storage.media_storage import InMemoryMediaStorage, set_media_storage


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _base_env(tmp_path) -> dict:
    return {
        "DATABASE_URL": f"sqlite:///{tmp_path / 'slice5.db'}",
        "ADMIN_TELEGRAM_IDS": "9001",
        "SUPERADMIN_TELEGRAM_IDS": "9001",
        "BOT_TOKEN": "123456:test-token",
        "TELEGRAM_INIT_DATA_MAX_AGE_SECONDS": "3600",
    }


def _apply_env(env: dict) -> None:
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _build_app(env: dict):
    """Build a fresh app with the given environment (mirrors conftest wiring)."""
    _apply_env(env)
    get_settings.cache_clear()
    reset_engine_state()
    set_media_storage(None)
    from app.main import create_app

    Base.metadata.create_all(bind=get_engine())
    return create_app()


@pytest.fixture()
def prod_app(tmp_path):
    saved = dict(os.environ)
    env = _base_env(tmp_path)
    env.update(
        {
            "APP_ENV": "production",
            "APP_DEBUG": "false",
            "SESSION_SECRET": "prod-session-secret-that-is-long-enough-1234567890",
            "MINI_APP_URL": "https://app.prava.uz",
            "DEV_AUTH_ENABLED": "false",
            "TELEGRAM_WEBHOOK_ENABLED": "false",
            "TELEGRAM_WEBHOOK_SECRET": "",
        }
    )
    app = _build_app(env)
    try:
        yield app
    finally:
        os.environ.clear()
        os.environ.update(saved)
        get_settings.cache_clear()
        reset_engine_state()
        set_media_storage(None)


# --------------------------------------------------------------------------- #
# /health
# --------------------------------------------------------------------------- #
def test_health_200_when_db_reachable(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --------------------------------------------------------------------------- #
# Webhook secret verification
# --------------------------------------------------------------------------- #
@pytest.fixture()
def webhook_app(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return True

    monkeypatch.setattr("aiogram.Bot.set_webhook", _noop)
    monkeypatch.setattr("aiogram.Bot.set_chat_menu_button", _noop)

    saved = dict(os.environ)
    env = _base_env(tmp_path)
    env.update(
        {
            "APP_ENV": "development",
            "APP_DEBUG": "true",
            "SESSION_SECRET": "dev-session-secret",
            "MINI_APP_URL": "https://app.prava.uz",
            "DEV_AUTH_ENABLED": "true",
            "TELEGRAM_WEBHOOK_ENABLED": "true",
            "TELEGRAM_WEBHOOK_SECRET": "webhook-secret-differs-from-session",
        }
    )
    app = _build_app(env)
    # Neutralize the bot's network session so lifespan shutdown does not hit the network.
    async def _sclose(*args, **kwargs):
        return None

    monkeypatch.setattr(app.state.telegram_bot.session, "close", _sclose)
    try:
        yield app
    finally:
        os.environ.clear()
        os.environ.update(saved)
        get_settings.cache_clear()
        reset_engine_state()
        set_media_storage(None)


def test_webhook_secret_verification(webhook_app):
    """One app instance (aiogram's module-level router attaches to a single dispatcher
    per process): wrong + missing secret -> 403; correct secret -> 200. Also asserts
    (docs/spec/09 webhook/bot) that the secret and full update payload are NEVER logged."""
    import logging

    log_records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            log_records.append(record.getMessage())

    handler = _Capture()
    prava_logger = logging.getLogger("prava")
    prava_logger.addHandler(handler)
    good_secret = "webhook-secret-differs-from-session"
    payload_marker = "SUPERSECRETPAYLOADMARKER"
    try:
        with TestClient(webhook_app) as c:
            # Wrong secret -> 403.
            wrong = c.post(
                "/telegram/webhook",
                json={"update_id": 1, "note": payload_marker},
                headers={"X-Telegram-Bot-Api-Secret-Token": "the-wrong-secret-value"},
            )
            assert wrong.status_code == 403

            # Missing secret -> 403.
            missing = c.post("/telegram/webhook", json={"update_id": 1})
            assert missing.status_code == 403

            # Correct secret -> 200 (empty-ish update: no handler fires, no network call).
            ok = c.post(
                "/telegram/webhook",
                json={"update_id": 1, "note": payload_marker},
                headers={"X-Telegram-Bot-Api-Secret-Token": good_secret},
            )
            assert ok.status_code == 200
            assert ok.json() == {"ok": True}
    finally:
        prava_logger.removeHandler(handler)

    blob = "\n".join(log_records)
    assert good_secret not in blob, "webhook secret leaked into logs"
    assert "the-wrong-secret-value" not in blob, "rejected secret leaked into logs"
    assert payload_marker not in blob, "full update payload leaked into logs"


# --------------------------------------------------------------------------- #
# Settings validators
# --------------------------------------------------------------------------- #
def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_webhook_secret_equal_session_secret_rejected():
    with pytest.raises(ValidationError):
        _settings(
            APP_ENV="development",
            SESSION_SECRET="same-secret-value",
            TELEGRAM_WEBHOOK_ENABLED=True,
            TELEGRAM_WEBHOOK_SECRET="same-secret-value",
        )


def test_prod_rejects_weak_session_secret():
    with pytest.raises(ValidationError):
        _settings(
            APP_ENV="production",
            APP_DEBUG=False,
            SESSION_SECRET="change-me",
            MINI_APP_URL="https://app.prava.uz",
        )


def test_prod_rejects_app_debug_true():
    with pytest.raises(ValidationError):
        _settings(
            APP_ENV="production",
            APP_DEBUG=True,
            SESSION_SECRET="prod-session-secret-that-is-long-enough-1234567890",
            MINI_APP_URL="https://app.prava.uz",
        )


def test_prod_rejects_http_mini_app_url():
    with pytest.raises(ValidationError):
        _settings(
            APP_ENV="production",
            APP_DEBUG=False,
            SESSION_SECRET="prod-session-secret-that-is-long-enough-1234567890",
            MINI_APP_URL="http://app.prava.uz",
        )


def test_prod_dev_auth_unavailable_even_if_flag_true():
    s = _settings(
        APP_ENV="production",
        APP_DEBUG=False,
        SESSION_SECRET="prod-session-secret-that-is-long-enough-1234567890",
        MINI_APP_URL="https://app.prava.uz",
        DEV_AUTH_ENABLED=True,
    )
    assert s.is_dev_auth_available is False


def test_valid_prod_settings_ok():
    s = _settings(
        APP_ENV="production",
        APP_DEBUG=False,
        SESSION_SECRET="prod-session-secret-that-is-long-enough-1234567890",
        MINI_APP_URL="https://app.prava.uz",
        TELEGRAM_WEBHOOK_ENABLED=True,
        TELEGRAM_WEBHOOK_SECRET="a-different-webhook-secret",
    )
    assert s.app_env == "production"


# --------------------------------------------------------------------------- #
# Dev login 404 in production
# --------------------------------------------------------------------------- #
def test_dev_login_404_in_production(prod_app):
    with TestClient(prod_app) as c:
        r = c.post("/api/dev/login", json={"telegram_id": 1001, "first_name": "X"})
        assert r.status_code == 404


# --------------------------------------------------------------------------- #
# CORS localhost gating
# --------------------------------------------------------------------------- #
def test_cors_disallows_localhost_in_production(prod_app):
    with TestClient(prod_app) as c:
        r = c.get("/health", headers={"Origin": "http://localhost:5173"})
        assert r.headers.get("access-control-allow-origin") != "http://localhost:5173"


def test_cors_allows_app_origin_in_production(prod_app):
    with TestClient(prod_app) as c:
        r = c.get("/health", headers={"Origin": "https://app.prava.uz"})
        assert r.headers.get("access-control-allow-origin") == "https://app.prava.uz"


def test_cors_allows_localhost_in_development(client):
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


# --------------------------------------------------------------------------- #
# Expired-mock sweep job
# --------------------------------------------------------------------------- #
def _seed_and_start_mock(dev_client) -> str:
    from tests.seed_helper import seed_demo_bank

    seed_demo_bank()
    r = dev_client.post("/api/mock/attempts", json={})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_expired_mock_sweep_finalizes_and_is_idempotent(dev_client):
    from app.jobs import expired_mock_sweep

    attempt_id = _seed_and_start_mock(dev_client)

    # Force the deadline into the past (simulate an abandoned attempt).
    with session_scope() as db:
        att = db.get(MockAttempt, attempt_id)
        assert att.status == MockStatus.IN_PROGRESS
        att.expires_at = datetime.now(timezone.utc) - timedelta(seconds=30)

    with session_scope() as db:
        summary = expired_mock_sweep.run(db)
    assert summary["finalized"] == 1

    with session_scope() as db:
        att = db.get(MockAttempt, attempt_id)
        assert att.status == MockStatus.COMPLETED

    # Idempotent: second run finalizes nothing.
    with session_scope() as db:
        summary2 = expired_mock_sweep.run(db)
    assert summary2["finalized"] == 0


def test_expired_mock_sweep_leaves_live_attempt_untouched(dev_client):
    from app.jobs import expired_mock_sweep

    attempt_id = _seed_and_start_mock(dev_client)  # deadline is in the future

    with session_scope() as db:
        summary = expired_mock_sweep.run(db)
    assert summary["finalized"] == 0

    with session_scope() as db:
        att = db.get(MockAttempt, attempt_id)
        assert att.status == MockStatus.IN_PROGRESS


# --------------------------------------------------------------------------- #
# Orphan-media cleanup job
# --------------------------------------------------------------------------- #
def _make_media(db, *, age_days: int, storage: InMemoryMediaStorage) -> QuestionMedia:
    key = f"media/{age_days}-{os.urandom(4).hex()}.webp"
    storage.put(key, b"bytes", "image/webp")
    m = QuestionMedia(
        media_type=MediaType.IMAGE,
        content_type="image/webp",
        content_hash=os.urandom(8).hex(),
        storage_key=key,
        byte_size=5,
    )
    db.add(m)
    db.flush()
    # created_at has a server_default; override to simulate age.
    m.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    db.flush()
    return m


def test_orphan_media_cleanup_deletes_only_unreferenced_past_grace(client):
    from app.jobs import orphan_media_cleanup

    storage = InMemoryMediaStorage()

    with session_scope() as db:
        # (a) referenced media, old -> must be KEPT.
        referenced = _make_media(db, age_days=60, storage=storage)
        q = Question(category=Category.B, topic=Topic.ROAD_SIGNS)
        db.add(q)
        db.flush()
        qv = QuestionVersion(
            question_id=q.id, version=1, status=VersionStatus.PUBLISHED,
            media_id=referenced.id,
        )
        db.add(qv)
        # (b) unreferenced, old (past grace) -> must be DELETED.
        orphan_old = _make_media(db, age_days=60, storage=storage)
        # (c) unreferenced, recent (within grace) -> must be KEPT.
        orphan_recent = _make_media(db, age_days=5, storage=storage)
        db.flush()
        ref_id, old_id, recent_id = referenced.id, orphan_old.id, orphan_recent.id
        old_key = orphan_old.storage_key
        ref_key = referenced.storage_key

    with session_scope() as db:
        summary = orphan_media_cleanup.run(db, storage)

    assert summary["deleted_rows"] == 1
    assert summary["skipped_referenced"] == 1
    assert summary["within_grace"] == 1

    with session_scope() as db:
        assert db.get(QuestionMedia, ref_id) is not None       # referenced kept
        assert db.get(QuestionMedia, recent_id) is not None     # within grace kept
        assert db.get(QuestionMedia, old_id) is None            # orphan deleted

    assert storage.exists(ref_key) is True    # referenced object kept
    assert storage.exists(old_key) is False   # orphan object removed


def test_orphan_media_cleanup_is_idempotent(client):
    from app.jobs import orphan_media_cleanup

    storage = InMemoryMediaStorage()
    with session_scope() as db:
        _make_media(db, age_days=90, storage=storage)

    with session_scope() as db:
        first = orphan_media_cleanup.run(db, storage)
    assert first["deleted_rows"] == 1

    with session_scope() as db:
        second = orphan_media_cleanup.run(db, storage)
    assert second["deleted_rows"] == 0


# --------------------------------------------------------------------------- #
# QA gap coverage (review_tests): /health 503, cascade cleanup, secret non-logging


# --------------------------------------------------------------------------- #
# QA gap coverage (review_tests): /health 503 + orphan cleanup cascade
# --------------------------------------------------------------------------- #
def test_health_503_when_db_unreachable(client, monkeypatch):
    """/health must return 503 when the DB is unreachable (docs/spec/13 Healthcheck)."""
    import app.main as main_mod

    def _boom():
        raise RuntimeError("simulated DB outage")

    # Patch the engine accessor used inside the /health handler so SELECT 1 fails.
    monkeypatch.setattr(main_mod, "get_engine", _boom)
    r = client.get("/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "unhealthy"
    assert body["database"] == "unreachable"


def test_orphan_media_cleanup_deletes_media_with_translations(client):
    """Unreferenced media carrying alt-text translations must be reaped cleanly via
    ORM cascade, not raise a FK IntegrityError (docs/spec/13 orphan cleanup)."""
    from sqlalchemy import func, select

    from app.domain.enums import Language
    from app.domain.models import QuestionMediaTranslation
    from app.jobs import orphan_media_cleanup

    storage = InMemoryMediaStorage()
    with session_scope() as db:
        media = _make_media(db, age_days=60, storage=storage)
        db.add(
            QuestionMediaTranslation(
                media_id=media.id, language=Language.UZ, alt_text="Yo'l belgisi"
            )
        )
        db.flush()
        media_id = media.id
        key = media.storage_key

    with session_scope() as db:
        summary = orphan_media_cleanup.run(db, storage)
    assert summary["deleted_rows"] == 1

    with session_scope() as db:
        assert db.get(QuestionMedia, media_id) is None
        remaining = db.scalar(
            select(func.count())
            .select_from(QuestionMediaTranslation)
            .where(QuestionMediaTranslation.media_id == media_id)
        )
        assert remaining == 0
    assert storage.exists(key) is False


# --------------------------------------------------------------------------- #
# QA gap (review_tests): webhook secret REQUIRED when webhook enabled
# --------------------------------------------------------------------------- #
def test_webhook_enabled_requires_nonempty_secret():
    """docs/spec/13 + settings.py:78-80 — enabling the webhook with an empty
    TELEGRAM_WEBHOOK_SECRET must be rejected at config time (not silently accept a
    blank secret that would make hmac.compare_digest trivially satisfiable)."""
    with pytest.raises(ValidationError):
        _settings(
            APP_ENV="development",
            SESSION_SECRET="dev-session-secret",
            TELEGRAM_WEBHOOK_ENABLED=True,
            TELEGRAM_WEBHOOK_SECRET="",
        )
