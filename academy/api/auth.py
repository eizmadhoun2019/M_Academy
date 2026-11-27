"""Account endpoints — ``docs/api.md`` §3, T-027 CP1.

Sign-in, sign-out, email verification and password reset/change. Responses are identical for an
unknown email and a wrong password (``invalid_credentials``) and for a known and an unknown reset
address (202 ``accepted``), so no endpoint tells a caller whether an account exists.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, Throttled
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from academy.access import accounts, invitations, mfa, sessions
from academy.access.principals import session_user
from academy.access.throttles import throttle_exceeded
from academy.exceptions import NotFound
from academy.models import User, UserSession

_NO_STORE = {"Cache-Control": "private, no-store"}


def _public_link(request: Request, path: str, token: str) -> str:
    """Absolute link from configured origin, never from the request's Host header."""
    origin = str(getattr(settings, "ACADEMY_PUBLIC_ORIGIN", "") or "").rstrip("/")
    if not origin:
        origin = request.build_absolute_uri("/").rstrip("/")
    return f"{origin}{path}?token={quote(token)}"


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})
    mfa_code = serializers.CharField(required=False, allow_blank=True, default="")


class AccountSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField()
    email_verified = serializers.BooleanField()


class LoginResponseSerializer(serializers.Serializer):
    user = AccountSerializer()
    redirect = serializers.CharField()
    email_verified = serializers.BooleanField()


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField()


class ResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    password = serializers.CharField(trim_whitespace=False)


class AcceptedSerializer(serializers.Serializer):
    status = serializers.CharField()


def _account(user: User) -> dict[str, Any]:
    return {
        "id": user.pk,
        "display_name": user.display_name,
        "email_verified": user.is_email_verified,
    }


def _signed_in(user: User) -> dict[str, Any]:
    return {
        "user": _account(user),
        "redirect": "/academy/",
        "email_verified": user.is_email_verified,
        "mfa_enabled": mfa.enabled(user),
    }


class LoginView(APIView):
    """Email + password sign-in; a failure never creates a session."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: LoginResponseSerializer,
            401: OpenApiResponse(description="invalid_credentials"),
            429: OpenApiResponse(description="throttled"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = accounts.authenticate_credentials(
            request,
            serializer.validated_data["email"],
            serializer.validated_data["password"],
            serializer.validated_data.get("mfa_code") or None,
        )
        return Response(_signed_in(user), headers=_NO_STORE)


class LogoutView(APIView):
    """End the current session; idempotent for any authenticated caller."""

    @extend_schema(request=None, responses={204: OpenApiResponse(description="ended")})
    def post(self, request: Request) -> Response:
        request.session.flush()
        return Response(status=204)


class PasswordResetRequestView(APIView):
    """Mail a reset token; always 202, whether or not the address exists."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]

    @extend_schema(request=EmailSerializer, responses={202: AcceptedSerializer})
    def post(self, request: Request) -> Response:
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if throttle_exceeded(request, "auth_password_reset", "5/hour"):
            raise Throttled()
        issued = accounts.password_reset_token(serializer.validated_data["email"])
        if issued is not None:
            user, token = issued
            ttl = int(getattr(settings, "ACADEMY_PASSWORD_RESET_TTL_SECONDS", 3600))
            accounts.send_account_mail(
                user, "password_reset", _public_link(request, "/academy/reset/", token), ttl
            )
        return Response({"status": "accepted"}, status=202, headers=_NO_STORE)


class PasswordResetConfirmView(APIView):
    """Consume a reset token once and set the new password."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=ResetConfirmSerializer,
        responses={200: AcceptedSerializer, 400: OpenApiResponse(description="token_invalid")},
    )
    def post(self, request: Request) -> Response:
        serializer = ResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        accounts.reset_password(
            serializer.validated_data["token"], serializer.validated_data["password"]
        )
        return Response({"status": "reset"}, headers=_NO_STORE)


class PasswordChangeView(APIView):
    """Change a known password; the current one is re-verified."""

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: AcceptedSerializer, 400: OpenApiResponse(description="validation_error")},
    )
    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = session_user(request)
        if user is None:
            raise NotAuthenticated("no Academy session")
        accounts.change_password(
            user,
            serializer.validated_data["current_password"],
            serializer.validated_data["password"],
        )
        request.session[accounts.SESSION_KEY] = accounts.session_payload(user)
        sessions.revoke_others(user, keep_key=request.session.session_key)
        return Response({"status": "changed"}, headers=_NO_STORE)


class EmailVerifyRequestView(APIView):
    """Resend verification mail; always 202, throttled per client address."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]

    @extend_schema(request=EmailSerializer, responses={202: AcceptedSerializer})
    def post(self, request: Request) -> Response:
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if throttle_exceeded(request, "auth_email_verify", "5/hour"):
            raise Throttled()
        user = (
            session_user(request)
            or User.objects.filter(
                email__iexact=serializer.validated_data["email"], is_email_verified=False
            ).first()
        )
        if user is not None and user.is_active and not user.is_email_verified:
            token = accounts.verification_token(user)
            ttl = int(getattr(settings, "ACADEMY_EMAIL_VERIFICATION_TTL_SECONDS", 86400))
            accounts.send_account_mail(
                user, "verification", _public_link(request, "/academy/verify-email/", token), ttl
            )
        return Response({"status": "accepted"}, status=202, headers=_NO_STORE)


class EmailVerifyConfirmView(APIView):
    """Consume a verification token once; the address becomes verified."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=TokenSerializer,
        responses={200: AcceptedSerializer, 400: OpenApiResponse(description="token_invalid")},
    )
    def post(self, request: Request) -> Response:
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        accounts.confirm_email(serializer.validated_data["token"])
        return Response({"status": "verified"}, headers=_NO_STORE)


class SessionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    last_seen_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    current = serializers.BooleanField()
    ip_prefix = serializers.CharField()
    user_agent_family = serializers.CharField()


class SessionListView(APIView):
    """List the caller's live sessions; the current one is flagged, never another account's."""

    @extend_schema(responses=SessionSerializer(many=True))
    def get(self, request: Request) -> Response:
        user = session_user(request)
        if user is None:
            raise NotAuthenticated("no Academy session")
        current_hash = sessions.key_hash(request.session.session_key)
        rows = UserSession.objects.filter(
            user=user, revoked_at__isnull=True, expires_at__gt=timezone.now()
        ).order_by("-last_seen_at")
        payload = [
            {
                "id": row.pk,
                "created_at": row.created_at,
                "last_seen_at": row.last_seen_at,
                "expires_at": row.expires_at,
                "current": row.session_key_hash == current_hash,
                "ip_prefix": row.ip_prefix,
                "user_agent_family": row.user_agent_family,
            }
            for row in rows
        ]
        return Response(payload, headers=_NO_STORE)


class SessionRevokeView(APIView):
    """Revoke one of the caller's sessions; another account's id is a plain 404."""

    @extend_schema(request=None, responses={204: OpenApiResponse(description="revoked")})
    def delete(self, request: Request, session_id: Any) -> Response:
        user = session_user(request)
        if user is None:
            raise NotAuthenticated("no Academy session")
        row = UserSession.objects.filter(pk=session_id, user=user).first()
        if row is None:
            raise NotFound("session not found")
        sessions.revoke(row)
        return Response(status=204)


class MFAVerifySerializer(serializers.Serializer):
    challenge_id = serializers.CharField()
    code = serializers.CharField(trim_whitespace=False)


class MFAEnrollSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})


class MFAEnrollResponseSerializer(serializers.Serializer):
    secret = serializers.CharField()
    otpauth_uri = serializers.CharField()


class MFAConfirmSerializer(serializers.Serializer):
    code = serializers.CharField(trim_whitespace=False)


class MFAConfirmResponseSerializer(serializers.Serializer):
    recovery_codes = serializers.ListField(child=serializers.CharField())


class MFADisableSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})
    code = serializers.CharField(trim_whitespace=False)


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})
    display_name = serializers.CharField(max_length=150)


class InvitationAcceptedSerializer(serializers.Serializer):
    status = serializers.CharField()
    redirect = serializers.CharField()


class MFAVerifyView(APIView):
    """Complete a challenged sign-in with a TOTP or recovery code (single use, 5 minutes)."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=MFAVerifySerializer,
        responses={
            200: LoginResponseSerializer,
            401: OpenApiResponse(description="mfa_invalid"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = accounts.complete_mfa(
            request,
            serializer.validated_data["challenge_id"],
            serializer.validated_data["code"],
        )
        return Response(_signed_in(user), headers=_NO_STORE)


class MFAEnrollView(APIView):
    """Start TOTP enrolment after a password re-entry; the secret is returned once."""

    @extend_schema(
        request=MFAEnrollSerializer,
        responses={
            200: MFAEnrollResponseSerializer,
            400: OpenApiResponse(description="validation_error"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = MFAEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = session_user(request)
        if user is None:
            raise NotAuthenticated("no Academy session")
        _, secret, uri = mfa.enroll(user, serializer.validated_data["password"])
        return Response({"secret": secret, "otpauth_uri": uri}, headers=_NO_STORE)


class MFAConfirmView(APIView):
    """Confirm the pending device; the ten recovery codes are shown once."""

    @extend_schema(
        request=MFAConfirmSerializer,
        responses={
            200: MFAConfirmResponseSerializer,
            400: OpenApiResponse(description="validation_error"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = MFAConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = session_user(request)
        if user is None:
            raise NotAuthenticated("no Academy session")
        codes = mfa.confirm(user, serializer.validated_data["code"])
        return Response({"recovery_codes": codes}, headers=_NO_STORE)


class MFADisableView(APIView):
    """Remove the second factor; both the password and a current code are required."""

    @extend_schema(
        request=MFADisableSerializer,
        responses={
            200: AcceptedSerializer,
            400: OpenApiResponse(description="validation_error"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = MFADisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = session_user(request)
        if user is None:
            raise NotAuthenticated("no Academy session")
        mfa.disable(
            user,
            serializer.validated_data["password"],
            serializer.validated_data["code"],
        )
        return Response({"status": "disabled"}, headers=_NO_STORE)


class InvitationAcceptView(APIView):
    """Accept a company invitation once; no session is created without the credential."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=InvitationAcceptSerializer,
        responses={
            200: InvitationAcceptedSerializer,
            400: OpenApiResponse(description="invitation_invalid"),
            409: OpenApiResponse(description="already_member"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if throttle_exceeded(request, "auth_invitation_accept", "10/hour"):
            raise Throttled()
        invitations.accept(
            serializer.validated_data["token"],
            password=serializer.validated_data["password"],
            display_name=serializer.validated_data["display_name"],
        )
        return Response({"status": "accepted", "redirect": "/academy/login/"}, headers=_NO_STORE)
