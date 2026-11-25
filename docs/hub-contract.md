# Masheed Hub ↔ Academy integration contract (OPTIONAL, DORMANT)

**Status: Dormant / optional integration (D-031, T-033).** H1.5 runs standalone: Academy owns its origin, accounts, memberships, permissions and mail. Nothing below is on the launch path, and no Hub route, key or job exists while `ACADEMY_HUB_ENABLED=false` (the default). The wire contract is retained for a future explicitly approved integration; every route and behavior is still a proposal for Hub-team review (D-004, D-010).

## Pending Hub-team confirmation (only when the integration is enabled)

| Decision | Proposal default | Configuration or owner action |
|---|---|---|
| D-004 · Token format and rotation | HMAC-SHA256 signed envelope, independent identity/webhook key rings, 60-second identity lifetime and five seconds of clock skew | Configure key rings and the identity verifier. A JWT variant requires a compatible verifier and agreement on the wire format. |
| D-010 · Hub implementation owner and availability | Academy-side verification uses a loopback Hub fake. Hub owner, integration contact, test URL and delivery date are pending. | Hub team assigns an owner and supplies the service URL, credential and accepted route map. Configure these per environment. |
| D-005 · Academy DNS and TLS | The **default** public origin is Academy's own HTTPS origin (D-035). A Hub reverse proxy is an optional topology only if both owners approve it. | Configure Academy's hostname/certificate for production. Only if the proxy topology is approved, also configure Hub origin, upstream, allowlisted proxy networks, prefix, CSRF origins and bucket CORS. Example hosts below are placeholders. |
| D-011 · Navigation source | Academy owns its own permission-aware sidebar and personal dashboard; it does **not** mirror Hub navigation. | Any legacy `ACADEMY_HUB_NAVIGATION_SOURCE` setting is a compatibility concern only; Academy decides internal links from effective Academy permissions. A contextual Return to Hub link is optional. |

## 1. Requests from the browser through Hub

This section applies **only** when the integration is enabled. Default: Academy serves `/` and `/academy/` on its own origin; no proxy is involved. In the optional topology: example public origin `https://hub.example.com`, private upstream `https://academy.internal.example.com`.

| Browser request | Hub forwarding |
|---|---|
| /academy/ | Authenticate in Hub, strip /academy once, and forward / to the Academy upstream. |
| /academy/api/v1/academy/ | Forward /api/v1/academy/ with fresh signed identity and the unchanged query string. |
| /academy/static/… | Serve collected Academy static assets under this prefix on the Hub origin. |
| Video upload, manifest or segment | Browser requests the HTTPS object-storage URL directly using the presigned authorization in that URL. |

For dynamic Academy routes, check the Hub session before proxying. Remove every client-supplied copy of X-Masheed-Identity, X-Masheed-Webhook and X-Forwarded-* and set authoritative values at the trusted proxy. Preserve the public Hub Host and send X-Forwarded-Proto: https. Forward Academy's CSRF cookie and the Origin, Referer and X-CSRFToken headers when present. Keep the Hub session cookie and authorization credentials at Hub. Do not forward browser traffic to the internal webhook or health routes.

Academy treats the mount prefix as Django FORCE_SCRIPT_NAME, emits the academy_csrftoken cookie with Path=/academy/, Secure and SameSite=Lax, and checks the exact Hub origin. For an unsafe browser request, send both this cookie and its token in X-CSRFToken or the Django form field. Hub should preserve status codes and Academy's CSRF Set-Cookie header. Protected responses must not be shared-cacheable. The proxy should reject delivered API request bodies above 2 MiB, with explicit connect, read and overall deadlines. Size and timeout settings should account for Academy's latency targets. Academy does not issue a production login redirect. Hub handles its own sign-in when the Hub session is missing.

T-033 verifies the protected API entry point against the fake while the feature is enabled, and proves the routes are absent while it is disabled. Learner pages under a mount are delivered by T-031 only in that approved topology.

Configure bucket CORS for the exact Hub origin. Allow PUT, GET and HEAD, the signed upload headers (for example Content-Type), and Range for playback when used. Expose ETag, Accept-Ranges and Content-Range as needed. Allow the storage origin in Hub's media and connection CSP directives. The browser uses signed storage URLs without cookies. Academy grants and refreshes playback URLs through the proxied API.

## 2. Signed identity provided by the Hub proxy

Default header: X-Masheed-Identity. The default token is kid.payload.signature, with three dot-separated fields. kid is an ASCII key identifier containing 1–64 letters, digits, underscores or hyphens. payload is the unpadded base64url encoding of a UTF-8 JSON object. Compute HMAC-SHA256 over the exact ASCII bytes of kid + "." + payload, using the raw UTF-8 bytes of the selected shared secret. Encode the resulting 32 bytes as unpadded base64url for signature. Verification authenticates the original encoded payload, so JSON whitespace and property ordering do not require canonicalization.

Example decoded claims for GET /academy/api/v1/academy/?view=compact:

```json
{
  "iss": "masheed-hub",
  "aud": "masheed-academy",
  "iat": 1795132800,
  "exp": 1795132860,
  "nonce": "N1928Egz4jYnK-w22BR8XP3mYXMh9mVB",
  "organization_id": "25498ed9-13b1-4f10-8294-859ff80a41b7",
  "user_ref": "u-42",
  "display_name": "Example Employee",
  "language": "ar",
  "role": "employee",
  "department_refs": ["training"],
  "is_active": true,
  "method": "GET",
  "target": "/api/v1/academy/?view=compact"
}
```

All fields above are required. Use integer Unix seconds for iat and exp, and generate a fresh cryptographically random nonce for each forwarded request, including retries. Encode 24 random bytes as unpadded base64url for the nonce. target is the decoded internal URL path after removing the prefix, followed by ? and the original query string when present. For example, preserve query order and encoding exactly. Sign the actual forwarded method and target. Hub must derive the organization, user status and claims from trusted sources. Academy maps the asserted Hub organization and user reference to an existing local `Organization` and `Membership`; an unmapped organization or user is rejected. Hub claims never create companies, accounts or permissions implicitly.

Use a stable opaque user_ref up to 64 characters, a display name up to 200 characters, language ar or en, and a current membership status. Supply exactly one of platform_admin, department_manager, or employee. Academy maps the signed role to its own configured defaults. T-016 adds Academy-local grants to that calculation, and the token contract remains the same. department_refs contains up to 50 opaque strings (up to 64 characters each), with the primary department first. When the identity navigation source is selected, optionally include navigation as an array of up to 30 objects, for example [{"label":"Home","url":"/"}]. The labels are plain text and links are absolute paths on the Hub origin.

Academy verifies the signature, issuer, audience, expiration, route binding and a shared atomic nonce check. An invalid, expired or replayed assertion is treated as missing identity. The Academy API responds 401 for missing/invalid identity, 403 account_inactive for a verified inactive member, and 403 for a denied capability or CSRF check. Academy uses this verified actor locally for learner heartbeat and progress. The Hub API is not called on that path.

Provision independent identity and webhook signing secrets with at least 32 random bytes of entropy. Use a secret manager, avoid forwarding or logging key material, and synchronize clocks. To rotate, add the new kid to Academy's verification ring, switch Hub to signing with it, then remove the old key after the maximum acceptance window and clock skew have elapsed. Do not reuse a retired kid. A replacement verifier must validate the cryptographic signature and return the decoded claim object or reject it. Academy continues to enforce the constraints and nonce checks above.

## 3. Proposed Hub service API called by Academy

Send over HTTPS. Academy uses an independent Bearer service credential in Authorization, and each request includes organization_id as a UUID query parameter. Hub must authorize the credential for that tenant and these resources. Use JSON for all results. Academy will not follow redirects. The configured service URL and resource paths are integration settings.

Example request:

```http
GET /v1/academy/department-members?organization_id=25498ed9-13b1-4f10-8294-859ff80a41b7&department_ref=operations HTTP/1.1
Host: hub-api.example.com
Authorization: Bearer <service credential>
Accept: application/json
```

Each GET returns HTTP 200 with an items array and next_cursor set to null or an opaque string. Echo a page cursor from the previous response using cursor=<value>, preserving all the original filters. Return an empty items list when the object or membership is unknown and the request is tenant-authorized. Filter peers and foreign organizations at the source.

| Default path | Query beyond organization_id | Example items |
|---|---|---|
| GET /v1/academy/departments | none | [{"ref":"operations","name":"Operations","parent_ref":null},{"ref":"training","name":"Training","parent_ref":"operations"}] |
| GET /v1/academy/department-members | department_ref=operations | [{"user_ref":"u-42"}]. Return active memberships within the named department and descendants. |
| GET /v1/academy/manager | user_ref=u-42 | [{"manager_ref":"u-10"}] or [{"manager_ref":null}]. At most one item. |
| GET /v1/academy/users | Repeat ref, at most 50 distinct values per request | [{"user_ref":"u-42","display_name":"Example Employee","email":null,"language":"ar","role":"employee","department_refs":["training"],"manager_ref":"u-10","is_active":true}]. Include authorized inactive memberships. |
| GET /v1/academy/roles | none | [{"ref":"employee","name":"Employee"},{"ref":"department_manager","name":"Department manager"},{"ref":"platform_admin","name":"Platform admin"}] |
| GET /v1/academy/role-members | role=employee | [{"user_ref":"u-42"}]. Return active memberships for the exact role. |

For example, a complete department-members response is {"items":[{"user_ref":"u-42"}],"next_cursor":null}.

### Mail and activity delivery

Both POST routes require Content-Type: application/json and Idempotency-Key. Keys are unique per resource and organization. Persist the key before performing the side effect. A retry with the same key and body returns 200 with {"accepted":true,"duplicate":true}. A first accepted submission returns 202 with {"accepted":true,"duplicate":false}. Return 409 if a key is reused for different content. Keep keys for at least the delivery retry window agreed with Academy.

```http
POST /v1/academy/mail?organization_id=25498ed9-13b1-4f10-8294-859ff80a41b7 HTTP/1.1
Host: hub-api.example.com
Authorization: Bearer <service credential>
Content-Type: application/json
Idempotency-Key: assigned-training-u42

{"kind":"course_assigned","recipient_ref":"u-42","title":"Assigned training","body":"A course is ready.","url":"/academy/","idempotency_key":"assigned-training-u42","channels":["email","in_app"],"payload":null}
```

The idempotency key in the body matches the header. Resolve the recipient by opaque reference in that tenant. Support the agreed channels in the array. Any channel the service accepts must deliver at most once for the key. url and payload are nullable.

```http
POST /v1/academy/activity-log?organization_id=25498ed9-13b1-4f10-8294-859ff80a41b7 HTTP/1.1
Host: hub-api.example.com
Authorization: Bearer <service credential>
Content-Type: application/json
Idempotency-Key: 6b648bad-1883-42f9-a5cc-e1c7c09c1d2f

{"event_id":"6b648bad-1883-42f9-a5cc-e1c7c09c1d2f","action":"enrollment.cancelled","actor_ref":"system","object_type":"enrollment","object_id":"e-79","occurred_at":"2026-11-20T08:00:00+00:00"}
```

The event ID is the delivery key. Treat this as a mirror of Academy's append-only audit record. The payload excludes names, contact details, IP data and audit metadata.

### Errors, retry and outage behavior

Return compact JSON, for example {"code":"unavailable"}. Use 400 for malformed requests, 401 for missing/invalid service credentials, 403 for a forbidden organization, 404 for an unsupported route, 409 for a conflicting idempotency key, 429 for a rate-limited request, and 503 for an unavailable dependency.

Academy defaults to a 0.5-second connection timeout, a one-second socket timeout and one synchronous retry with 0.1 seconds of backoff. It retries connection failures and 429, 500, 502, 503 and 504. A write always carries the original idempotency key. After three exhausted transient calls, the shared circuit opens for 30 seconds. Academy caches directory data by tenant for at most 60 seconds and invalidates it on membership webhooks. If a required lookup fails, Academy returns 503 and defers the affected operation. Signed learner progress requests continue while the proxy can issue fresh identities. If the proxy itself goes down, Academy resumes from server-confirmed progress after recovery.

## 4. Membership webhooks Hub sends to Academy

**Proposed Academy endpoint:** POST https://academy.internal.example.com/internal/hub/webhooks/. Send directly from the Hub service over HTTPS. Use application/json and X-Masheed-Webhook. The default HMAC envelope is the same as §2 with a separate key ring, audience masheed-academy:webhooks, five-minute maximum delivery lifetime, and a distinct nonce. The signed JSON contains iss, aud, iat, exp, nonce, target and body_sha256. body_sha256 is lowercase hexadecimal SHA-256 of the exact request-body bytes. target is the internal path and any unchanged query string.

```http
POST /internal/hub/webhooks/ HTTP/1.1
Host: academy.internal.example.com
Content-Type: application/json
X-Masheed-Webhook: <kid.payload.signature>

{"event_id":"0a1c08da-6ee4-4bba-b2af-9c9a670aeaab","type":"member_changed","organization_id":"25498ed9-13b1-4f10-8294-859ff80a41b7","user_ref":"u-42","occurred_at":1795132800,"department_refs":["training"],"role":"employee","is_active":true}
```

Use member_deactivated with the same required envelope fields and a new unique event_id. Membership change attributes may be included on member_changed. Hub directory reads must reflect the change when the event is sent. Academy invalidates its directory cache for both types. member_deactivated invokes Academy's transactional cancellation hook. Enrollment expansion on member_changed belongs to T-019.

A successful POST returns 200 with {"accepted":true,"duplicate":false}. After an uncertain outcome, retry the same event ID with the same body bytes and a fresh nonce/signature; a duplicate returns 200 and duplicate:true. Reusing an event ID with a different body returns 409. A reused delivery nonce returns 401 even if the event ID was processed. Expect 400 for invalid event bodies, 401 for an invalid signature, 403 for an out-of-scope tenant, 405 for other methods, and 413 for requests above the body limit. Retry transport errors and 5xx responses with bounded backoff. Keep the original event until it is accepted or escalated for operations.

## 5. Configure Academy's side

The Hub variables below are required **only** when `ACADEMY_HUB_ENABLED=true` and `ACADEMY_ACCESS_MODE=hub`. With the default `false`, production startup must succeed without any of them and must not register webhook routes or Hub jobs (T-033 test). When enabled, startup rejects missing key rings or keys shorter than 32 UTF-8 bytes. Keep secrets in the deployment secret manager. Standalone mode always uses local Django authentication (D-033).

| Settings | What to configure |
|---|---|
| `ACADEMY_HUB_ORIGIN`, `ACADEMY_HUB_UPSTREAM_HOST`, `ACADEMY_TRUSTED_PROXY_NETWORKS` | Exact public HTTPS origin, private Academy hostname, and comma-separated trusted ingress CIDRs. Terminate TLS on the trusted Academy ingress and set its authoritative forwarded protocol and host. |
| `ACADEMY_PROXY_PATH_PREFIX`, `ACADEMY_CSRF_TRUSTED_ORIGINS`, `ACADEMY_STORAGE_CORS_ORIGIN` | Public prefix (default `/academy`), exact CSRF origins (defaults to the Hub origin), and exact origin to apply when provisioning bucket CORS. |
| `ACADEMY_HUB_API_BASE_URL`, `ACADEMY_HUB_API_TOKEN`, `ACADEMY_HUB_API_PATHS` | Hub service HTTPS URL, outbound bearer and optional JSON object overriding paths. Resource keys are `users`, `departments`, `department_members`, `manager`, `roles`, `role_members`, `mail`, `activity`. |
| `ACADEMY_HUB_IDENTITY_KEYS`, `ACADEMY_HUB_WEBHOOK_KEYS`, `ACADEMY_HUB_IDENTITY_VERIFIER` | Separate JSON key-ID-to-secret maps, or verification keys for a replacement identity verifier. The verifier is a dotted callable path. Its interface is `verify(token, keys) -> dict`, raising `ValueError` for invalid input. |
| `ACADEMY_HUB_IDENTITY_HEADER`, `ACADEMY_HUB_WEBHOOK_HEADER`, `ACADEMY_HUB_WEBHOOK_PATH`, `ACADEMY_HUB_ISSUER`, `ACADEMY_HUB_AUDIENCE` | Align headers, internal webhook route and issuer/audience with the proxy and sender. Webhook audience adds `:webhooks`. |
| `ACADEMY_HUB_ASSERTION_TTL`, `ACADEMY_HUB_WEBHOOK_TTL`, `ACADEMY_HUB_CLOCK_SKEW` | Lifetime and skew in seconds (60, 300 and 5). Preserve the same acceptance windows during rotation. |
| `ACADEMY_HUB_CONNECT_TIMEOUT`, `ACADEMY_HUB_READ_TIMEOUT`, `ACADEMY_HUB_API_RETRIES`, `ACADEMY_HUB_RETRY_BACKOFF`, `ACADEMY_HUB_CIRCUIT_FAILURES`, `ACADEMY_HUB_CIRCUIT_SECONDS`, `ACADEMY_HUB_DIRECTORY_TTL` | Outbound timeout, retry, outage and caching controls from §3. All durations are in seconds. |
| `ACADEMY_HUB_NAVIGATION_SOURCE`, `ACADEMY_HUB_NAVIGATION` | `settings` (default) or `identity`, and a JSON array of menu items when using settings. |

## Hub team acceptance checklist

- [ ] Confirm D-004, D-005, D-010 and D-011 (see `docs/decisions.md`) and exchange tenant UUIDs, public origin, trusted networks, separate credentials and key IDs through the agreed secure channel.
- [ ] Verify reverse-proxied URLs, redirects, scripts and static assets use the Hub origin and a single /academy prefix. Confirm source/header sanitization and that forging forwarded identity cannot authenticate a browser.
- [ ] Exercise valid, expired, tampered, wrong-audience and replayed assertions; rotate keys through an overlap window; exercise all three roles, known inactive membership and wrong-tenant requests.
- [ ] Verify Academy CSRF on a browser POST and successful same-origin playback setup. Verify direct storage CORS preflights, upload and HLS range requests from the Hub origin.
- [ ] Verify directory filtering, descendant membership, pagination, manager lookup and organization isolation against the examples. Retry each POST and confirm one mail delivery or one activity item.
- [ ] Deliver both webhook types. Verify wrong signatures fail, repeated nonce fails, and the original event with a new nonce and identical body is acknowledged without repeating effects.
- [ ] Simulate Hub service API errors and repeat under an open circuit. Continue signed learner heartbeat through the available proxy. Simulate proxy loss and verify resume from Academy's confirmed progress after recovery.


## 6. Dormant status and reactivation checklist

**Current state (2026-11-25): dormant.** The integration code and contract tests are retained
(T-015), Hub is disabled by default (D-031/T-033), and the platform does not require Hub to
boot, authenticate, mail, learn or report. The earlier H1 clarification (Hub-owned identity,
`grants_only`, single organization, Academy on the Hub domain) is **superseded** by D-032,
D-033, D-034 and D-035; it is not in force and must not guide new work.

Reactivation requires, in order:
1. An owner decision that supersedes D-031 for a named deployment, with a scope and date.
2. A security review of the wire format, key management, replay/nonce handling, tenant mapping
   and proxy trust (D-004/D-010).
3. A confirmed Hub contract version and test endpoint from the Hub owner.
4. Mapping rules: Hub organization → local `Organization`; Hub user reference → local `User` +
   `Membership`; Hub roles **never** become Academy permissions (D-034).
5. The full contract suite plus end-to-end sign-in, webhook, mail-off and outage tests on
   staging.
6. `ACADEMY_HUB_ENABLED=true` set only for that environment, with monitoring and an audit entry.

While dormant, `docs/access-control.md`, `docs/security.md` and `docs/api.md` remain authoritative;
this file never overrides them.
