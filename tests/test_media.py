"""T-018 acceptance: upload policy, ``stat`` verification, the HLS pipeline and playback.

The storage seam runs against ``InMemoryStorage``; the pipeline is exercised with a real
``ffmpeg``/``ffprobe`` run on a two-second generated clip, so a playlist that exists in the
bucket is proof the worker produced it. The slow test is marked ``slow`` and skips when
``ffmpeg`` is missing from the image.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any
from uuid import UUID

import pytest
from django.test import override_settings
from factories import make_course, make_enrollment, make_lesson, make_section, make_version

from academy.authorization.core import Access, Capability, Principal, Scope
from academy.exceptions import MediaUploadError, NotFound, StateConflict
from academy.media import service
from academy.models import MediaAsset
from host_stub.storage import InMemoryStorage

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

pytestmark = pytest.mark.django_db


def access(**overrides: Any) -> Access:
    principal = Principal(
        user_ref="u-manager", organization_id=ORG, department_refs=frozenset({"dep-1"})
    )
    granted = {capability: Scope.everything() for capability in Capability}
    for key, value in overrides.items():
        setattr(principal, key, value)
    return Access(principal=principal, capabilities=granted)


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch) -> InMemoryStorage:
    store = InMemoryStorage()
    monkeypatch.setattr(service, "_storage", lambda: store)
    return store


@pytest.fixture
def clip(tmp_path: Any) -> bytes:
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg is not installed")
    target = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=320x240:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-shortest",
            str(target),
        ],
        capture_output=True,
        check=True,
    )
    return target.read_bytes()


# --- upload policy ----------------------------------------------------------


def test_upload_creates_an_awaiting_asset_with_a_tenant_key(storage: InMemoryStorage) -> None:
    asset = service.create_upload(
        access(),
        kind="video",
        original_filename="../Lesson one.mp4",
        content_type="video/mp4",
        size_bytes=1024,
    )

    assert asset.status == MediaAsset.Status.AWAITING_UPLOAD
    assert asset.original_filename == "Lesson one.mp4"
    assert asset.storage_key == f"org/{ORG}/media/{asset.pk}/original.mp4"
    assert service.presigned_upload_url(asset).startswith("memory://academy/org/")


def test_an_oversized_upload_is_refused_before_it_is_stored(storage: InMemoryStorage) -> None:
    with (
        override_settings(ACADEMY_UPLOAD_MAX_IMAGE_BYTES=100),
        pytest.raises(MediaUploadError) as error,
    ):
        service.create_upload(
            access(),
            kind="image",
            original_filename="cover.png",
            content_type="image/png",
            size_bytes=101,
        )
    assert error.value.code == "upload_too_large"
    assert not MediaAsset.objects.exists()


def test_a_content_type_outside_the_allowlist_is_refused(storage: InMemoryStorage) -> None:
    with pytest.raises(MediaUploadError) as error:
        service.create_upload(
            access(),
            kind="video",
            original_filename="clip.avi",
            content_type="video/x-msvideo",
            size_bytes=10,
        )
    assert error.value.code == "unsupported_type"


# --- stat verification ------------------------------------------------------


def test_complete_verifies_the_object_with_stat(storage: InMemoryStorage) -> None:
    asset = service.create_upload(
        access(),
        kind="image",
        original_filename="cover.png",
        content_type="image/png",
        size_bytes=5,
    )
    storage.put(asset.storage_key or "", b"12345", content_type="image/png")

    done = service.complete_upload(access(), asset, storage=storage)

    assert done.status == MediaAsset.Status.UPLOADED
    assert done.size_bytes == 5


def test_a_missing_object_is_reported_as_upload_missing(storage: InMemoryStorage) -> None:
    asset = service.create_upload(
        access(),
        kind="image",
        original_filename="cover.png",
        content_type="image/png",
        size_bytes=5,
    )

    with pytest.raises(StateConflict) as error:
        service.complete_upload(access(), asset, storage=storage)

    assert error.value.code == "upload_missing"


def test_a_size_mismatch_is_a_checksum_mismatch(storage: InMemoryStorage) -> None:
    asset = service.create_upload(
        access(),
        kind="image",
        original_filename="cover.png",
        content_type="image/png",
        size_bytes=99,
    )
    storage.put(asset.storage_key or "", b"12345", content_type="image/png")

    with pytest.raises(StateConflict) as error:
        service.complete_upload(access(), asset, storage=storage)

    assert error.value.code == "checksum_mismatch"


def test_an_asset_of_another_tenant_is_not_found(storage: InMemoryStorage) -> None:
    asset = service.create_upload(
        access(),
        kind="image",
        original_filename="cover.png",
        content_type="image/png",
        size_bytes=1,
    )
    outsider = Access(
        principal=Principal(
            user_ref="u-other",
            organization_id=UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11"),
            department_refs=frozenset(),
        ),
        capabilities={capability: Scope.everything() for capability in Capability},
    )

    with pytest.raises(NotFound):
        service.require_asset(outsider, outsider.principal.organization_id, asset.pk)


# --- pipeline ---------------------------------------------------------------


@pytest.mark.slow
def test_the_pipeline_writes_hls_playlists_and_segments(
    storage: InMemoryStorage, clip: bytes
) -> None:
    asset = service.create_upload(
        access(),
        kind="video",
        original_filename="lesson.mp4",
        content_type="video/mp4",
        size_bytes=len(clip),
    )
    storage.put(asset.storage_key or "", clip, content_type="video/mp4")
    service.complete_upload(access(), asset, storage=storage)
    service.process_asset(str(asset.pk), str(ORG))

    asset.refresh_from_db()

    assert asset.status == MediaAsset.Status.READY, asset.error_code
    assert float(asset.duration_seconds or 0) > 0
    prefixes = f"org/{ORG}/media/{asset.pk}/hls/"
    stored = list(storage.keys())
    playlists = [key for key in stored if key.startswith(prefixes) and key.endswith("index.m3u8")]
    segments = [key for key in stored if key.startswith(prefixes) and key.endswith(".ts")]
    assert playlists, stored
    assert segments, stored
    assert "360p" in asset.renditions
    assert asset.renditions["360p"]["playlist"].endswith("index.m3u8")


@pytest.mark.slow
def test_a_ready_asset_is_never_reprocessed(storage: InMemoryStorage, clip: bytes) -> None:
    asset = service.create_upload(
        access(),
        kind="video",
        original_filename="lesson.mp4",
        content_type="video/mp4",
        size_bytes=len(clip),
    )
    storage.put(asset.storage_key or "", clip, content_type="video/mp4")
    service.complete_upload(access(), asset, storage=storage)
    service.process_asset(str(asset.pk), str(ORG))
    asset.refresh_from_db()
    attempts = asset.attempt_count

    service.process_asset(str(asset.pk), str(ORG))

    asset.refresh_from_db()
    assert asset.status == MediaAsset.Status.READY
    assert asset.attempt_count == attempts


def test_a_missing_object_fails_with_a_stable_error_code(storage: InMemoryStorage) -> None:
    asset = service.create_upload(
        access(),
        kind="video",
        original_filename="lesson.mp4",
        content_type="video/mp4",
        size_bytes=10,
    )
    asset.status = MediaAsset.Status.UPLOADED
    asset.save(update_fields=["status"])

    service.process_asset(str(asset.pk), str(ORG))

    asset.refresh_from_db()
    assert asset.status == MediaAsset.Status.FAILED
    assert asset.error_code == "storage_unavailable"


def test_retry_is_capped_by_the_configured_attempts(storage: InMemoryStorage) -> None:
    asset = service.create_upload(
        access(),
        kind="video",
        original_filename="lesson.mp4",
        content_type="video/mp4",
        size_bytes=1,
    )
    asset.status = MediaAsset.Status.FAILED
    asset.error_code = "transcode_failed"
    asset.attempt_count = 3
    asset.save(update_fields=["status", "error_code", "attempt_count"])

    with pytest.raises(StateConflict) as error:
        service.retry_upload(access(), asset, storage=storage)

    assert error.value.code == "retry_limit_reached"


def test_retry_requeues_a_failed_asset(storage: InMemoryStorage) -> None:
    asset = service.create_upload(
        access(),
        kind="video",
        original_filename="lesson.mp4",
        content_type="video/mp4",
        size_bytes=1,
    )
    asset.status = MediaAsset.Status.FAILED
    asset.error_code = "transcode_failed"
    asset.attempt_count = 1
    asset.save(update_fields=["status", "error_code", "attempt_count"])

    retried = service.retry_upload(access(), asset, storage=storage)

    assert retried.error_code is None
    assert retried.status in {MediaAsset.Status.UPLOADED, MediaAsset.Status.FAILED}


# --- playback ---------------------------------------------------------------


def _enrollment(user_ref: str) -> Any:
    course = make_course(ORG)
    version = make_version(ORG, course=course)
    section = make_section(ORG, version=version, position=1)
    lesson = make_lesson(ORG, section=section, content_type="video", body=None, position=1)
    enrollment = make_enrollment(ORG, course=course, version=version, user_ref=user_ref)
    return enrollment, lesson


def test_playback_returns_presigned_playlists_for_a_ready_asset(
    storage: InMemoryStorage,
) -> None:
    enrollment, lesson = _enrollment("u-manager")
    asset = service.create_upload(
        access(),
        kind="video",
        original_filename="lesson.mp4",
        content_type="video/mp4",
        size_bytes=10,
    )
    asset.status = MediaAsset.Status.READY
    asset.storage_key = asset.storage_key or f"org/{ORG}/media/{asset.pk}/original.mp4"
    asset.duration_seconds = 120
    asset.renditions = {"360p": {"playlist": "hls/360p/index.m3u8"}}
    asset.save()
    lesson.media_asset = asset
    lesson.save(update_fields=["media_asset"])

    payload = service.playback_urls(access(), enrollment.pk, lesson.pk)

    assert "360p" in payload["renditions"]
    assert payload["renditions"]["360p"].startswith("memory://academy/")
    assert payload["ttl_seconds"] >= 360


def test_playback_refuses_an_asset_that_is_not_ready(storage: InMemoryStorage) -> None:
    enrollment, lesson = _enrollment("u-manager")
    asset = service.create_upload(
        access(),
        kind="video",
        original_filename="lesson.mp4",
        content_type="video/mp4",
        size_bytes=10,
    )
    lesson.media_asset = asset
    lesson.save(update_fields=["media_asset"])

    with pytest.raises(StateConflict) as error:
        service.playback_urls(access(), enrollment.pk, lesson.pk)

    assert error.value.code == "media_not_ready"


def test_playback_of_another_learners_enrollment_is_not_found(storage: InMemoryStorage) -> None:
    enrollment, lesson = _enrollment("u-someone-else")

    with pytest.raises(NotFound):
        service.playback_urls(access(), enrollment.pk, lesson.pk)
