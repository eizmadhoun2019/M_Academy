"""`/api/v1/academy/` routes (``docs/api.md`` §1)."""

from __future__ import annotations

from django.urls import path

from academy.api.assignments import (
    AssignmentDetailView,
    AssignmentListCreateView,
    AssignmentPreviewView,
    CourseRosterView,
    EnrollmentCancelView,
    EnrollmentDetailView,
    MyCoursesView,
    MyEnrollmentsView,
)
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
from academy.api.media import (
    MediaCompleteView,
    MediaDetailView,
    MediaRetryView,
    MediaUploadCreateView,
    PlaybackView,
)
from academy.api.progress import (
    AcknowledgeView,
    EnrollmentCompleteView,
    EnrollmentOverrideCompleteView,
    LessonCompleteView,
    LessonProgressView,
)
from academy.api.reports import (
    ReportCompletionView,
    ReportExportView,
    ReportOverdueView,
    ReportSummaryView,
)
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
    path("manage/media/uploads/", MediaUploadCreateView.as_view(), name="manage-media-uploads"),
    path("manage/media/<uuid:media_id>/", MediaDetailView.as_view(), name="manage-media"),
    path(
        "manage/media/<uuid:media_id>/complete/",
        MediaCompleteView.as_view(),
        name="manage-media-complete",
    ),
    path(
        "manage/media/<uuid:media_id>/retry/",
        MediaRetryView.as_view(),
        name="manage-media-retry",
    ),
    path("manage/reports/summary/", ReportSummaryView.as_view(), name="manage-reports-summary"),
    path("manage/reports/overdue/", ReportOverdueView.as_view(), name="manage-reports-overdue"),
    path(
        "manage/reports/completion/",
        ReportCompletionView.as_view(),
        name="manage-reports-completion",
    ),
    path("manage/reports/export.csv", ReportExportView.as_view(), name="manage-reports-export"),
    path("manage/assignments/", AssignmentListCreateView.as_view(), name="manage-assignments"),
    path(
        "manage/assignments/preview/",
        AssignmentPreviewView.as_view(),
        name="manage-assignments-preview",
    ),
    path(
        "manage/assignments/<uuid:assignment_id>/",
        AssignmentDetailView.as_view(),
        name="manage-assignment",
    ),
    path(
        "manage/courses/<uuid:course_id>/enrollments/",
        CourseRosterView.as_view(),
        name="manage-course-enrollments",
    ),
    path(
        "manage/enrollments/<uuid:enrollment_id>/cancel/",
        EnrollmentCancelView.as_view(),
        name="manage-enrollment-cancel",
    ),
    path(
        "manage/enrollments/<uuid:enrollment_id>/complete/",
        EnrollmentOverrideCompleteView.as_view(),
        name="manage-enrollment-complete",
    ),
    path("my/courses/", MyCoursesView.as_view(), name="my-courses"),
    path("my/enrollments/", MyEnrollmentsView.as_view(), name="my-enrollments"),
    path(
        "my/enrollments/<uuid:enrollment_id>/",
        EnrollmentDetailView.as_view(),
        name="my-enrollment",
    ),
    path(
        "enrollments/<uuid:enrollment_id>/lessons/<uuid:lesson_id>/playback/",
        PlaybackView.as_view(),
        name="lesson-playback",
    ),
    path(
        "enrollments/<uuid:enrollment_id>/lessons/<uuid:lesson_id>/progress/",
        LessonProgressView.as_view(),
        name="lesson-progress",
    ),
    path(
        "enrollments/<uuid:enrollment_id>/lessons/<uuid:lesson_id>/complete/",
        LessonCompleteView.as_view(),
        name="lesson-complete",
    ),
    path(
        "enrollments/<uuid:enrollment_id>/acknowledge/",
        AcknowledgeView.as_view(),
        name="enrollment-acknowledge",
    ),
    path(
        "enrollments/<uuid:enrollment_id>/complete/",
        EnrollmentCompleteView.as_view(),
        name="enrollment-complete",
    ),
]
