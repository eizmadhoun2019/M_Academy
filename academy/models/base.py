"""Tenant base model and its scoped manager — ``docs/domain-model.md`` §1.1.

Every concrete Academy model subclasses :class:`TenantModel`; every runtime read starts at
:meth:`TenantQuerySet.for_org`. ``objects`` stays unrestricted on purpose only for migrations
and tests, so an accidental unscoped query is visible in review instead of silently global.
"""

from __future__ import annotations

import uuid
from typing import cast

from django.db import models
from django.utils import timezone


class TenantQuerySet(models.QuerySet["TenantModel"]):
    """A queryset that cannot be scoped by accident."""

    def for_org(self, organization_id: uuid.UUID) -> TenantQuerySet:
        """Restrict to one organization; anything that is not an organization UUID is a bug."""
        if not isinstance(organization_id, uuid.UUID):
            raise ValueError(
                f"for_org() requires an organization UUID, got {type(organization_id).__name__}"
            )
        return cast(TenantQuerySet, self.filter(organization_id=organization_id))


class TenantManager(models.Manager["TenantModel"]):
    """Default manager: unscoped for migrations/tests, ``for_org`` for every runtime read."""

    def get_queryset(self) -> TenantQuerySet:
        return TenantQuerySet(self.model, using=self._db)

    def for_org(self, organization_id: uuid.UUID) -> TenantQuerySet:
        return self.get_queryset().for_org(organization_id)


class TenantModel(models.Model):
    """Columns every Academy table shares (``docs/domain-model.md`` §1.1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Never a foreign key: the organization lives in the Hub, and the tenant boundary must
    # hold even if the Hub is unreachable.
    organization_id = models.UUIDField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        abstract = True
