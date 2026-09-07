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
    id/role. ``admin_role`` is NOT set here and is never consulted for gating — admin
    capability is resolved from the ADMIN_TELEGRAM_IDS allowlist server-side on every
    request (two-level admin/user model), so it can never be smuggled through a login
    payload.
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
    # Two-level model: admin_role is NOT set here. Admin capability is resolved from the
    # ADMIN_TELEGRAM_IDS allowlist server-side on every request (see admin_deps); the
    # users.admin_role DB column is vestigial and never consulted for gating.
    db.commit()
    db.refresh(user)
    return user


def _is_allowlisted(user: User) -> bool:
    try:
        return int(user.telegram_id) in get_settings().all_admin_ids
    except (TypeError, ValueError):
        return False


def user_out(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "photo_url": user.photo_url,
        # Two-level model: is_admin is purely allowlist-driven (server-side). We also
        # surface admin_role='admin' for allowlisted users so the frontend's existing
        # admin-entry / canReview checks keep working with zero frontend-logic changes.
        # The DB column user.admin_role is NOT consulted here.
        "is_admin": _is_allowlisted(user),
        "admin_role": "admin" if _is_allowlisted(user) else None,
        "onboarding_completed": bool(user.profile and user.profile.onboarding_completed),
    }
