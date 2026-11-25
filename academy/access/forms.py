"""The development sign-in form (X1). It creates nothing and stores no password."""

from __future__ import annotations

from django import forms

from academy.access.principals import ROLES

_USER_REF = r"^[A-Za-z0-9_-]{1,64}$"


class DevelopmentLoginForm(forms.Form):
    """A local stub for the Hub identity: no account row, no password store."""

    user_ref = forms.RegexField(
        label="User reference",
        regex=_USER_REF,
        max_length=64,
        error_messages={"invalid": "Use 1-64 letters, digits, underscores or hyphens."},
    )
    password = forms.CharField(label="Password", widget=forms.PasswordInput, strip=False)
    role = forms.ChoiceField(
        label="Role",
        choices=[(role, role.replace("_", " ").title()) for role in ROLES],
        initial="employee",
    )
    department_ref = forms.CharField(label="Department reference", required=False, max_length=64)
    simulate_inactive = forms.BooleanField(label="Simulate an inactive membership", required=False)
