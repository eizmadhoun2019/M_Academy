"""The development sign-in form (X1). It creates nothing and stores no password.

T-026 CP3: the stub selects a **seeded account**, never a company. The account's single
membership supplies the company on every request; the form only offers accounts that own one.
"""

from __future__ import annotations

from typing import Any, cast

from django import forms

from academy.access.principals import ROLES
from academy.models import Membership, User


def seeded_account_choices() -> list[tuple[str, str]]:
    """Legacy references of accounts with an active membership, for the local stub."""
    rows = (
        User.objects.filter(memberships__status=Membership.Status.ACTIVE)
        .exclude(legacy_ref__isnull=True)
        .exclude(legacy_ref="")
        .order_by("display_name", "email")
        .values_list("legacy_ref", "display_name", "email")
    )
    return [(str(ref), f"{name} — {email}") for ref, name, email in rows]


class DevelopmentLoginForm(forms.Form):
    """A local stub for the Hub identity: no password store, no company selection."""

    user_ref = forms.ChoiceField(label="User reference", choices=[])
    password = forms.CharField(label="Password", widget=forms.PasswordInput, strip=False)
    role = forms.ChoiceField(
        label="Role",
        choices=[(role, role.replace("_", " ").title()) for role in ROLES],
        initial="employee",
    )
    simulate_inactive = forms.BooleanField(label="Simulate an inactive membership", required=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        field = cast(forms.ChoiceField, self.fields["user_ref"])
        field.choices = seeded_account_choices()
