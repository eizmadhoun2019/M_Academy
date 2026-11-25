"""Loopback Hub fake — the development and test double of ``docs/hub-contract.md`` §3.

It speaks the proposed service API over real HTTP on ``127.0.0.1`` so the transports are
exercised end to end (timeouts, retries, idempotency, JSON shapes) without a Hub. It also signs
identity assertions for browser-facing tests, and its recorded calls let a suite assert that a
retry delivered exactly once.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from host_stub.identity import sign_claims

DEFAULT_TOKEN = "hub-service-token"
DEFAULT_KID = "k1"
DEFAULT_SECRET = "dev-identity-secret-that-is-at-least-32-bytes"


def new_nonce() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(24)).rstrip(b"=").decode("ascii")


def sign_identity(
    *,
    method: str,
    target: str,
    organization_id: UUID,
    user_ref: str = "u-42",
    role: str = "employee",
    department_refs: list[str] | None = None,
    is_active: bool = True,
    kid: str = DEFAULT_KID,
    secret: str = DEFAULT_SECRET,
    now: int | None = None,
    nonce: str | None = None,
) -> str:
    import time

    issued = int(now if now is not None else time.time())
    claims = {
        "iss": "masheed-hub",
        "aud": "masheed-academy",
        "iat": issued,
        "exp": issued + 60,
        "nonce": nonce or new_nonce(),
        "organization_id": str(organization_id),
        "user_ref": user_ref,
        "display_name": "Example Employee",
        "language": "ar",
        "role": role,
        "department_refs": department_refs if department_refs is not None else ["training"],
        "is_active": is_active,
        "method": method,
        "target": target,
    }
    return sign_claims(claims, kid=kid, secret=secret)


def sign_webhook(
    body: bytes,
    *,
    target: str = "/internal/hub/webhooks/",
    organization_id: UUID,
    kid: str = "w1",
    secret: str = "dev-webhook-secret-that-is-at-least-32-bytes",
    now: int | None = None,
    nonce: str | None = None,
    ttl: int = 300,
) -> str:
    import time

    issued = int(now if now is not None else time.time())
    claims = {
        "iss": "masheed-hub",
        "aud": "masheed-academy:webhooks",
        "iat": issued,
        "exp": issued + ttl,
        "nonce": nonce or new_nonce(),
        "target": target,
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "organization_id": str(organization_id),
    }
    return sign_claims(claims, kid=kid, secret=secret)


class _Handler(BaseHTTPRequestHandler):
    server: FakeHubServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self, query: dict[str, list[str]]) -> tuple[bool, dict[str, Any]]:
        hub = self.server.hub
        if self.headers.get("Authorization") != f"Bearer {hub.token}":
            return False, {"code": "unauthorized"}
        tenant = (query.get("organization_id") or [""])[0]
        if tenant != str(hub.organization_id):
            return False, {"code": "forbidden"}
        return True, {}

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        hub = self.server.hub
        hub.requests.append(("GET", parsed.path, query))
        ok, error = self._authorized(query)
        if not ok:
            self._send(403 if error["code"] == "forbidden" else 401, error)
            return
        route = parsed.path.rsplit("/", 1)[-1]
        if route == "departments":
            self._send(200, {"items": hub.departments, "next_cursor": None})
        elif route == "department-members":
            ref = (query.get("department_ref") or [""])[0]
            members = hub.department_members(ref)
            self._send(
                200, {"items": [{"user_ref": ref_} for ref_ in members], "next_cursor": None}
            )
        elif route == "manager":
            ref = (query.get("user_ref") or [""])[0]
            user = hub.users.get(ref)
            manager = user.get("manager_ref") if user else None
            self._send(200, {"items": [{"manager_ref": manager}], "next_cursor": None})
        elif route == "users":
            refs = query.get("ref", [])
            items = [hub.users[ref] for ref in refs if ref in hub.users]
            self._send(200, {"items": items, "next_cursor": None})
        elif route == "roles":
            self._send(200, {"items": hub.roles, "next_cursor": None})
        elif route == "role-members":
            role = (query.get("role") or [""])[0]
            items = [user for user in hub.users.values() if user.get("role") == role]
            self._send(200, {"items": [{"user_ref": u["user_ref"]} for u in items]})
        else:
            self._send(404, {"code": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        hub = self.server.hub
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        hub.requests.append(("POST", parsed.path, query))
        ok, error = self._authorized(query)
        if not ok:
            self._send(403 if error["code"] == "forbidden" else 401, error)
            return
        key = self.headers.get("Idempotency-Key", "")
        if not key:
            self._send(400, {"code": "invalid_request"})
            return
        digest = hashlib.sha256(raw).hexdigest()
        route = parsed.path.rsplit("/", 1)[-1]
        if key in hub.deliveries:
            if hub.deliveries[key] != digest:
                self._send(409, {"code": "idempotency_conflict"})
            else:
                self._send(200, {"accepted": True, "duplicate": True})
            return
        hub.deliveries[key] = digest
        body = json.loads(raw or b"{}")
        if route == "mail":
            hub.mails.append(body)
        elif route == "activity-log":
            hub.activities.append(body)
        else:
            self._send(404, {"code": "not_found"})
            return
        self._send(202, {"accepted": True, "duplicate": False})


class FakeHubServer(ThreadingHTTPServer):
    daemon_threads = True
    hub: FakeHub


class FakeHub:
    """A running loopback Hub service with seedable directory data."""

    def __init__(
        self,
        *,
        organization_id: UUID,
        token: str = DEFAULT_TOKEN,
        identity_secret: str = DEFAULT_SECRET,
        identity_kid: str = DEFAULT_KID,
    ) -> None:
        self.organization_id = organization_id
        self.token = token
        self.identity_secret = identity_secret
        self.identity_kid = identity_kid
        self.departments: list[dict[str, Any]] = []
        self.users: dict[str, dict[str, Any]] = {}
        self.roles: list[dict[str, str]] = []
        self.mails: list[dict[str, Any]] = []
        self.activities: list[dict[str, Any]] = []
        self.deliveries: dict[str, str] = {}
        self.requests: list[tuple[str, str, dict[str, list[str]]]] = []
        self._server = FakeHubServer(("127.0.0.1", 0), _Handler)
        self._server.hub = self
        self._thread: threading.Thread | None = None

    # --- lifecycle ----------------------------------------------------------

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{str(host)}:{int(port)}"

    def __enter__(self) -> FakeHub:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    # --- seeding ------------------------------------------------------------

    def add_department(self, ref: str, name: str, parent_ref: str | None = None) -> None:
        self.departments.append({"ref": ref, "name": name, "parent_ref": parent_ref})

    def add_role(self, ref: str, name: str) -> None:
        self.roles.append({"ref": ref, "name": name})

    def add_user(self, user: dict[str, Any]) -> None:
        self.users[str(user["user_ref"])] = user

    def department_members(self, department_ref: str) -> list[str]:
        """Members of the department and its descendants, active only (contract §3)."""
        refs = {department_ref}
        changed = True
        while changed:
            changed = False
            for department in self.departments:
                if department["parent_ref"] in refs and department["ref"] not in refs:
                    refs.add(department["ref"])
                    changed = True
        return [
            user["user_ref"]
            for user in self.users.values()
            if user.get("is_active") and refs.intersection(user.get("department_refs", []))
        ]

    # --- signing ------------------------------------------------------------

    def sign(
        self,
        *,
        method: str,
        target: str,
        user_ref: str = "u-42",
        role: str = "employee",
        department_refs: list[str] | None = None,
        is_active: bool = True,
        now: int | None = None,
        nonce: str | None = None,
    ) -> str:
        return sign_identity(
            method=method,
            target=target,
            organization_id=self.organization_id,
            user_ref=user_ref,
            role=role,
            department_refs=department_refs,
            is_active=is_active,
            kid=self.identity_kid,
            secret=self.identity_secret,
            now=now,
            nonce=nonce,
        )
