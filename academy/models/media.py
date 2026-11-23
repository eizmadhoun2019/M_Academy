"""Media assets — ``docs/domain-model.md`` §2.5 and the state machine of §5.

An asset row exists before the bytes do: the upload flow creates it ``awaiting_upload``, hands
the browser a presigned ``PUT``, and only a verified ``stat`` moves it on. ``renditions`` is
written by the pipeline; the object itself is never served through Academy.
"""

from __future__ import annotations

from django.db import models

from academy.models.base import TenantManager, TenantModel


class MediaAsset(TenantModel):
    """One uploaded object (video, cover image or document) of one organization."""

    class Kind(models.TextChoices):
        VIDEO = "video", "Video"
        IMAGE = "image", "Image"
        DOCUMENT = "document", "Document"

    class Status(models.TextChoices):
        AWAITING_UPLOAD = "awaiting_upload", "Awaiting upload"
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.VIDEO)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_UPLOAD)
    storage_key = models.CharField(max_length=512, null=True, blank=True)  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    original_filename = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    content_type = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    size_bytes = models.BigIntegerField(null=True, blank=True)
    checksum_sha256 = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    duration_seconds = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    renditions = models.JSONField(default=dict)
    error_code = models.CharField(max_length=40, null=True, blank=True)  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    attempt_count = models.SmallIntegerField(default=0)
    ready_at = models.DateTimeField(null=True, blank=True)
    created_by_ref = models.CharField(max_length=64)
    objects: TenantManager[MediaAsset] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=["video", "image", "document"]),
                name="media_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["awaiting_upload", "uploaded", "processing", "ready", "failed"]
                ),
                name="media_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="ready") | models.Q(storage_key__isnull=False),
                name="media_ready_has_key",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(kind="video")
                    | ~models.Q(status="ready")
                    | models.Q(duration_seconds__gt=0)
                ),
                name="media_video_ready_duration",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="failed") | models.Q(error_code__isnull=False),
                name="media_failed_has_error",
            ),
            models.CheckConstraint(
                condition=models.Q(size_bytes__isnull=True) | models.Q(size_bytes__gte=0),
                name="media_size_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["organization_id", "status"], name="media_org_status"),
            models.Index(fields=["organization_id", "created_at"], name="media_org_created"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.id}"
