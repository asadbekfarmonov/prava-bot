"""Server-side admin authorization (docs/spec/08 roles + 09 admin security).

Being in ADMIN_TELEGRAM_IDS (or SUPERADMIN_TELEGRAM_IDS) is the *base* capability;
the EFFECTIVE capability is the user's persisted ``admin_role``. Every admin endpoint
enforces ``require_role(min_role)`` server-side — hiding frontend routes is NOT a
control. A user removed from the allowlist loses capability on the next request
(role is resolved server-side each time, never cached in the cookie).
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.api.deps import CurrentUser
from app.config import get_settings
from app.domain.enums import AdminRole, role_rank
from app.domain.models import User


def _telegram_id_int(user: User) -> int | None:
    try:
        return int(user.telegram_id)
    except (TypeError, ValueError):
        return None


def resolve_effective_role(user: User) -> AdminRole | None:
    """Effective admin role, or None. Requires allowlist membership AND a set role."""
    settings = get_settings()
    tid = _telegram_id_int(user)
    if tid is None:
        return None
    if tid not in settings.admin_ids and tid not in settings.superadmin_ids:
        return None
    return user.admin_role


def require_role(min_role: AdminRole) -> Callable[..., User]:
    """FastAPI dependency factory enforcing ``effective_role >= min_role`` (403 else)."""

    def _dependency(user: CurrentUser) -> User:
        effective = resolve_effective_role(user)
        if role_rank(effective) < role_rank(min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Ruxsat etilmagan (rol talab qilinadi)"
            )
        return user

    return _dependency


# Convenience typed dependencies for the common gates.
def require_author() -> Callable[..., User]:
    return require_role(AdminRole.CONTENT_AUTHOR)


def require_reviewer() -> Callable[..., User]:
    return require_role(AdminRole.CONTENT_REVIEWER)


def require_admin() -> Callable[..., User]:
    return require_role(AdminRole.ADMIN)


def require_superadmin() -> Callable[..., User]:
    return require_role(AdminRole.SUPERADMIN)


AuthorUser = Depends(require_role(AdminRole.CONTENT_AUTHOR))
ReviewerUser = Depends(require_role(AdminRole.CONTENT_REVIEWER))
AdminUser = Depends(require_role(AdminRole.ADMIN))
SuperadminUser = Depends(require_role(AdminRole.SUPERADMIN))
