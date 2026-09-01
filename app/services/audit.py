"""Admin audit trail (docs/spec/08 + 09): every create/edit/review/publish/supersede/
archive/import/report-resolve is recorded with actor, entity, and optional warning."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.models import AdminAuditEvent, User


def record_audit(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    *,
    version: int | None = None,
    detail: dict | None = None,
    warning: str | None = None,
) -> AdminAuditEvent:
    event = AdminAuditEvent(
        actor_user_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        version=version,
        detail=detail,
        warning=warning,
    )
    db.add(event)
    db.flush()
    return event
