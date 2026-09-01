"""QA adversarial edge cases (Slice 1).

Extends the developer's suite with tests that verify the *security-relevant claims*
rather than the happy path: that the initData HMAC actually covers the payload
(not just a corrupted hash), that identity/role/correctness can never be smuggled
via the client, that option ids are opaque, and that key schema invariants hold.
"""

import json
import os
import time
from urllib.parse import parse_qsl, quote, urlencode

from fastapi.testclient import TestClient

from tests.conftest import BOT_TOKEN
from tests.test_auth import signed_init_data
from tests.seed_helper import seed_demo_bank


# --------------------------------------------------------------------------- #
# initData HMAC: prove the signature covers the *content*, not only the hash.
# --------------------------------------------------------------------------- #
def test_tampered_user_field_rejected(client):
    """Valid signature for id=700, then swap the user id but keep the old hash.

    A correct HMAC check must reject this (the hash no longer matches the data);
    otherwise a client could sign as itself and impersonate anyone.
    """
    good = signed_init_data(BOT_TOKEN, {"id": 700, "first_name": "Real"})
    pairs = dict(parse_qsl(good, keep_blank_values=True))
    pairs["user"] = json.dumps({"id": 999, "first_name": "Attacker"}, separators=(",", ":"))
    tampered = urlencode(pairs, quote_via=quote)
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": tampered})
    assert r.status_code == 401


def test_wrong_bot_token_signature_rejected(client):
    # Signed with a different bot token => HMAC mismatch against the server's token.
    init_data = signed_init_data("999999:attacker-secret", {"id": 800, "first_name": "X"})
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": init_data})
    assert r.status_code == 401


def test_missing_hash_rejected(client):
    init_data = "auth_date=%d&user=%s" % (
        int(time.time()),
        quote(json.dumps({"id": 1, "first_name": "X"}, separators=(",", ":"))),
    )
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": init_data})
    assert r.status_code == 401


def test_future_within_skew_accepted(client):
    # <=60s of clock skew is tolerated; 600s is rejected (see test_auth).
    init_data = signed_init_data(BOT_TOKEN, {"id": 601, "first_name": "X"}, auth_date=int(time.time()) + 30)
    r = client.post("/api/auth/telegram-mini-app", json={"init_data": init_data})
    assert r.status_code == 200


# --------------------------------------------------------------------------- #
# Session gating: no session cookie => 401 on protected routes.
# --------------------------------------------------------------------------- #
def test_unauthenticated_requests_rejected(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/practice/questions/next").status_code == 401
    assert client.post("/api/practice/sessions", json={}).status_code == 401
    assert client.post(
        "/api/practice/answers",
        json={"practice_session_id": "x", "question_id": "y"},
    ).status_code == 401


# --------------------------------------------------------------------------- #
# Dev login is gated on BOTH conditions (APP_ENV=development AND DEV_AUTH_ENABLED).
# The developer tested the env half; this closes the flag half.
# --------------------------------------------------------------------------- #
def test_dev_login_disabled_when_flag_off_even_in_development(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'flagoff.db'}"
    os.environ["APP_ENV"] = "development"
    os.environ["DEV_AUTH_ENABLED"] = "false"
    os.environ["SESSION_SECRET"] = "test-secret"
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
        os.environ["DEV_AUTH_ENABLED"] = "true"
        from app.config.settings import get_settings
        from app.storage.db import reset_engine_state

        get_settings.cache_clear()
        reset_engine_state()


# --------------------------------------------------------------------------- #
# Mass-assignment defense (docs/spec/09): server ignores client-supplied
# privileged / correctness fields.
# --------------------------------------------------------------------------- #
def test_profile_cannot_smuggle_admin_role(dev_client):
    # dev_client is telegram_id 1001 (NOT in ADMIN_TELEGRAM_IDS=9001).
    r = dev_client.put(
        "/api/profile",
        json={
            "display_name": "X",
            "category": "B",
            "language": "uz",
            "admin_role": "superadmin",  # smuggled
            "is_admin": True,            # smuggled
        },
    )
    assert r.status_code == 200
    me = dev_client.get("/api/auth/me").json()
    assert me["user"]["admin_role"] is None
    assert me["user"]["is_admin"] is False


def test_answer_ignores_client_supplied_is_correct(dev_client):
    seed_demo_bank()
    dev_client.post("/api/practice/sessions", json={"topic": "road_signs"})
    q = dev_client.get("/api/practice/questions/next", params={"topic": "road_signs"}).json()

    # Discover the correct option via a throwaway (repeatable) session.
    sid1 = dev_client.post("/api/practice/sessions", json={"topic": "road_signs"}).json()["id"]
    disc = dev_client.post(
        "/api/practice/answers",
        json={
            "practice_session_id": sid1,
            "question_id": q["question_id"],
            "selected_option_id": q["options"][0]["id"],
        },
    ).json()
    correct_id = disc["correct_option_id"]
    wrong = next(o for o in q["options"] if o["id"] != correct_id)

    # Submit the WRONG option but smuggle is_correct=true; server must grade False.
    sid2 = dev_client.post("/api/practice/sessions", json={"topic": "road_signs"}).json()["id"]
    r = dev_client.post(
        "/api/practice/answers",
        json={
            "practice_session_id": sid2,
            "question_id": q["question_id"],
            "selected_option_id": wrong["id"],
            "is_correct": True,   # smuggled
            "correct_option_id": wrong["id"],  # smuggled
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_correct"] is False
    assert body["correct_option_id"] == correct_id


# --------------------------------------------------------------------------- #
# Option ids are opaque UUIDs; correct answer is not sorted-first / positional.
# --------------------------------------------------------------------------- #
def test_option_ids_are_opaque_uuids(dev_client):
    seed_demo_bank()
    dev_client.post("/api/practice/sessions", json={})
    q = dev_client.get("/api/practice/questions/next").json()
    for o in q["options"]:
        assert len(o["id"]) == 36 and o["id"].count("-") == 4  # UUID form
        assert o["id"] != str(o["position"])                    # id does not encode position


def test_correct_option_not_always_first_in_bank():
    from app.services.content_sources.seed import SeedContentSource

    src = SeedContentSource()
    correct_indexes = [
        next(i for i, o in enumerate(q.options) if o.is_correct) for q in src.questions()
    ]
    # If the bank always placed the correct option first, an attacker could infer it.
    assert set(correct_indexes) != {0}
    assert len(set(correct_indexes)) > 1


# --------------------------------------------------------------------------- #
# Schema invariants (docs/spec/02).
# --------------------------------------------------------------------------- #
def test_media_holds_metadata_not_bytes():
    from app.domain.models import QuestionMedia

    cols = set(QuestionMedia.__table__.columns.keys())
    assert {"content_hash", "storage_key", "byte_size"} <= cols  # metadata present
    for forbidden in ("data", "bytes", "blob", "payload", "content"):
        assert forbidden not in cols  # no in-DB media payload


def test_practice_answer_has_no_global_unique_constraint():
    from sqlalchemy import UniqueConstraint

    from app.domain.models import PracticeAnswer

    uniques = [
        c for c in PracticeAnswer.__table__.constraints if isinstance(c, UniqueConstraint)
    ]
    assert uniques == []  # questions may recur across sessions


def test_question_version_translation_carries_content_not_the_version_row():
    # Content lives in the translation table, not on QuestionVersion itself.
    from app.domain.models import QuestionVersion, QuestionVersionTranslation

    version_cols = set(QuestionVersion.__table__.columns.keys())
    assert "prompt" not in version_cols
    assert "short_explanation" not in version_cols
    tr_cols = set(QuestionVersionTranslation.__table__.columns.keys())
    assert {"prompt", "short_explanation", "language"} <= tr_cols


def test_exam_constants_absent_from_env_settings():
    from app.config.settings import Settings
    from app.domain.exam_config import get_exam_config

    fields = set(Settings.model_fields.keys())
    for banned in (
        "questions",
        "question_count",
        "time_limit_seconds",
        "minimum_correct",
        "pass_correct",
        "maximum_mistakes",
    ):
        assert banned not in fields  # legal exam constants must not be env-configurable

    cfg = get_exam_config()
    assert (cfg.questions, cfg.minimum_correct, cfg.time_limit_seconds) == (20, 18, 1500)
