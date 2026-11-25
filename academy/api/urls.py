"""`/api/v1/academy/` routes (``docs/api.md`` §1)."""

from __future__ import annotations

from django.urls import path

from academy.api.content import (
    CourseArchiveView,
    CourseCloneView,
    CourseDetailView,
    CourseListCreateView,
    LessonDetailView,
    LessonReorderView,
    SectionDetailView,
    SectionLessonsView,
    SectionReorderView,
    VersionDetailView,
    VersionDiscardView,
    VersionPublishView,
    VersionSectionsView,
)
from academy.api.grants import GrantListCreateView, GrantRevokeView
from academy.api.views import MeCapabilitiesView

app_name = "academy_api"

urlpatterns = [
    path("me/capabilities/", MeCapabilitiesView.as_view(), name="me-capabilities"),
    path("manage/grants/", GrantListCreateView.as_view(), name="manage-grants"),
    path("manage/grants/<uuid:grant_id>/", GrantRevokeView.as_view(), name="manage-grant"),
    path("manage/courses/", CourseListCreateView.as_view(), name="manage-courses"),
    path("manage/courses/<uuid:course_id>/", CourseDetailView.as_view(), name="manage-course"),
    path(
        "manage/courses/<uuid:course_id>/archive/",
        CourseArchiveView.as_view(),
        name="manage-course-archive",
    ),
    path(
        "manage/courses/<uuid:course_id>/versions/",
        CourseCloneView.as_view(),
        name="manage-course-versions",
    ),
    path("manage/versions/<uuid:version_id>/", VersionDetailView.as_view(), name="manage-version"),
    path(
        "manage/versions/<uuid:version_id>/publish/",
        VersionPublishView.as_view(),
        name="manage-version-publish",
    ),
    path(
        "manage/versions/<uuid:version_id>/discard/",
        VersionDiscardView.as_view(),
        name="manage-version-discard",
    ),
    path(
        "manage/versions/<uuid:version_id>/sections/",
        VersionSectionsView.as_view(),
        name="manage-version-sections",
    ),
    path(
        "manage/versions/<uuid:version_id>/sections/reorder/",
        SectionReorderView.as_view(),
        name="manage-version-sections-reorder",
    ),
    path(
        "manage/sections/<uuid:section_id>/",
        SectionDetailView.as_view(),
        name="manage-section",
    ),
    path(
        "manage/sections/<uuid:section_id>/lessons/",
        SectionLessonsView.as_view(),
        name="manage-section-lessons",
    ),
    path(
        "manage/sections/<uuid:section_id>/lessons/reorder/",
        LessonReorderView.as_view(),
        name="manage-section-lessons-reorder",
    ),
    path("manage/lessons/<uuid:lesson_id>/", LessonDetailView.as_view(), name="manage-lesson"),
]
