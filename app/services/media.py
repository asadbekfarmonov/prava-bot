"""Media pipeline: upload validation + content-addressed ingestion (docs/spec/05, 09).

Hard rules (server-side, never trust the client):
- Sniff type from BYTES (magic bytes + Pillow for images; container magic for video);
  never trust the client Content-Type or filename.
- REJECT SVG entirely (script vector).
- Allow image/png|jpeg|webp (re-encode to WebP), image/gif (frame/pixel/dim caps),
  video/mp4|video/webm (container check, size cap, NO transcoding).
- Guard decompression bombs (pixel/dimension caps), GIF frame bombs, byte-size caps.
- content_hash = sha256 of the STORED bytes; storage_key is server-generated random
  (never derived from the client filename → no path traversal).
- Persist QuestionMedia metadata ONLY (bytes live in object storage) + optional
  QuestionMediaTranslation alt_text.
"""

from __future__ import annotations

import hashlib
import io
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.enums import Language, MediaType
from app.domain.models import QuestionMedia, QuestionMediaTranslation, User
from app.storage.media_storage import get_media_storage

_ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}  # re-encoded to WebP
_WEBP_CONTENT_TYPE = "image/webp"
_GIF_CONTENT_TYPE = "image/gif"


class MediaValidationError(ValueError):
    """Raised when an upload fails a security/validation check (maps to HTTP 400)."""


def _looks_like_svg(raw: bytes) -> bool:
    head = raw[:1024].lstrip().lstrip(b"\xef\xbb\xbf").lstrip().lower()
    return head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in raw[:1024].lower()


def _sniff_kind(raw: bytes) -> tuple[str, str | None]:
    """Return ('image'|'video'|'unknown', content_type_hint). Magic-byte based only."""
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image", "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image", "image/jpeg"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image", "image/gif"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image", "image/webp"
    if len(raw) >= 12 and raw[4:8] == b"ftyp":
        return "video", "video/mp4"
    if raw[:4] == b"\x1a\x45\xdf\xa3":  # EBML header (webm/mkv)
        return "video", "video/webm"
    return "unknown", None


def _new_storage_key(ext: str) -> str:
    """Server-generated, random, non-user-controlled key under a private prefix."""
    return f"media/{uuid4().hex}{ext}"


def _persist(
    db: Session,
    *,
    media_type: MediaType,
    content_type: str,
    stored_bytes: bytes,
    storage_key: str,
    width: int | None,
    height: int | None,
    duration_ms: int | None,
    poster_storage_key: str | None,
    alt_text_uz: str | None,
) -> QuestionMedia:
    content_hash = hashlib.sha256(stored_bytes).hexdigest()

    # Content-addressed + immutable: identical bytes reuse the existing row/object.
    existing = db.scalar(select(QuestionMedia).where(QuestionMedia.content_hash == content_hash))
    if existing is not None:
        return existing

    get_media_storage().put(storage_key, stored_bytes, content_type)
    media = QuestionMedia(
        media_type=media_type,
        content_type=content_type,
        content_hash=content_hash,
        storage_key=storage_key,
        poster_storage_key=poster_storage_key,
        width=width,
        height=height,
        duration_ms=duration_ms,
        byte_size=len(stored_bytes),
    )
    db.add(media)
    db.flush()
    if alt_text_uz:
        db.add(
            QuestionMediaTranslation(media_id=media.id, language=Language.UZ, alt_text=alt_text_uz)
        )
    db.flush()
    return media


def _ingest_image(db: Session, raw: bytes, alt_text_uz: str | None) -> QuestionMedia:
    from PIL import Image

    try:
        from PIL.Image import DecompressionBombError
    except ImportError:  # pragma: no cover
        DecompressionBombError = Exception  # type: ignore

    settings = get_settings()
    if len(raw) > settings.max_image_bytes:
        raise MediaValidationError("Rasm hajmi juda katta.")

    Image.MAX_IMAGE_PIXELS = settings.max_image_pixels
    try:
        img = Image.open(io.BytesIO(raw))
        width, height = img.size
        fmt = (img.format or "").upper()
    except DecompressionBombError as exc:
        raise MediaValidationError("Rasm piksellari soni chegaradan oshdi (decompression bomb).") from exc
    except Exception as exc:  # noqa: BLE001
        raise MediaValidationError("Rasmni o'qib bo'lmadi.") from exc

    if width <= 0 or height <= 0:
        raise MediaValidationError("Rasm o'lchamlari yaroqsiz.")
    if width > settings.max_image_dimension or height > settings.max_image_dimension:
        raise MediaValidationError("Rasm o'lchamlari juda katta.")
    if width * height > settings.max_image_pixels:
        raise MediaValidationError("Rasm piksellari soni chegaradan oshdi (decompression bomb).")

    if fmt == "GIF":
        return _ingest_gif(db, img, raw, width, height, alt_text_uz)

    if fmt not in _ALLOWED_IMAGE_FORMATS:
        raise MediaValidationError(f"Ruxsat etilmagan rasm turi: {fmt or 'nomalum'}.")

    # Re-encode to WebP (strips metadata / disarms polyglots).
    try:
        rgb = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
        out = io.BytesIO()
        rgb.save(out, format="WEBP", quality=82, method=4)
    except Exception as exc:  # noqa: BLE001
        raise MediaValidationError("Rasmni WebP ga aylantirib bo'lmadi.") from exc

    return _persist(
        db,
        media_type=MediaType.IMAGE,
        content_type=_WEBP_CONTENT_TYPE,
        stored_bytes=out.getvalue(),
        storage_key=_new_storage_key(".webp"),
        width=width,
        height=height,
        duration_ms=None,
        poster_storage_key=None,
        alt_text_uz=alt_text_uz,
    )


def _ingest_gif(db, img, raw, width, height, alt_text_uz) -> QuestionMedia:
    settings = get_settings()
    frames = getattr(img, "n_frames", 1)
    if frames > settings.max_gif_frames:
        raise MediaValidationError("GIF kadrlari soni chegaradan oshdi (frame bomb).")
    if width * height * frames > settings.max_image_pixels * 4:
        raise MediaValidationError("GIF umumiy piksellari chegaradan oshdi.")
    # GIF kept as-is (no transcoding); content-addressed by its bytes.
    return _persist(
        db,
        media_type=MediaType.GIF,
        content_type=_GIF_CONTENT_TYPE,
        stored_bytes=raw,
        storage_key=_new_storage_key(".gif"),
        width=width,
        height=height,
        duration_ms=None,
        poster_storage_key=None,
        alt_text_uz=alt_text_uz,
    )


def _ingest_video(db: Session, raw: bytes, sniffed: str, alt_text_uz: str | None) -> QuestionMedia:
    settings = get_settings()
    if len(raw) > settings.max_video_bytes:
        raise MediaValidationError("Video hajmi juda katta.")
    ext = ".mp4" if sniffed == "video/mp4" else ".webm"
    # NO server transcoding (docs/spec/05). Poster (first-frame still) needs a video
    # decoder (ffmpeg) not guaranteed in v1 -> best-effort None; the frontend falls
    # back to preload="metadata". Duration probing likewise deferred.
    return _persist(
        db,
        media_type=MediaType.VIDEO,
        content_type=sniffed,
        stored_bytes=raw,
        storage_key=_new_storage_key(ext),
        width=None,
        height=None,
        duration_ms=None,
        poster_storage_key=None,
        alt_text_uz=alt_text_uz,
    )


def ingest_upload(
    db: Session,
    *,
    raw: bytes,
    filename: str | None = None,
    client_content_type: str | None = None,
    author: User | None = None,
    alt_text_uz: str | None = None,
) -> QuestionMedia:
    """Validate + store an uploaded media file. Type is sniffed from BYTES only.

    ``filename`` and ``client_content_type`` are accepted for logging only and are
    NEVER trusted for type decisions or storage-key derivation.
    """
    if not raw:
        raise MediaValidationError("Bo'sh fayl.")

    # SVG is rejected outright (script vector) — before any decoder touches it.
    if _looks_like_svg(raw):
        raise MediaValidationError("SVG fayllar qo'llab-quvvatlanmaydi.")

    kind, _hint = _sniff_kind(raw)
    if kind == "image":
        return _ingest_image(db, raw, alt_text_uz)
    if kind == "video":
        sniffed = "video/mp4" if (len(raw) >= 12 and raw[4:8] == b"ftyp") else "video/webm"
        return _ingest_video(db, raw, sniffed, alt_text_uz)

    raise MediaValidationError("Fayl turini aniqlab bo'lmadi yoki u qo'llab-quvvatlanmaydi.")


# --------------------------------------------------------------------------- #
# Read serializer — no-leak media metadata for question-embedding surfaces.
# Returns ONLY presentation metadata (never answer/explanation/rule). Enough for
# the frontend QuestionMedia component to build the content-addressed URL and pick
# an <img> vs <video> renderer with a fixed aspect-ratio box.
# --------------------------------------------------------------------------- #
def media_meta(db: Session, media_id: str | None) -> dict | None:
    """Resolve a QuestionMedia into a small presentation dict, or ``None``.

    Shape: ``{media_id, content_hash, media_type, url, alt, width, height, duration_ms}``.
    The ``url`` is the public content-addressed serving route
    ``/api/media/{id}/{hash}``. Alt text (Uzbek) is included for accessibility.
    """
    if not media_id:
        return None
    media = db.get(QuestionMedia, media_id)
    if media is None:
        return None
    alt_tr = db.scalar(
        select(QuestionMediaTranslation).where(
            QuestionMediaTranslation.media_id == media.id,
            QuestionMediaTranslation.language == Language.UZ,
        )
    )
    return {
        "media_id": media.id,
        "content_hash": media.content_hash,
        "media_type": media.media_type.value,
        "url": f"/api/media/{media.id}/{media.content_hash}",
        "alt": alt_tr.alt_text if alt_tr else None,
        "width": media.width,
        "height": media.height,
        "duration_ms": media.duration_ms,
    }


# --------------------------------------------------------------------------- #
# Admin media library — bulk in-use computation + paginated listing.
# --------------------------------------------------------------------------- #
def referenced_media_ids(db: Session) -> set[str]:
    """All media ids referenced by ANY version/container (published or not).

    Computed as a BULK set (one SELECT DISTINCT per referencing column — a small
    fixed number of queries), NEVER per-row, so callers can test membership in O(1)
    while listing media. Covers question base image + outcome clips, theory section
    icons, article hero/block media, and every catalogue container + its versions.
    """
    from app.domain.models import (
        ControllerGesture,
        ControllerGestureVersion,
        QuestionVersion,
        RoadMarking,
        RoadMarkingVersion,
        RoadSign,
        RoadSignVersion,
        TheoryArticleVersion,
        TheoryContentBlock,
        TheorySection,
        TrafficLightState,
        TrafficLightStateVersion,
    )

    columns = (
        QuestionVersion.media_id,
        QuestionVersion.success_media_id,
        QuestionVersion.fail_media_id,
        TheorySection.icon_media_id,
        TheoryArticleVersion.hero_media_id,
        TheoryContentBlock.media_id,
        RoadSign.media_id,
        RoadSignVersion.media_id,
        RoadMarking.media_id,
        RoadMarkingVersion.media_id,
        ControllerGesture.media_id,
        ControllerGesture.animation_media_id,
        ControllerGestureVersion.media_id,
        ControllerGestureVersion.animation_media_id,
        TrafficLightState.media_id,
        TrafficLightStateVersion.media_id,
    )

    referenced: set[str] = set()
    for col in columns:
        for mid in db.scalars(select(col).where(col.is_not(None)).distinct()):
            if mid:
                referenced.add(mid)
    return referenced


_MEDIA_LIST_MAX_LIMIT = 100  # server-side hard cap (defense-in-depth clamp).


def list_media(
    db: Session,
    *,
    q: str | None = None,
    media_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Paginated admin media listing (newest first) with an ``in_use`` flag.

    - ``limit`` is clamped to [1, 100] (server max), ``offset`` to >= 0.
    - ``q`` is a case-insensitive substring match on content_type OR uz alt_text OR id.
    - ``media_type`` filters by MediaType value ('image'|'gif'|'video'); an invalid
      value raises ValueError (mapped to HTTP 400 in the route).
    - ``in_use`` is resolved against a single bulk set (see ``referenced_media_ids``).
    """
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(_MEDIA_LIST_MAX_LIMIT, limit))
    try:
        offset = int(offset)
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    mt_enum: MediaType | None = None
    if media_type:
        try:
            mt_enum = MediaType(media_type)
        except ValueError as exc:
            raise ValueError(f"Yaroqsiz media turi: {media_type}") from exc

    # LEFT JOIN the uz alt-text translation (unique per (media, language) => no fan-out).
    join_cond = (QuestionMediaTranslation.media_id == QuestionMedia.id) & (
        QuestionMediaTranslation.language == Language.UZ
    )

    conditions = []
    if mt_enum is not None:
        conditions.append(QuestionMedia.media_type == mt_enum)
    if q:
        like = f"%{q.lower()}%"
        conditions.append(
            or_(
                func.lower(QuestionMedia.content_type).like(like),
                func.lower(QuestionMediaTranslation.alt_text).like(like),
                func.lower(QuestionMedia.id).like(like),
            )
        )

    count_stmt = (
        select(func.count(func.distinct(QuestionMedia.id)))
        .select_from(QuestionMedia)
        .outerjoin(QuestionMediaTranslation, join_cond)
    )
    rows_stmt = select(QuestionMedia, QuestionMediaTranslation.alt_text).outerjoin(
        QuestionMediaTranslation, join_cond
    )
    for cond in conditions:
        count_stmt = count_stmt.where(cond)
        rows_stmt = rows_stmt.where(cond)

    total = int(db.scalar(count_stmt) or 0)
    rows_stmt = (
        rows_stmt.order_by(QuestionMedia.created_at.desc(), QuestionMedia.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(rows_stmt).all()

    referenced = referenced_media_ids(db)
    items = [
        {
            "id": media.id,
            "media_type": media.media_type.value,
            "content_type": media.content_type,
            "content_hash": media.content_hash,
            "url": f"/api/media/{media.id}/{media.content_hash}",
            "alt": alt_text or None,
            "width": media.width,
            "height": media.height,
            "duration_ms": media.duration_ms,
            "byte_size": media.byte_size,
            "in_use": media.id in referenced,
            "created_at": media.created_at.isoformat() if media.created_at else None,
        }
        for media, alt_text in rows
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items}
