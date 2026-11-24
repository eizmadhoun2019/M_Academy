"""Catalog — ``docs/domain-model.md`` §2.1–§2.4.

Course → CourseVersion → Section → Lesson. A version is the unit of publishing: once
``published`` its content is frozen (a database trigger, not a service promise), and at most one
version of a course is published at a time (a partial unique index). There is deliberately no
``Course.published_version`` column; the published version is derived from ``CourseVersion``.
"""

from __future__ import annotations

from django.db import models

from academy.models.base import TenantManager, TenantModel
from academy.models.media import MediaAsset

TITLE_NOT_BLANK = r"\S"


class Course(TenantModel):
    """Container for versions; the learner-facing unit."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=200)
    description = models.TextField(default="", blank=True)
    # D-013: NULL means a general course that only a platform admin may edit.
    owner_department_ref = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_by_ref = models.CharField(max_length=64)
    objects: TenantManager[Course] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "published", "archived"]),
                name="course_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(title__regex=TITLE_NOT_BLANK),
                name="course_title_not_blank",
            ),
        ]
        indexes = [
            models.Index(fields=["organization_id", "status"], name="course_org_status"),
            models.Index(
                fields=["organization_id", "owner_department_ref"], name="course_org_dept"
            ),
        ]

    def __str__(self) -> str:
        return self.title


class CourseVersion(TenantModel):
    """A snapshot of a course; immutable once published (§2.2, ADR-004)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    course = models.ForeignKey(Course, on_delete=models.RESTRICT, related_name="versions")
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    acknowledgment_required = models.BooleanField(default=False)
    cover_media = models.ForeignKey(
        MediaAsset,
        on_delete=models.PROTECT,
        related_name="cover_versions",
        null=True,
        blank=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by_ref = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    created_by_ref = models.CharField(max_length=64)
    objects: TenantManager[CourseVersion] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "version_number"], name="version_number_per_course"
            ),
            models.UniqueConstraint(
                fields=["course"],
                condition=models.Q(status="published"),
                name="version_one_published",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "published", "archived"]),
                name="version_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(version_number__gte=1), name="version_number_positive"
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status="published")
                    | (
                        models.Q(published_at__isnull=False)
                        & models.Q(published_by_ref__isnull=False)
                    )
                ),
                name="version_published_stamped",
            ),
        ]
        indexes = [
            models.Index(fields=["organization_id", "course"], name="version_org_course"),
            models.Index(
                fields=["organization_id"],
                name="version_org_published",
                condition=models.Q(status="published"),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.course} v{self.version_number}"


class Section(TenantModel):
    """An ordered group of lessons inside one version."""

    version = models.ForeignKey(CourseVersion, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=200)
    position = models.PositiveIntegerField()
    objects: TenantManager[Section] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "position"],
                name="section_position_per_version",
                deferrable=models.Deferrable.DEFERRED,
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1), name="section_position_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(title__regex=TITLE_NOT_BLANK),
                name="section_title_not_blank",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class Lesson(TenantModel):
    """A video, text or PDF lesson inside one section."""

    class ContentType(models.TextChoices):
        VIDEO = "video", "Video"
        TEXT = "text", "Text"
        PDF = "pdf", "PDF"

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=200)
    # D-016.
    summary = models.CharField(max_length=300, null=True, blank=True)  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    body = models.TextField(null=True, blank=True, default="")  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    position = models.PositiveIntegerField()
    content_type = models.CharField(
        max_length=16, choices=ContentType.choices, default=ContentType.VIDEO
    )
    media_asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.PROTECT,
        related_name="lessons",
        null=True,
        blank=True,
    )
    required = models.BooleanField(default=True)
    required_watch_percent = models.SmallIntegerField(default=90)
    objects: TenantManager[Lesson] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["section", "position"],
                name="lesson_position_per_section",
                deferrable=models.Deferrable.DEFERRED,
            ),
            models.CheckConstraint(
                condition=models.Q(content_type__in=["video", "text", "pdf"]),
                name="lesson_content_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1), name="lesson_position_positive"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(required_watch_percent__gte=50)
                    & models.Q(required_watch_percent__lte=100)
                ),
                name="lesson_watch_percent_range",
            ),
            models.CheckConstraint(
                condition=models.Q(title__regex=TITLE_NOT_BLANK),
                name="lesson_title_not_blank",
            ),
            models.CheckConstraint(
                condition=~models.Q(content_type="pdf") | models.Q(body__isnull=False),
                name="lesson_pdf_has_body",
            ),
        ]

    def __str__(self) -> str:
        return self.title
