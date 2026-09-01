from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.models import User


def upsert_telegram_user(db: Session, payload: dict[str, Any]) -> User:
    """Create/update a user from a *trusted* Telegram payload.

    The caller must have validated initData first; we never trust a client-supplied
    id/role. ``admin_role`` is NOT set here — it is allowlist-gated + assigned
    server-side by a superadmin (out of slice-1 scope), so it can never be smuggled
    through a login payload.
    """
    telegram_id = str(payload["id"])
    user = db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(telegram_id=telegram_id)
        db.add(user)
    user.username = payload.get("username")
    user.first_name = payload.get("first_name")
    user.last_name = payload.get("last_name")
    user.photo_url = payload.get("photo_url")
    user.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def user_out(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "photo_url": user.photo_url,
        "is_admin": int(user.telegram_id) in get_settings().admin_ids,
        "admin_role": user.admin_role.value if user.admin_role else None,
        "onboarding_completed": bool(user.profile and user.profile.onboarding_completed),
    }
