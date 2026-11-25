# CONFIGURATION — Settings, Upload Policy, Media, Pagination, Throttles

**Status:** Canonical for everything **except** Hub integration variables, which live in
`docs/hub-contract.md` §7 and are not duplicated here.
**Last updated:** 2026-11-22
**Consumed by:** T-001 (`.env.example`), T-002 (settings profiles), T-011, T-014, T-018.

All project settings use the `ACADEMY_` prefix and are read once at process start. A value
that is not listed here does not exist: adding one means adding a row. Secrets come from the
untracked `.env` in development and from the deployment's environment in production, and are
never committed (`docs/operations/environments.md` §1).

---

## 1. Core / Django

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | — required, ≥50 chars, generated at T-001 | Never reused from another project |
| `ACADEMY_ENV` | `development` | `development \| test \| production` |
| `ACADEMY_DEBUG` | `false` (true only in `development`) | Production refuses to start with `true` |
| `ACADEMY_ALLOWED_HOSTS` | `localhost,127.0.0.1` (dev) | Comma-separated |
| `ACADEMY_TIME_ZONE` | `UTC` | Storage and logs always UTC |
| `ACADEMY_BUSINESS_TZ` | `UTC` (D-002) | Reminder anchors and display only |
| `ACADEMY_DEFAULT_LANGUAGE` | `ar` | `ar \| en`; `LocaleMiddleware`, cookie `django_language` |
| `ACADEMY_SESSION_COOKIE_NAME` | `m_academy_sessionid` | Namespaced — never bare `sessionid` |
| `ACADEMY_SESSION_COOKIE_AGE` | `28800` (8 h) | Sliding: `SESSION_SAVE_EVERY_REQUEST=true` |
| `ACADEMY_LOGIN_URL` | `/academy/login/` | Start of sign-in in `standalone` mode; `hub` mode starts at the Hub |
| `ACADEMY_ACCESS_MODE` | `hub` (dev/test: `standalone`) | `hub` = verified Hub identity, no Academy login; `standalone` = local sign-in with trusted local membership (D-026). One record set; never a second organization |
| `ACADEMY_ORGANIZATION_ID` | the agreed organization UUID (`docs/hub-contract.md` §7 example) | The single tenant this deployment serves (D-026); a Hub assertion or session naming another organization is refused |
| `ACADEMY_AUTHORIZATION_MODE` | `role_plus_grants` (H1 production: `grants_only`) | Effective management authority (D-027). `grants_only` ignores Hub role defaults; `academy.learn` still needs active membership plus enrollment |
| `ACADEMY_HUB_ROLE_DEFAULTS` | `platform_admin=all; department_manager=own departments` | Role-to-capability map used only in `role_plus_grants`; mirrors `docs/api.md` §2 |
| `ACADEMY_MEMBERSHIP_RECONCILE_MINUTES` | `60` | Linked-user reconciliation interval (D-029); `0` disables the job |
| `ACADEMY_API_BODY_LIMIT_BYTES` | `2097152` (2 MiB) | Larger payloads → `413 payload_too_large` |
| `ACADEMY_DEVELOPMENT_LOGIN` | `true` in dev/test, `false` otherwise | Local identity stub |
| `ACADEMY_THROTTLES_ENABLED` | `true` (test profile: `false`) | Turns the documented rate counters on or off; disabling is a test-only setting, never a production choice |
| `ACADEMY_LOG_LEVEL` | `INFO` | JSON to stdout; never logs tokens, cookies, media URLs or emails |

Hub integration values (semantics and rotation in `docs/hub-contract.md` §5):

| Variable | Default | Notes |
|---|---|---|
| `ACADEMY_HUB_ORIGIN`, `ACADEMY_HUB_UPSTREAM_HOST`, `ACADEMY_TRUSTED_PROXY_NETWORKS` | empty | Exact public origin, private upstream host, trusted ingress CIDRs |
| `ACADEMY_PROXY_PATH_PREFIX`, `ACADEMY_STORAGE_CORS_ORIGIN` | `/academy`, empty | Public mount prefix and bucket CORS origin |
| `ACADEMY_HUB_API_BASE_URL`, `ACADEMY_HUB_API_TOKEN`, `ACADEMY_HUB_API_PATHS` | empty, empty, `{}` | Hub service URL, outbound bearer, optional path overrides |
| `ACADEMY_HUB_IDENTITY_KEYS`, `ACADEMY_HUB_WEBHOOK_KEYS` | `{}` | Separate JSON `kid` → secret maps; start-up refuses keys under 32 bytes in production |
| `ACADEMY_HUB_IDENTITY_VERIFIER` | empty | Dotted `module:callable` replacement verifier; the identity adapter is used when empty |
| `ACADEMY_HUB_IDENTITY_HEADER`, `ACADEMY_HUB_WEBHOOK_HEADER`, `ACADEMY_HUB_WEBHOOK_PATH` | `X-Masheed-Identity`, `X-Masheed-Webhook`, `/internal/hub/webhooks/` | Must match the proxy and sender |
| `ACADEMY_HUB_ISSUER`, `ACADEMY_HUB_AUDIENCE` | `masheed-hub`, `masheed-academy` | Webhook audience adds `:webhooks` |
| `ACADEMY_HUB_ASSERTION_TTL`, `ACADEMY_HUB_WEBHOOK_TTL`, `ACADEMY_HUB_CLOCK_SKEW` | `60`, `300`, `5` | Seconds; preserved across key rotation |
| `ACADEMY_HUB_CONNECT_TIMEOUT`, `ACADEMY_HUB_READ_TIMEOUT`, `ACADEMY_HUB_API_RETRIES`, `ACADEMY_HUB_RETRY_BACKOFF` | `0.5`, `1`, `1`, `0.1` | Transport behaviour of §3 |
| `ACADEMY_HUB_CIRCUIT_FAILURES`, `ACADEMY_HUB_CIRCUIT_SECONDS`, `ACADEMY_HUB_DIRECTORY_TTL` | `3`, `30`, `60` | Shared circuit and tenant directory cache |
| `ACADEMY_HUB_NAVIGATION_SOURCE`, `ACADEMY_HUB_NAVIGATION` | `settings`, `[]` | `settings` or `identity`, plus the settings-mode menu |

Proxy/TLS, CSRF-trusted origins, path prefix and storage CORS origin: `docs/hub-contract.md` §7.

## 2. Data stores

| Variable | Default (dev stack) | Notes |
|---|---|---|
| `ACADEMY_DB_HOST` / `_PORT` | `db` / `5432` | Host-side `127.0.0.1:5433` |
| `ACADEMY_DB_NAME` / `_USER` | `academy` / `academy` | Own instance, never the legacy one |
| `ACADEMY_DB_PASSWORD` | generated at T-001 | |
| `ACADEMY_DB_CONN_MAX_AGE` | `60` | Seconds; `CONN_HEALTH_CHECKS=true` |
| `ACADEMY_REDIS_URL` | `redis://redis:6379/0` | Cache DB 0, key prefix `macademy:` |
| `ACADEMY_CACHE_TTL_SECONDS` | `60` | Hub membership/directory cache (ADR-012) |
| `ACADEMY_CELERY_BROKER_URL` | `redis://redis:6379/1` | Own Redis instance |
| `ACADEMY_CELERY_RESULT_URL` | `redis://redis:6379/2` | Results kept 1 day |
| `ACADEMY_STORAGE_ENDPOINT` | `http://minio:9000` | `StorageAdapter` only |
| `ACADEMY_STORAGE_BUCKET` | `academy-media-dev` (`academy-media-test` in tests) | Never a legacy bucket |
| `ACADEMY_STORAGE_REGION` | `us-east-1` | MinIO ignores it |
| `ACADEMY_STORAGE_PATH_STYLE` | `true` in dev, `false` in production | |
| `ACADEMY_STORAGE_ACCESS_KEY` / `_SECRET_KEY` | generated at T-001 | |
| `ACADEMY_EMAIL_BACKEND` | SMTP → MailHog (`mailhog:1025`) in dev, Hub mail API in production | REQ-03 |

## 3. Upload policy (enforced twice: on request, then on `stat` verification)

| Variable | Default | Enforcement |
|---|---|---|
| `ACADEMY_UPLOAD_MAX_VIDEO_BYTES` | `2147483648` (2 GiB) | `400 upload_too_large` |
| `ACADEMY_UPLOAD_MAX_IMAGE_BYTES` | `10485760` (10 MiB) | `400 upload_too_large` |
| `ACADEMY_UPLOAD_MAX_DOCUMENT_BYTES` | `26214400` (25 MiB) | `400 upload_too_large` |
| `ACADEMY_UPLOAD_VIDEO_TYPES` | `video/mp4` | `400 unsupported_type` |
| `ACADEMY_UPLOAD_IMAGE_TYPES` | `image/png,image/jpeg,image/webp` | `400 unsupported_type` |
| `ACADEMY_UPLOAD_DOCUMENT_TYPES` | `application/pdf` | `400 unsupported_type` |
| `ACADEMY_UPLOAD_MAX_DURATION_SECONDS` | `14400` (4 h) | Checked after `ffprobe`; asset → `failed` with `duration_exceeded` |
| `ACADEMY_UPLOAD_URL_TTL_SECONDS` | `900` | Presigned `PUT` lifetime |
| `ACADEMY_UPLOAD_ABANDON_HOURS` | `24` | `awaiting_upload` older than this is purged |
| `ACADEMY_PLAYBACK_URL_TTL_SECONDS` | `300` | Presigned `GET` per playlist/segment request |

Rationale: 2 GiB at 2 Mbps ≈ 2.2 h of source, enough for any single lesson, and the presigned
`PUT` keeps the payload off the application server (performance profile body limit 2 MiB).
Raising a limit is a one-row change plus a test update.

## 4. Video pipeline (ffmpeg → HLS)

| Variable | Default | Notes |
|---|---|---|
| `ACADEMY_HLS_RENDITIONS` | `360p,720p` | Matches the `renditions` jsonb keys in `docs/domain-model.md` §2.5 |
| `ACADEMY_HLS_360P` | `640x360`, `800k` video, `96k` audio | Single-pass H.264 `main`, AAC stereo |
| `ACADEMY_HLS_720P` | `1280x720`, `2500k` video, `128k` audio | Source below 720p produces 360p only |
| `ACADEMY_HLS_SEGMENT_SECONDS` | `6` | Playlist window `0` (VOD) |
| `ACADEMY_HLS_GOP_FRAMES` | `48` | Fixed keyframe interval, `-sc_threshold 0`, aligned to segments |
| `ACADEMY_HLS_SEGMENT_TYPE` | `mpegts` | `ts` segments + `.m3u8`; no DRM in Phase 1 |
| `ACADEMY_TRANSCODE_TIMEOUT_SECONDS` | `3600` | Per asset |
| `ACADEMY_TRANSCODE_ATTEMPTS` | `2` retries (3 total) | Beyond that `409 retry_limit_reached` |
| `ACADEMY_KEEP_ORIGINALS` | `false` | Original object deleted after `ready` when false |

Storage layout: `org/<organization_id>/media/<asset_id>/original.<ext>`,
`.../hls/<rendition>/index.m3u8`, `.../hls/<rendition>/seg-<n>.ts`, `.../poster.jpg`.
Playback URLs are minted per request and never stored (`docs/domain-model.md` §6).

## 5. Pagination and result limits

| Variable | Default | Notes |
|---|---|---|
| `ACADEMY_PAGE_SIZE` | `25` | Matches the performance profile |
| `ACADEMY_MAX_PAGE_SIZE` | `100` | Larger values are clamped silently, not rejected |
| `ACADEMY_CURSOR_PAGE_SIZE` | `50` | Cursor endpoints: report rows, audit search |
| `ACADEMY_PREVIEW_RECIPIENT_CAP` | `5000` | D-017 |

## 6. Throttles (DRF scoped throttles + middleware for web views)

| Scope | Rate | Applies to |
|---|---|---|
| `anon` | `20/min` per IP | Unauthenticated requests |
| `login` | `10/min` per IP | Development login and Hub callback |
| `heartbeat` | `30/min` per user | `POST …/progress/` (nominal load is 4/min) |
| `playback` | `30/min` per user | `POST …/playback/` |
| `read` | `120/min` per user | Default for `GET` endpoints |
| `write` | `60/min` per user | Default for management `POST/PATCH/DELETE` |
| `export` | `5/hour` per user | CSV and privacy export |
| `webhook` | `600/min` per source IP | Hub webhook route |

Rates are per process-independent (Redis-backed). Exceeding returns `429 rate_limited` with
`Retry-After`. The heartbeat rate leaves 7× headroom over design load so a client retrying
after a network drop is never locked out, while a scripted cursor-scrub loop is (it also
trips `progress_skip_rejected`).

## 7. Values deliberately left to the database or the owner

| Item | Where it lives | Why not an env var |
|---|---|---|
| Completion threshold (default 90%) | `Organization settings`, default `DEFAULT_COMPLETE_PERCENT` | Per-organization business rule |
| Retention windows | `Organization settings`, defaults per `docs/domain-model.md` §8 | Legal/management decision (D-003) |
| Grants-only mode | `Organization settings` | Toggled by an admin, audited |
| Business time zone | `ACADEMY_BUSINESS_TZ` (D-002) | Deployment-wide |

## 8. Test profile overrides

`ACADEMY_ENV=test` forces: in-memory email, eager Celery, `MEDIA` on a temp dir, storage
adapter `InMemoryStorage` or MinIO `academy-media-test`, throttle rates disabled
(`ACADEMY_THROTTLES_ENABLED=false`), fixed clock injected through the clock service, and
`ACADEMY_UPLOAD_MAX_*` lowered so oversize tests do not write gigabytes.

## 9. `.env.example` contract (created at T-001)

Contains every variable of §1–§6 with placeholder values and a comment naming the owning
document. No secret, no real host, no legacy value. `git check-ignore .env` must pass
(`docs/operations/environments.md` §7 item 9).

## 10. Logging and request ids

Every process writes one JSON object per line to stdout, so the container runtime collects a
stream that needs no parsing rule:

| Field | Meaning |
|---|---|
| `ts` | UTC ISO 8601 with milliseconds |
| `level` | `DEBUG` … `CRITICAL` |
| `logger` | Dotted logger name |
| `service` | `academy` |
| `env` | Value of `ACADEMY_ENV` |
| `message` | Rendered message; never a token, cookie, email or media URL (§1) |
| `request_id` | Present only inside a request |
| `exception` / `stack` | Present only when the record carries them |

A request id is accepted from the inbound `X-Request-ID` header only when it matches
`[A-Za-z0-9._-]{1,64}`; anything else is replaced by a generated 32-character id, which is also
returned in `X-Request-ID` on the response. This is what makes a support report traceable to
the lines it produced.

## 11. Adapters

`academy/` reaches the host only through four seams (`ARCHITECTURE.md` §4). Each seam is named
by a `module.path:ClassName` value, resolved on first use by `academy.adapters.loader` and
cached for the process lifetime. An empty value means **not configured**: the loader raises
`AdapterNotConfigured` instead of substituting a default, so a deployment that forgot an
adapter fails on the first call rather than degrading silently. `academy` itself never imports
`host_stub` or a provider SDK (gate G7); only the configured class does.

| Variable | Seam | Default | Notes |
|---|---|---|---|
| `ACADEMY_ADAPTER_IDENTITY` | `identity` | `host_stub.identity:DevelopmentIdentity` (dev/test), empty in production | Signed-identity verification (T-015 adds the Hub verifier) |
| `ACADEMY_ADAPTER_ORGANIZATION` | `organization` | `host_stub.organization:StubDirectory` (dev/test), empty in production | Hub directory lookups (ADR-012) |
| `ACADEMY_ADAPTER_NOTIFY` | `notify` | `host_stub.notify:RecordingNotifier` (dev/test), empty in production | Mail and activity log; never called from a request cycle |
| `ACADEMY_ADAPTER_STORAGE` | `storage` | `host_stub.storage:InMemoryStorage` (dev/test), empty in production | Presign/stat/delete for media (D-001 keeps the provider open) |

The development and test profiles fill any empty value with the stub above, so a fresh clone
runs without a Hub or a bucket; the production profile keeps the empty value and therefore
fails at the first call until the deployment supplies a real implementation. Each seam has a
contract suite under `tests/contracts/` — an implementation is accepted when that suite passes,
which is how T-015's Hub transports and T-018's bucket implementation land without changing
their callers.
