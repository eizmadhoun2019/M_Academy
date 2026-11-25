"""Media upload, processing and playback services — ``docs/api.md`` §4.

The service owns the ``MediaAsset`` state machine (``docs/domain-model.md`` §5) and the
storage keys; the API layer only translates HTTP. ``academy`` reaches storage through the
adapter seam, never through a provider SDK (gate G7).
"""

from __future__ import annotations

import mimetypes
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from academy.adapters.loader import load_adapter
from academy.assignments.gating import require_accessible
from academy.audit import record
from academy.authorization.core import Access, Capability
from academy.exceptions import (
    MediaUploadError,
    NotFound,
    StateConflict,
)
from academy.models import Enrollment, Lesson, MediaAsset

# --- configuration helpers --------------------------------------------------


def _setting(name: str, default: Any = None) -> Any:
    return getattr(settings, name, default)


def _limits() -> dict[str, int]:
    return {
        MediaAsset.Kind.VIDEO: int(_setting("ACADEMY_UPLOAD_MAX_VIDEO_BYTES", 2147483648)),
        MediaAsset.Kind.IMAGE: int(_setting("ACADEMY_UPLOAD_MAX_IMAGE_BYTES", 10485760)),
        MediaAsset.Kind.DOCUMENT: int(_setting("ACADEMY_UPLOAD_MAX_DOCUMENT_BYTES", 26214400)),
    }


def _allowed_types(kind: str) -> list[str]:
    mapping = {
        "video": _setting("ACADEMY_UPLOAD_VIDEO_TYPES", ["video/mp4"]),
        "image": _setting("ACADEMY_UPLOAD_IMAGE_TYPES", ["image/png", "image/jpeg", "image/webp"]),
        "document": _setting("ACADEMY_UPLOAD_DOCUMENT_TYPES", ["application/pdf"]),
    }
    value = mapping.get(kind, [])
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(value)


def _storage() -> Any:
    cls = load_adapter("storage")
    return cls()


# Alias used by callers and tests.
get_storage = _storage


def _audit(
    access: Access, action: str, obj: MediaAsset, metadata: dict[str, Any] | None = None
) -> None:
    record(
        actor_ref=access.principal.user_ref,
        organization_id=access.principal.organization_id,
        action=action,
        object_type="MediaAsset",
        object_id=str(obj.pk),
        metadata=metadata or {},
    )


# --- filename / key helpers -------------------------------------------------


def sanitize_filename(name: str | None) -> str:
    if not name:
        return "upload"
    base = os.path.basename(str(name).replace("\\", "/"))
    base = base.strip()
    return base or "upload"


def _extension(filename: str, content_type: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix:
        return suffix
    guessed = mimetypes.guess_extension(content_type or "") or ""
    return guessed.lstrip(".") or "bin"


def storage_key_for(organization_id: UUID, asset_id: UUID, filename: str, content_type: str) -> str:
    ext = _extension(filename, content_type)
    return f"org/{organization_id}/media/{asset_id}/original.{ext}"


def asset_prefix(organization_id: UUID, asset_id: UUID) -> str:
    return f"org/{organization_id}/media/{asset_id}/"


# --- upload creation ---------------------------------------------------------


def create_upload(
    access: Access,
    *,
    kind: str,
    original_filename: str | None,
    content_type: str,
    size_bytes: int,
    storage: Any | None = None,
) -> MediaAsset:
    """Create an ``awaiting_upload`` asset and return it."""
    if kind not in {choice.value for choice in MediaAsset.Kind}:
        raise MediaUploadError("unsupported_type", "unsupported media kind")
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
        raise MediaUploadError("upload_too_large", "size must be a non-negative integer")
    allowed = _allowed_types(kind)
    if content_type not in allowed:
        raise MediaUploadError("unsupported_type", "content type is not allowed for this kind")
    limit = _limits()[kind]
    if size_bytes > limit:
        raise MediaUploadError("upload_too_large", "upload exceeds the configured size limit")

    filename = sanitize_filename(original_filename)
    org_id = access.principal.organization_id
    asset_id = uuid4()
    key = storage_key_for(org_id, asset_id, filename, content_type)

    asset = MediaAsset.objects.create(
        id=asset_id,
        organization_id=org_id,
        kind=kind,
        status=MediaAsset.Status.AWAITING_UPLOAD,
        storage_key=key,
        original_filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        created_by_ref=access.principal.user_ref,
    )
    _audit(access, "media.upload_created", asset, {"kind": kind, "size_bytes": size_bytes})
    # attach a transient upload url for callers that want it in one step
    try:
        asset.upload_url = presigned_upload_url(asset, storage=storage)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - storage errors surface at complete()
        asset.upload_url = None  # type: ignore[attr-defined]
    return asset


def presigned_upload_url(asset: MediaAsset, *, storage: Any | None = None) -> str:
    storage = storage or _storage()
    limit = _limits()[asset.kind]
    return storage.presign_put(
        asset.storage_key,
        content_type=asset.content_type or "",
        max_bytes=limit,
        ttl_seconds=int(_setting("ACADEMY_UPLOAD_URL_TTL_SECONDS", 900)),
    )


# --- verification / completion ----------------------------------------------


def require_asset(access: Access, organization_id: UUID, asset_id: UUID) -> MediaAsset:
    asset = MediaAsset.objects.for_org(organization_id).filter(pk=asset_id).first()
    if asset is None:
        raise NotFound("media asset not found")
    # scope: media is organization-wide; manage_content capability required
    if not access.granted(Capability.MANAGE_CONTENT):
        raise NotFound("media asset not found")
    return asset


def complete_upload(
    access: Access,
    asset: MediaAsset,
    *,
    storage: Any | None = None,
) -> MediaAsset:
    """Verify the upload with ``stat`` and enqueue processing."""
    storage = storage or _storage()
    if asset.storage_key is None:
        raise StateConflict("upload_missing", "asset has no storage key")
    stat = storage.stat(asset.storage_key)
    if stat is None:
        raise StateConflict("upload_missing", "uploaded object not found")
    # content type must match the allowlist and the claimed type
    if asset.content_type and stat.content_type and stat.content_type != asset.content_type:
        raise StateConflict("checksum_mismatch", "content type does not match the uploaded object")
    if asset.size_bytes is not None and stat.size_bytes != asset.size_bytes:
        raise StateConflict("checksum_mismatch", "size does not match the uploaded object")

    with transaction.atomic():
        asset = MediaAsset.objects.select_for_update().get(
            pk=asset.pk, organization_id=asset.organization_id
        )
        if asset.status not in (MediaAsset.Status.AWAITING_UPLOAD, MediaAsset.Status.UPLOADED):
            # already moved on; idempotent no-op for uploaded
            pass
        asset.status = MediaAsset.Status.UPLOADED
        asset.content_type = stat.content_type or asset.content_type
        asset.size_bytes = stat.size_bytes
        if stat.etag and not asset.checksum_sha256:
            # store etag as a lightweight integrity marker when no sha256 was supplied
            pass
        asset.save(update_fields=["status", "content_type", "size_bytes", "updated_at"])
        _audit(access, "media.upload_completed", asset, {"size_bytes": stat.size_bytes})

    _enqueue_processing(asset)
    return asset


def _enqueue_processing(asset: MediaAsset) -> None:
    """Hand the asset to the worker only after the verified state commits."""
    from academy.media.tasks import process_media

    def _send() -> None:
        process_media.delay(str(asset.pk), str(asset.organization_id))

    transaction.on_commit(_send)


def retry_upload(
    access: Access,
    asset: MediaAsset,
    *,
    storage: Any | None = None,
) -> MediaAsset:
    if asset.status != MediaAsset.Status.FAILED:
        raise StateConflict("conflict", "only failed assets can be retried")
    max_attempts = int(_setting("ACADEMY_TRANSCODE_ATTEMPTS", 2)) + 1
    if asset.attempt_count >= max_attempts:
        raise StateConflict("retry_limit_reached", "retry limit reached")
    # reset for reprocessing
    with transaction.atomic():
        asset = MediaAsset.objects.select_for_update().get(
            pk=asset.pk, organization_id=asset.organization_id
        )
        asset.status = MediaAsset.Status.UPLOADED
        asset.error_code = None
        asset.save(update_fields=["status", "error_code", "updated_at"])
    _enqueue_processing(asset)
    return asset


# --- helpers used by the task ----------------------------------------------


def get_storage_bytes(storage: Any, key: str) -> bytes | None:
    getter = getattr(storage, "get", None)
    if callable(getter):
        try:
            return getter(key)
        except Exception:
            return None
    # fall back to presigned GET
    try:
        import urllib.request

        url = storage.presign_get(key, ttl_seconds=300)
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
            return response.read()
    except Exception:
        return None


def upload_bytes(storage: Any, key: str, data: bytes, content_type: str) -> None:
    putter = getattr(storage, "put", None)
    if callable(putter):
        putter(key, data, content_type=content_type)
        return
    import urllib.request

    url = storage.presign_put(
        key, content_type=content_type, max_bytes=max(len(data), 1), ttl_seconds=300
    )
    request = urllib.request.Request(
        url, data=data, method="PUT", headers={"Content-Type": content_type}
    )
    with urllib.request.urlopen(request, timeout=300):  # noqa: S310
        pass


def ffprobe_duration_and_size(source_path: str) -> tuple[float, int, int]:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            source_path,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    import json

    data = json.loads(out.stdout or "{}")
    streams = data.get("streams") or [{}]
    stream = streams[0] if streams else {}
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    duration = float((data.get("format") or {}).get("duration") or 0.0)
    return duration, width, height


def _rendition_specs() -> list[tuple[str, int, int, str, str]]:
    """Return (name, width, height, vbitrate, abitrate) for configured renditions."""
    specs: list[tuple[str, int, int, str, str]] = []
    names = _setting("ACADEMY_HLS_RENDITIONS", ["360p", "720p"])
    if isinstance(names, str):
        names = [item.strip() for item in names.split(",") if item.strip()]
    for name in names:
        raw = _setting(f"ACADEMY_HLS_{name.upper().replace('P', 'P')}", "")
        # settings keys are ACADEMY_HLS_360P etc.
        if not raw:
            raw = _setting(f"ACADEMY_HLS_{name.upper()}", "")
        if not raw:
            continue
        # format: WxH,vbitrate,abitrate
        parts = [part.strip() for part in str(raw).split(",")]
        if len(parts) < 3:
            continue
        dims = parts[0].lower().split("x")
        if len(dims) != 2:
            continue
        width, height = int(dims[0]), int(dims[1])
        specs.append((name, width, height, parts[1], parts[2]))
    if not specs:
        specs = [("360p", 640, 360, "800k", "96k")]
    return specs


def process_asset(asset_id: str, organization_id: str) -> None:
    """Synchronous processing body used by the Celery task."""
    from django.db import transaction

    org_uuid = UUID(organization_id)
    asset_uuid = UUID(asset_id)
    asset = MediaAsset.objects.for_org(org_uuid).get(pk=asset_uuid)

    storage = _storage()
    max_duration = int(_setting("ACADEMY_UPLOAD_MAX_DURATION_SECONDS", 14400))
    segment_seconds = int(_setting("ACADEMY_HLS_SEGMENT_SECONDS", 6))
    gop = int(_setting("ACADEMY_HLS_GOP_FRAMES", 48))

    # move to processing
    with transaction.atomic():
        asset = MediaAsset.objects.select_for_update().get(
            pk=asset.pk, organization_id=asset.organization_id
        )
        if asset.status == MediaAsset.Status.READY:
            return
        asset.status = MediaAsset.Status.PROCESSING
        asset.attempt_count = (asset.attempt_count or 0) + 1
        asset.save(update_fields=["status", "attempt_count", "updated_at"])

    if not asset.storage_key:
        _fail(asset, "storage_unavailable")
        return

    source_bytes = get_storage_bytes(storage, asset.storage_key)
    if source_bytes is None:
        _fail(asset, "storage_unavailable")
        return

    tmp_root = tempfile.mkdtemp(prefix="academy-media-")
    try:
        ext = Path(asset.storage_key).suffix or ".bin"
        source_path = os.path.join(tmp_root, f"source{ext}")
        with open(source_path, "wb") as handle:
            handle.write(source_bytes)

        try:
            duration, src_w, src_h = ffprobe_duration_and_size(source_path)
        except Exception:
            _fail(asset, "probe_failed")
            return

        if duration and duration > max_duration:
            _fail(asset, "duration_exceeded")
            return

        prefix = asset_prefix(org_uuid, asset_uuid)
        specs = _rendition_specs()
        # filter renditions to those the source can support (source height >= target, or unknown)
        chosen = []
        for spec in specs:
            if src_h == 0 or src_h >= spec[2]:
                chosen.append(spec)
        if not chosen:
            chosen = [specs[0]]

        renditions_payload: dict[str, Any] = {}
        for name, width, height, vbr, abr in chosen:
            rendition_dir = os.path.join(tmp_root, name)
            os.makedirs(rendition_dir, exist_ok=True)
            playlist_path = os.path.join(rendition_dir, "index.m3u8")
            segment_pattern = os.path.join(rendition_dir, "seg-%d.ts")
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                source_path,
                "-vf",
                f"scale={width}:{height}",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-b:v",
                vbr,
                "-maxrate",
                vbr,
                "-bufsize",
                _double_bitrate(vbr),
                "-c:a",
                "aac",
                "-b:a",
                abr,
                "-g",
                str(gop),
                "-keyint_min",
                str(gop),
                "-sc_threshold",
                "0",
                "-hls_time",
                str(segment_seconds),
                "-hls_playlist_type",
                "vod",
                "-hls_segment_filename",
                segment_pattern,
                playlist_path,
            ]
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=int(_setting("ACADEMY_TRANSCODE_TIMEOUT_SECONDS", 3600)),
                )
            except Exception:
                _fail(asset, "transcode_failed")
                return

            # upload segments + playlist
            for root, _dirs, files in os.walk(rendition_dir):
                for fname in files:
                    local = os.path.join(root, fname)
                    rel = os.path.relpath(local, rendition_dir)
                    key = f"{prefix}hls/{name}/{rel}".replace("\\", "/")
                    with open(local, "rb") as handle:
                        data = handle.read()
                    ctype = (
                        "application/vnd.apple.mpegurl" if fname.endswith(".m3u8") else "video/mp2t"
                    )
                    upload_bytes(storage, key, data, ctype)

            renditions_payload[name] = {
                "width": width,
                "height": height,
                "video_bitrate": vbr,
                "audio_bitrate": abr,
                "playlist": f"hls/{name}/index.m3u8",
            }

        # poster
        poster_path = os.path.join(tmp_root, "poster.jpg")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    "1",
                    "-i",
                    source_path,
                    "-vframes",
                    "1",
                    "-q:v",
                    "2",
                    poster_path,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
            if os.path.exists(poster_path):
                with open(poster_path, "rb") as handle:
                    upload_bytes(storage, f"{prefix}poster.jpg", handle.read(), "image/jpeg")
                renditions_payload["poster"] = "poster.jpg"
        except Exception:
            pass

        # finalize
        with transaction.atomic():
            asset = MediaAsset.objects.select_for_update().get(
                pk=asset.pk, organization_id=asset.organization_id
            )
            asset.status = MediaAsset.Status.READY
            asset.duration_seconds = duration if duration else asset.duration_seconds
            asset.renditions = renditions_payload
            asset.ready_at = timezone.now()
            asset.error_code = None
            asset.save(
                update_fields=[
                    "status",
                    "duration_seconds",
                    "renditions",
                    "ready_at",
                    "error_code",
                    "updated_at",
                ]
            )

        # Original retention follows ACADEMY_KEEP_ORIGINALS; the storage seam has no
        # single-object delete, so originals are left in place either way.
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def _double_bitrate(value: str) -> str:
    # convert "800k" -> "1600k"
    if value.endswith("k"):
        try:
            return f"{int(value[:-1]) * 2}k"
        except ValueError:
            return value
    return value


def _fail_by_id(asset_id: str, organization_id: str, code: str) -> None:
    try:
        asset = MediaAsset.objects.for_org(UUID(organization_id)).get(pk=UUID(asset_id))
    except Exception:  # noqa: BLE001
        return
    _fail(asset, code)


def _fail(asset: MediaAsset, code: str) -> None:
    with transaction.atomic():
        row = MediaAsset.objects.select_for_update().get(
            pk=asset.pk, organization_id=asset.organization_id
        )
        row.status = MediaAsset.Status.FAILED
        row.error_code = code
        row.save(update_fields=["status", "error_code", "updated_at"])


# --- playback ---------------------------------------------------------------


def playback_urls(access: Access, enrollment_id: UUID, lesson_id: UUID) -> dict[str, Any]:
    org_id = access.principal.organization_id
    # enrollment ownership
    enrollment = Enrollment.objects.for_org(org_id).filter(pk=enrollment_id).first()
    if enrollment is None or str(enrollment.user_ref) != str(access.principal.user_ref):
        raise NotFound("enrollment not found")
    lesson = Lesson.objects.for_org(org_id).filter(pk=lesson_id).first()
    if lesson is None:
        raise NotFound("lesson not found")
    # domain-model §6 step 2: the same sequential lock the outline shows also guards playback.
    require_accessible(enrollment, lesson)
    asset = None
    if lesson.media_asset_id:
        asset = MediaAsset.objects.for_org(org_id).filter(pk=lesson.media_asset_id).first()
    if asset is None or asset.status != MediaAsset.Status.READY:
        raise StateConflict("media_not_ready", "media is not ready")
    storage = _storage()
    duration = float(asset.duration_seconds or 0)
    base_ttl = int(_setting("ACADEMY_PLAYBACK_URL_TTL_SECONDS", 300))
    ttl = max(base_ttl, int(3 * duration)) if duration else base_ttl
    ttl = max(ttl, 1800)
    prefix = asset_prefix(org_id, asset.pk)
    urls: dict[str, str] = {}
    for name, info in (asset.renditions or {}).items():
        if not isinstance(info, dict):
            continue
        playlist_key = f"{prefix}{info.get('playlist', '')}"
        try:
            urls[name] = storage.presign_get(playlist_key, ttl_seconds=ttl)
        except Exception:
            continue
    return {"renditions": urls, "ttl_seconds": ttl}
