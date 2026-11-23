"""Tenant base model and its scoped manager — ``docs/domain-model.md`` §1.1.

Every concrete Academy model subclasses :class:`TenantModel`; every runtime read starts at
:meth:`TenantQuerySet.for_org`. ``objects`` stays unrestricted on purpose only for migrations
and tests, so an accidental unscoped query is visible in review instead of silently global.

The manager is generic so ``Course.objects.for_org(...)`` types as ``Course`` rows: a generic
manager is what keeps the type checker able to find a call site that bypassed ``for_org``.
"""

from __future__ import annotations

import uuid
from typing import Any, TypeVar, cast

from django.db import models
from django.utils import timezone

_ModelT = TypeVar("_ModelT", bound="TenantModel")


class TenantQuerySet(models.QuerySet[_ModelT]):
    """A queryset that cannot be scoped by accident."""

    def for_org(self, organization_id: uuid.UUID) -> TenantQuerySet[_ModelT]:
        """Restrict to one organization; anything that is not an organization UUID is a bug."""
        if not isinstance(organization_id, uuid.UUID):
            raise ValueError(
                f"for_org() requires an organization UUID, got {type(organization_id).__name__}"
            )
        return cast("TenantQuerySet[_ModelT]", self.filter(organization_id=organization_id))


class TenantManager(models.Manager[_ModelT]):
    """Default manager: unscoped for migrations/tests, ``for_org`` for every runtime read."""

    def get_queryset(self) -> TenantQuerySet[_ModelT]:
        return TenantQuerySet(self.model, using=self._db)

    def for_org(self, organization_id: uuid.UUID) -> TenantQuerySet[_ModelT]:
        return self.get_queryset().for_org(organization_id)


class TenantModel(models.Model):
    """Columns every Academy table shares (``docs/domain-model.md`` §1.1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Never a foreign key: the organization lives in the Hub, and the tenant boundary must
    # hold even if the Hub is unreachable.
    organization_id = models.UUIDField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    # Re-bound per concrete model (``objects: TenantManager[Course]``), which is what keeps
    # ``.create()`` and ``.for_org()`` typed as that model. The base stays ``Any`` so the
    # override is legal for the type checker instead of becoming a ClassVar conflict.
    objects: Any = TenantManager()

    class Meta:
        abstract = True
