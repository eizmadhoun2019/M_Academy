"""T-026 CP1 acceptance: four tables, tenant constraints and the database foreign keys."""

from __future__ import annotations

import uuid
from datetime import timedelta
from uuid import UUID

import pytest
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from academy.models import (
    Course,
    Department,
    Membership,
    Organization,
    User,
)


def make_user(email: str = "learner@example.com") -> User:
    return User.objects.create(email=email, display_name="Learner")


def make_membership(
    organization_id: UUID, user: User, *, status: str = Membership.Status.ACTIVE, **extra: object
) -> Membership:
    values = {"organization_id": organization_id, "user": user, "status": status}
    if status == Membership.Status.ACTIVE:
        values["joined_at"] = timezone.now()
    values.update(extra)
    return Membership.objects.create(**values)


@pytest.mark.django_db
def test_seed_created_masheed_once(org_id: UUID) -> None:
    organization = Organization.objects.get(id=org_id)

    assert organization.slug == "masheed"
    assert organization.name_ar == settings.ACADEMY_COMPANY_NAME
    assert organization.status == Organization.Status.ACTIVE
    assert organization.timezone == settings.ACADEMY_BUSINESS_TZ
    assert Organization.objects.filter(slug="masheed").count() == 1


@pytest.mark.django_db
def test_organization_slug_is_unique_and_lowercase(org_id: UUID, other_org_id: UUID) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Organization.objects.create(id=uuid.uuid4(), name_ar="Duplicate", slug="masheed")

    with pytest.raises(IntegrityError), transaction.atomic():
        Organization.objects.create(id=uuid.uuid4(), name_ar="Upper", slug="Not-Lower")


@pytest.mark.django_db
def test_organization_archive_is_stamped(org_id: UUID) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Organization.objects.create(
            id=uuid.uuid4(), name_ar="Archived", slug="archived-co", status="archived"
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Organization.objects.create(
            id=uuid.uuid4(), name_ar="Active", slug="active-co", archived_at=timezone.now()
        )


@pytest.mark.django_db
def test_email_is_case_insensitively_unique() -> None:
    make_user("Person@Example.com")

    with pytest.raises(IntegrityError), transaction.atomic():
        make_user("person@example.com")


@pytest.mark.django_db
def test_one_membership_per_account_at_the_database(org_id: UUID, other_org_id: UUID) -> None:
    user = make_user()
    make_membership(org_id, user)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_membership(other_org_id, user)


@pytest.mark.django_db
def test_platform_only_account_needs_no_membership() -> None:
    user = make_user("platform@example.com")

    assert user.memberships.count() == 0


@pytest.mark.django_db
def test_membership_status_lifecycle_is_stamped(org_id: UUID) -> None:
    user = make_user()

    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.create(organization_id=org_id, user=user, status="active")
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.create(organization_id=org_id, user=user, status="removed")


@pytest.mark.django_db
def test_department_constraints(org_id: UUID) -> None:
    root = Department.objects.create(organization_id=org_id, name_ar="التدريب")

    with pytest.raises(IntegrityError), transaction.atomic():
        Department.objects.create(organization_id=org_id, name_ar="التدريب")

    child = Department.objects.create(organization_id=org_id, name_ar="قسم", parent=root)
    with pytest.raises(IntegrityError), transaction.atomic():
        Department.objects.create(organization_id=org_id, name_ar="قسم", parent=root)
    assert child.parent_id == root.id

    with pytest.raises(IntegrityError), transaction.atomic():
        root.parent = root
        root.save()


@pytest.mark.django_db
def test_department_parent_cannot_cross_companies(org_id: UUID, other_org_id: UUID) -> None:
    foreign = Department.objects.create(organization_id=other_org_id, name_ar="خارجي")

    with pytest.raises(IntegrityError), transaction.atomic():
        Department.objects.create(organization_id=org_id, name_ar="داخلي", parent=foreign)


@pytest.mark.django_db
def test_membership_department_cannot_cross_companies(org_id: UUID, other_org_id: UUID) -> None:
    user = make_user()
    foreign = Department.objects.create(organization_id=other_org_id, name_ar="خارجي")

    with pytest.raises(IntegrityError), transaction.atomic():
        make_membership(org_id, user, department=foreign)


@pytest.mark.django_db
def test_tenant_row_requires_an_existing_company() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Course.objects.create(
            organization_id=uuid.uuid4(),
            title="Orphan course",
            created_by_ref="u-author",
        )


@pytest.mark.django_db
def test_membership_removal_keeps_history(org_id: UUID) -> None:
    user = make_user()
    membership = make_membership(org_id, user)
    removed_at = timezone.now() + timedelta(minutes=1)

    membership.status = Membership.Status.REMOVED
    membership.removed_at = removed_at
    membership.save()

    assert Membership.objects.get(id=membership.id).removed_at == removed_at
