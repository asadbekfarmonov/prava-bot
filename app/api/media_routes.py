"""Media upload (admin) + content-addressed serving (docs/spec/05, 09).

Serving route: GET /api/media/{media_id}/{content_hash}
- published-question media is PUBLIC and cacheable behind the hash (immutable);
- draft/unpublished media is ADMIN-ONLY (private, no-store);
- unknown id / mismatched hash / unauthorized draft -> 404 (no existence leak).
NOTE: not /api/questions/{id}/media (docs/spec/05).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.admin_deps import require_role, resolve_effective_role
from app.api.deps import DbSession
from app.config import get_settings
from app.domain.enums import AdminRole, VersionStatus
from app.domain.models import QuestionVersion, QuestionMedia, User
from app.services import media as media_service
from app.services.audit import record_audit
from app.storage.media_storage import get_media_storage

router = APIRouter()

AuthorUser = Annotated[User, Depends(require_role(AdminRole.CONTENT_AUTHOR))]

_MAX_UPLOAD_BYTES = 30 * 1024 * 1024  # hard cap before type-specific caps apply


def _media_out(media: QuestionMedia) -> dict:
    return {
        "id": media.id,
        "media_type": media.media_type.value,
        "content_type": media.content_type,
        "content_hash": media.content_hash,
        "width": media.width,
        "height": media.height,
        "duration_ms": media.duration_ms,
        "byte_size": media.byte_size,
        "url": f"/api/media/{media.id}/{media.content_hash}",
    }


@router.post("/api/admin/media", status_code=status.HTTP_201_CREATED)
async def upload_media(
    user: AuthorUser,
    db: DbSession,
    file: UploadFile,
    alt_text: Annotated[str | None, Form()] = None,
) -> dict:
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fayl juda katta")
    try:
        media = media_service.ingest_upload(
            db,
            raw=raw,
            filename=file.filename,
            client_content_type=file.content_type,
            author=user,
            alt_text_uz=alt_text,
        )
    except media_service.MediaValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record_audit(db, user, "media.upload", "question_media", media.id,
                 detail={"content_type": media.content_type, "byte_size": media.byte_size})
    db.commit()
    db.refresh(media)
    return _media_out(media)


def _is_published_media(db: DbSession, media_id: str) -> bool:
    if db.scalar(
        select(QuestionVersion.id).where(
            QuestionVersion.media_id == media_id,
            QuestionVersion.status == VersionStatus.PUBLISHED,
        ).limit(1)
    ):
        return True
    return _is_published_theory_media(db, media_id)


def _is_published_theory_media(db, media_id: str) -> bool:
    """Media is also public when referenced by a PUBLISHED Theory/catalogue entity
    (section icon, article hero/block media, sign/marking/gesture/light media)."""
    from app.domain.models import (
        ControllerGesture,
        RoadMarking,
        RoadSign,
        TheoryArticle,
        TheoryArticleVersion,
        TheoryContentBlock,
        TheorySection,
        TrafficLightState,
    )

    # Section icons on published sections.
    if db.scalar(
        select(TheorySection.id).where(
            TheorySection.icon_media_id == media_id,
            TheorySection.status == VersionStatus.PUBLISHED,
        ).limit(1)
    ):
        return True

    # Article hero media / block media on the CURRENT published article version.
    if db.scalar(
        select(TheoryArticleVersion.id)
        .join(TheoryArticle, TheoryArticle.current_version_id == TheoryArticleVersion.id)
        .where(
            TheoryArticleVersion.hero_media_id == media_id,
            TheoryArticle.lifecycle_status == VersionStatus.PUBLISHED,
        ).limit(1)
    ):
        return True
    if db.scalar(
        select(TheoryContentBlock.id)
        .join(TheoryArticle, TheoryArticle.current_version_id == TheoryContentBlock.article_version_id)
        .where(
            TheoryContentBlock.media_id == media_id,
            TheoryArticle.lifecycle_status == VersionStatus.PUBLISHED,
        ).limit(1)
    ):
        return True

    # Catalogue container media (published containers only).
    catalog = (
        (RoadSign, (RoadSign.media_id,)),
        (RoadMarking, (RoadMarking.media_id,)),
        (ControllerGesture, (ControllerGesture.media_id, ControllerGesture.animation_media_id)),
        (TrafficLightState, (TrafficLightState.media_id,)),
    )
    from sqlalchemy import or_

    for model, media_cols in catalog:
        cond = or_(*[col == media_id for col in media_cols])
        if db.scalar(
            select(model.id).where(cond, model.lifecycle_status == VersionStatus.PUBLISHED).limit(1)
        ):
            return True
    return False


def _requester_is_admin(request: Request, db) -> bool:
    user_id = request.session.get("user_id")
    if not user_id:
        return False
    user = db.get(User, user_id)
    if user is None:
        return False
    return resolve_effective_role(user) is not None


@router.get("/api/media/{media_id}/{content_hash}")
def serve_media(media_id: str, content_hash: str, request: Request, db: DbSession):
    media = db.get(QuestionMedia, media_id)
    # Mismatched hash or unknown id -> 404 (content-addressed; no existence leak).
    if media is None or media.content_hash != content_hash:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media topilmadi")

    published = _is_published_media(db, media.id)
    if not published:
        # Draft/unpublished media is admin-only.
        if not _requester_is_admin(request, db):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media topilmadi")

    storage = get_media_storage()
    ttl = get_settings().media_presign_ttl_seconds
    presigned = storage.create_download_url(media.storage_key, ttl=ttl)
    if presigned:
        # Real object storage: redirect to a short-lived presigned GET.
        return RedirectResponse(url=presigned, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    try:
        data = storage.get(media.storage_key)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media topilmadi") from exc

    if published:
        cache_control = "public, max-age=31536000, immutable"
    else:
        cache_control = "private, no-store"
    return Response(content=data, media_type=media.content_type, headers={"Cache-Control": cache_control})
