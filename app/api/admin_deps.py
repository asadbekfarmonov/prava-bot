"""Server-side admin authorization (two-level model: ADMIN / USER).

The role model is an ALLOWLIST: any Telegram id in ADMIN_TELEGRAM_IDS (or the
SUPERADMIN_TELEGRAM_IDS alias) is a full ADMIN, resolved server-side on every
request. There is no persisted role tier and no role-assignment flow — the
``users.admin_role`` DB column is vestigial and never consulted for gating.

Every admin endpoint enforces ``require_role(...)`` server-side; hiding frontend
routes is NOT a control. A user removed from the allowlist loses capability on the
next request (membership is resolved server-side each time, never cached in the
cookie). ``min_role`` is retained in the signature for source compatibility with the
existing typed deps (AuthorUser/ReviewerUser/AdminUser/SuperadminUser) but is ignored:
an allowlisted admin passes every gate.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.api.deps import CurrentUser
from app.config import get_settings
from app.domain.enums import AdminRole
from app.domain.models import User


def _telegram_id_int(user: User) -> int | None:
    try:
        return int(user.telegram_id)
    except (TypeError, ValueError):
        return None


def resolve_effective_role(user: User) -> AdminRole | None:
    """Effective admin role, or None. ADMIN iff the Telegram id is allowlisted.

    Does NOT depend on the ``user.admin_role`` DB column (two-level model).
    """
    settings = get_settings()
    tid = _telegram_id_int(user)
    if tid is None:
        return None
    if tid in settings.all_admin_ids:
        return AdminRole.ADMIN
    return None


def require_role(min_role: AdminRole) -> Callable[..., User]:
    """FastAPI dependency factory. Allowed iff the user is an allowlisted admin.

    ``min_role`` is ignored (two-level model): any admin passes every gate. The
    parameter is kept so existing routers/typed deps keep compiling unchanged.
    """

    def _dependency(user: CurrentUser) -> User:
        if resolve_effective_role(user) is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ruxsat etilmagan (administrator talab qilinadi)",
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
