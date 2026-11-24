"""Pagination fixed by ``docs/api.md`` §1: ``page`` + ``page_size`` (25, maximum 100)."""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class AcademyPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
