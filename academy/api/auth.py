"""Account endpoints — ``docs/api.md`` §3, T-027 CP1.

Sign-in, sign-out, email verification and password reset/change. Responses are identical for an
unknown email and a wrong password (``invalid_credentials``) and for a known and an unknown reset
address (202 ``accepted``), so no endpoint tells a caller whether an account exists.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, Throttled
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from academy.access import accounts
from academy.access.principals import SESSION_KEY, session_auth_hash, session_user
from academy.access.throttles import throttle_exceeded
from academy.models import User

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
        )
        return Response(
            {
                "user": {
                    "id": user.pk,
                    "display_name": user.display_name,
                    "email_verified": user.is_email_verified,
                },
                "redirect": "/academy/",
                "email_verified": user.is_email_verified,
            },
            headers=_NO_STORE,
        )


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
        request.session[SESSION_KEY] = {
            "user_id": str(user.pk),
            "auth_hash": session_auth_hash(user),
            "roles": ["employee"],
        }
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
