import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

BOT_TOKEN = "123456:test-token"


@pytest.fixture()
def client(tmp_path) -> Generator[TestClient, None, None]:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.db'}"
    os.environ["APP_ENV"] = "development"
    os.environ["DEV_AUTH_ENABLED"] = "true"
    os.environ["ADMIN_TELEGRAM_IDS"] = "9001"
    os.environ["SESSION_SECRET"] = "test-secret"
    os.environ["BOT_TOKEN"] = BOT_TOKEN
    os.environ["TELEGRAM_INIT_DATA_MAX_AGE_SECONDS"] = "3600"
    os.environ.pop("TELEGRAM_WEBHOOK_ENABLED", None)

    from app.api.rate_limit import clear_rate_limits  # noqa: F401  (optional; ignored if absent)
    from app.config.settings import get_settings
    from app.domain import models  # noqa: F401
    from app.domain.base import Base
    from app.main import create_app
    from app.storage.db import get_engine, reset_engine_state

    get_settings.cache_clear()
    reset_engine_state()
    Base.metadata.create_all(bind=get_engine())
    with TestClient(create_app()) as test_client:
        yield test_client
    reset_engine_state()
    get_settings.cache_clear()


@pytest.fixture()
def dev_client(client) -> TestClient:
    """A client logged in as a non-admin dev user with completed onboarding."""
    r = client.post("/api/dev/login", json={"telegram_id": 1001, "first_name": "Dev"})
    assert r.status_code == 200
    r = client.put("/api/profile", json={"display_name": "Dilnoza", "category": "B", "language": "uz"})
    assert r.status_code == 200
    return client
