import hashlib
import hmac
import json
import os
import time
from urllib.parse import quote, urlencode

import pytest
from fastapi.testclient import TestClient

from tests.conftest import BOT_TOKEN


def signed_init_data(bot_token: str, user: dict, auth_date: int | None = None) -> str:
    pairs = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "query-1",
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs, quote_via=quote)


def test_valid_init_data_creates_session(client):
    init_data = signed_init_data(BOT_TOKEN, {"id": 222, "first_name": "Aziz", "username": "aziz"})
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": init_data})
    assert r.status_code == 200
    assert r.json()["user"]["telegram_id"] == "222"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "aziz"


def test_forged_init_data_rejected(client):
    init_data = signed_init_data(BOT_TOKEN, {"id": 333}) + "tampered"
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": init_data})
    assert r.status_code == 401


def test_expired_init_data_rejected(client):
    init_data = signed_init_data(BOT_TOKEN, {"id": 444}, auth_date=int(time.time()) - 7200)
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": init_data})
    assert r.status_code == 401


def test_future_init_data_rejected(client):
    init_data = signed_init_data(BOT_TOKEN, {"id": 445}, auth_date=int(time.time()) + 600)
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": init_data})
    assert r.status_code == 401


def test_client_supplied_user_id_not_trusted(client):
    # A signed payload for id=500 must never yield a session for a different id.
    init_data = signed_init_data(BOT_TOKEN, {"id": 500, "first_name": "Real"})
    client.post("/api/auth/telegram-mini-app", json={"init_data": init_data})
    assert client.get("/api/auth/me").json()["user"]["telegram_id"] == "500"


def test_dev_login_available_in_development(client):
    r = client.post("/api/dev/login", json={"telegram_id": 9001, "first_name": "Admin"})
    assert r.status_code == 200
    assert r.json()["user"]["is_admin"] is True


def test_dev_login_disabled_outside_development(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'prod.db'}"
    os.environ["APP_ENV"] = "production"
    os.environ["APP_DEBUG"] = "false"
    os.environ["DEV_AUTH_ENABLED"] = "true"  # even enabled, non-dev env must gate it off
    os.environ["SESSION_SECRET"] = "x" * 40
    os.environ["MINI_APP_URL"] = "https://app.prava.uz"
    os.environ["BOT_TOKEN"] = BOT_TOKEN
    try:
        from app.config.settings import get_settings
        from app.domain.base import Base
        from app.main import create_app
        from app.storage.db import get_engine, reset_engine_state

        get_settings.cache_clear()
        reset_engine_state()
        Base.metadata.create_all(bind=get_engine())
        with TestClient(create_app()) as c:
            r = c.post("/api/dev/login", json={"telegram_id": 1, "first_name": "X"})
            assert r.status_code == 404
    finally:
        for k in ("APP_ENV", "APP_DEBUG", "MINI_APP_URL"):
            os.environ.pop(k, None)
        from app.config.settings import get_settings
        from app.storage.db import reset_engine_state

        reset_engine_state()
        get_settings.cache_clear()
