from __future__ import annotations

import hashlib
import hmac
import json
import time
from json import JSONDecodeError
from urllib.parse import parse_qsl

from app.config import get_settings


class TelegramAuthError(ValueError):
    pass


def validate_init_data(init_data: str, max_age_seconds: int | None = None) -> dict:
    """Validate Telegram Mini App initData per Telegram's spec.

    Recomputes the HMAC with the bot token and compares in constant time. Enforces
    max-age and rejects future-dated ``auth_date``. The authenticated identity comes
    ONLY from validated initData — never from a client-supplied user id/role.
    """
    settings = get_settings()
    if not settings.bot_token:
        raise TelegramAuthError("Telegram login is not configured on the server.")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("Telegram did not provide a login signature.")

    try:
        auth_date = int(pairs.get("auth_date", "0") or "0")
    except ValueError as exc:
        raise TelegramAuthError("Telegram did not provide a valid login timestamp.") from exc
    if auth_date <= 0:
        raise TelegramAuthError("Telegram did not provide a login timestamp.")
    if auth_date > int(time.time()) + 60:
        raise TelegramAuthError(
            "Telegram login timestamp is invalid. Reopen the Mini App from Telegram."
        )
    effective_max_age = (
        max_age_seconds if max_age_seconds is not None else settings.telegram_init_data_max_age_seconds
    )
    if effective_max_age and auth_date < int(time.time()) - effective_max_age:
        raise TelegramAuthError("Telegram login expired. Reopen the Mini App from Telegram.")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", settings.bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramAuthError("Telegram login could not be verified.")

    try:
        user_payload = json.loads(pairs["user"])
    except (KeyError, JSONDecodeError) as exc:
        raise TelegramAuthError("Telegram did not provide a valid user profile.") from exc
    if not isinstance(user_payload, dict) or "id" not in user_payload:
        raise TelegramAuthError("Telegram did not provide a valid user profile.")

    return {
        "auth_date": auth_date,
        "query_id": pairs.get("query_id"),
        "user": user_payload,
        "raw": pairs,
    }
