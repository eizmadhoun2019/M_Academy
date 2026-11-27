# CONFIGURATION — Settings, Upload Policy, Media, Pagination, Throttles

**Status:** Canonical for everything **except** Hub integration variables, which live in
`docs/hub-contract.md` §7 and are not duplicated here.
**Last updated:** 2026-11-25
**Consumed by:** T-001 (`.env.example`), T-002 (settings profiles), T-011, T-014, T-018,
T-027…T-030, T-034.

All project settings use the `ACADEMY_` prefix and are read once at process start. A value not
listed here does not exist: adding one means adding a row. Secrets come from the untracked
`.env` in development and from the deployment environment in production; they are never
committed (`docs/operations/environments.md` §7).

---

## 1. Core / Django

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | — required, ≥50 chars | Never reused from another project |
| `ACADEMY_ENV` | `development` | `development \| test \| staging \| production` |
| `ACADEMY_DEBUG` | `false` (true only in `development`) | Production refuses to start with `true` |
| `ACADEMY_ALLOWED_HOSTS` | `localhost,127.0.0.1` (dev) | Comma-separated; no wildcard in production |
| `ACADEMY_PUBLIC_BASE_URL` | `http://localhost:8101` | Absolute links in mail and public pages; never derived from the request `Host` |
| `ACADEMY_TIME_ZONE` | `UTC` | Storage and logs always UTC |
| `ACADEMY_DEFAULT_LANGUAGE` | `ar` | `ar \| en`; fallback when a company/user has no preference; `LocaleMiddleware` |
| `ACADEMY_SESSION_COOKIE_NAME` | `m_academy_sessionid` | Namespaced — never bare `sessionid` |
| `ACADEMY_SESSION_COOKIE_AGE` | `43200` (12 h) | Absolute lifetime |
| `ACADEMY_SESSION_IDLE_MINUTES` | `30` | Server-side last-activity check; no per-request write |
| `ACADEMY_SESSION_SAVE_EVERY_REQUEST` | `false` | Must stay false; idle timeout is enforced by middleware |
| `ACADEMY_LOGIN_URL` | `/academy/login/` | Start of sign-in; Hub is never the login page (D-035) |
| `ACADEMY_ACCESS_MODE` | `standalone` | `standalone` (local accounts, always works) or `hub` (optional signed identity for an integrated deployment). Hub mode requires `ACADEMY_HUB_ENABLED=true`; it never disables local admin recovery. |
| `ACADEMY_DEVELOPMENT_LOGIN` | `false` | Development-only identity stub. Startup refuses it when `DEBUG=false` or `ACADEMY_ENV=production`; tests assert this. |
| `ACADEMY_API_BODY_LIMIT_BYTES` | `2097152` (2 MiB) | Larger → `413 payload_too_large` |
| `ACADEMY_THROTTLES_ENABLED` | `true` (test profile: `false`) | Test-only off switch; never a production choice |
| `ACADEMY_LOG_LEVEL` | `INFO` | JSON to stdout; never tokens, cookies, media URLs, emails or names |
| `ACADEMY_DEFAULT_FROM_EMAIL` | `no-reply@academy.invalid` | Replaced by a real sender in production |
| `ACADEMY_SUPPORT_EMAIL` | empty | Shown on public contact page and in failure mail footers |
| `ACADEMY_COMPANY_NAME` | `مشيد` | Brand line on the public site; not a tenant name |

## 2. Authentication, sessions and security

| Variable | Default | Notes |
|---|---|---|
| `ACADEMY_PASSWORD_MIN_LENGTH` | `12` | Django validators; no forced composition |
| `ACADEMY_LOGIN_MAX_FAILURES` | `5` | Per email+IP per window |
| `ACADEMY_LOGIN_WINDOW_SECONDS` | `900` | 15 min; then exponential backoff |
| `ACADEMY_LOGIN_IP_MAX_FAILURES` | `20` | Per IP per window |
| `ACADEMY_MFA_ENCRYPTION_KEY` | — required in production | Long random string; hashed to the 32-byte key that encrypts TOTP secrets, so rotation re-encrypts |
| `ACADEMY_MFA_REQUIRED_ROLES` | `super_admin,company_admin` | Roles that must present a second factor; the codes activate with the T-028 role catalogue, and a role configured here must also exist there |
| `ACADEMY_MFA_CHALLENGE_TTL_SECONDS` | `300` | Lifetime of a single-use sign-in challenge |
| `ACADEMY_MFA_ISSUER` | `Masheed Academy` | Issuer shown in the authenticator application |
| `ACADEMY_PUBLIC_ORIGIN` | empty | Absolute origin used in mailed account links; never the request's `Host` header |
| `ACADEMY_EMAIL_VERIFICATION_TTL_SECONDS` | `86400` | 24 h |
| `ACADEMY_PASSWORD_RESET_TTL_SECONDS` | `3600` | 1 h |
| `ACADEMY_INVITATION_TTL_SECONDS` | `604800` | 7 days |
| `ACADEMY_SESSION_COOKIE_SECURE` | `true` in staging/production | Must be true outside development |
| `ACADEMY_CSRF_TRUSTED_ORIGINS` | empty | Comma-separated exact origins; no wildcard |
| `ACADEMY_SECURE_SSL_REDIRECT` | `true` in staging/production | Proxy must forward the scheme |
| `ACADEMY_HSTS_SECONDS` | `31536000` in production | `includeSubDomains` only after D-005 confirms |
| `ACADEMY_CSP_STORAGE_ORIGIN` | empty | Storage host allowed in `media-src`/`connect-src`; required in production |
| `ACADEMY_TRUSTED_PROXY_NETWORKS` | empty | Only these peers may supply `X-Forwarded-For`/proto |

## 3. Data stores

| Variable | Default (dev stack) | Notes |
|---|---|---|
| `ACADEMY_DB_HOST` / `_PORT` | `db` / `5432` | Host-side `127.0.0.1:5433` |
| `ACADEMY_DB_NAME` / `_USER` | `academy` / `academy` | Own instance, never the legacy one |
| `ACADEMY_DB_PASSWORD` | generated | |
| `ACADEMY_DB_CONN_MAX_AGE` | `60` | Seconds; `CONN_HEALTH_CHECKS=true` |
| `ACADEMY_REDIS_URL` | `redis://redis:6379/0` | Cache DB 0, prefix `macademy:` |
| `ACADEMY_CACHE_TTL_SECONDS` | `60` | Authorization/company-context cache; never a permission long-cache |
| `ACADEMY_CELERY_BROKER_URL` | `redis://redis:6379/1` | Own Redis instance |
| `ACADEMY_CELERY_RESULT_URL` | `redis://redis:6379/2` | Results kept 1 day |
| `ACADEMY_STORAGE_ENDPOINT` | `http://minio:9000` | `StorageAdapter` only |
| `ACADEMY_STORAGE_BUCKET` | `academy-media-dev` (`academy-media-test` in tests) | Never a legacy bucket |
| `ACADEMY_STORAGE_REGION` | `us-east-1` | MinIO ignores it |
| `ACADEMY_STORAGE_PATH_STYLE` | `true` in dev, `false` in production | |
| `ACADEMY_STORAGE_ACCESS_KEY` / `_SECRET_KEY` | generated | |

## 4. Mail (D-036)

| Variable | Default | Notes |
|---|---|---|
| `ACADEMY_MAIL_TRANSPORT` | `smtp` (`console` in test) | `smtp \| console \| locmem \| hub`; `hub` only when Hub is enabled |
| `ACADEMY_SMTP_HOST` / `_PORT` | `mailhog` / `1025` (dev) | Production uses the provider's host |
| `ACADEMY_SMTP_USER` / `_PASSWORD` | empty | Never logged |
| `ACADEMY_SMTP_USE_TLS` / `_USE_SSL` | `false` / `false` | Exactly one may be true |
| `ACADEMY_SMTP_TIMEOUT_SECONDS` | `10` | Connection/read timeout |
| `ACADEMY_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` | Kept for Django compatibility; `ACADEMY_MAIL_TRANSPORT` decides the adapter |
| `ACADEMY_EMAIL_RETRY_ATTEMPTS` | `3` | Notification task retries |
| `ACADEMY_EMAIL_RETRY_BACKOFF_SECONDS` | `60` | Exponential |

Sender identity: company `sender_name` if set, else `ACADEMY_COMPANY_NAME`; address is always
`ACADEMY_DEFAULT_FROM_EMAIL` in H1.5 (per-company domains are H2). SPF/DKIM/DMARC are deployment
tasks, not settings.

## 5. Upload policy (enforced twice: on request, then on `stat` verification)

| Variable | Default | Enforcement |
|---|---|---|
| `ACADEMY_UPLOAD_MAX_VIDEO_BYTES` | `2147483648` (2 GiB) | `400 upload_too_large` |
| `ACADEMY_UPLOAD_MAX_IMAGE_BYTES` | `10485760` (10 MiB) | `400 upload_too_large` |
| `ACADEMY_UPLOAD_MAX_DOCUMENT_BYTES` | `26214400` (25 MiB) | `400 upload_too_large` |
| `ACADEMY_UPLOAD_VIDEO_TYPES` | `video/mp4` | `400 unsupported_type` |
| `ACADEMY_UPLOAD_IMAGE_TYPES` | `image/png,image/jpeg,image/webp` | `400 unsupported_type` |
| `ACADEMY_UPLOAD_DOCUMENT_TYPES` | `application/pdf` | `400 unsupported_type` |
| `ACADEMY_UPLOAD_MAX_DURATION_SECONDS` | `14400` (4 h) | After `ffprobe`; asset → `failed` `duration_exceeded` |
| `ACADEMY_UPLOAD_URL_TTL_SECONDS` | `900` | Presigned `PUT` lifetime |
| `ACADEMY_UPLOAD_ABANDON_HOURS` | `24` | `awaiting_upload` older than this is purged |
| `ACADEMY_PLAYBACK_URL_TTL_SECONDS` | `300` | Presigned `GET` per playlist/segment |

Rationale: 2 GiB at 2 Mbps ≈ 2.2 h of source, enough for one lesson; the presigned `PUT` keeps
payloads off the application server (2 MiB body limit). Raising a limit is a row plus a test.

## 6. Video pipeline (ffmpeg → HLS)

| Variable | Default | Notes |
|---|---|---|
| `ACADEMY_HLS_RENDITIONS` | `360p,720p` | Matches `renditions` jsonb keys |
| `ACADEMY_HLS_360P` | `640x360,800k,96k` | Single-pass H.264 `main`, AAC stereo |
| `ACADEMY_HLS_720P` | `1280x720,2500k,128k` | Source below the height produces that rendition only |
| `ACADEMY_HLS_SEGMENT_SECONDS` | `6` | Playlist window `0` (VOD) |
| `ACADEMY_HLS_GOP_FRAMES` | `48` | Fixed keyframe interval, `-sc_threshold 0` |
| `ACADEMY_HLS_SEGMENT_TYPE` | `mpegts` | `.ts` + `.m3u8`; no DRM in H1.5 |
| `ACADEMY_TRANSCODE_TIMEOUT_SECONDS` | `3600` | Per asset |
| `ACADEMY_TRANSCODE_ATTEMPTS` | `2` retries (3 total) | Beyond → `409 retry_limit_reached` |
| `ACADEMY_KEEP_ORIGINALS` | `false` | Original deleted after `ready` when false |

Storage layout: `org/<organization_id>/media/<asset_id>/original.<ext>`,
`.../hls/<rendition>/index.m3u8`, `.../hls/<rendition>/seg-<n>.ts`, `.../poster.jpg`.
Playback URLs are minted per request and never stored.

## 7. Values that belong to the company (not env vars)
Organization settings are edited by a Company Admin (`academy.settings.manage`) and audited.
They are the source of truth; environment values are only platform fallbacks.

| Setting | Default | Notes |
|---|---|---|
| Display name (ar/en) | from the Organization row | Used in UI, mail, reports |
| Default language | `ar` | Applies to members without a personal preference |
| Time zone | `Asia/Riyadh` | Reminder hour and date display; storage stays UTC (D-038) |
| Reminder hour | `08:00` local | 0–23 |
| Sender name | platform default | Mail from-name |
| Completion threshold | `90` | Per lesson default; 50–100 |
| Retention overrides | platform defaults | Bounded by legal minimum/maximum |
| Department tree | — | Managed in N3 |

## 8. Pagination and result limits

| Variable | Default | Notes |
|---|---|---|
| `ACADEMY_PAGE_SIZE` | `25` | Matches the performance profile |
| `ACADEMY_MAX_PAGE_SIZE` | `100` | Larger values are clamped, not rejected |
| `ACADEMY_CURSOR_PAGE_SIZE` | `50` | Report rows, audit search |
| `ACADEMY_PREVIEW_RECIPIENT_CAP` | `5000` | D-017 |

## 9. Throttles (DRF scoped throttles + middleware for web views)

| Scope | Rate | Applies to |
|---|---|---|
| `anon` | `20/min` per IP | Unauthenticated requests |
| `login` | `5/15 min` per email+IP, `20/15 min` per IP | Login, reset request, verification resend |
| `heartbeat` | `30/min` per user | `POST …/progress/` (nominal 4/min) |
| `playback` | `30/min` per user | `POST …/playback/` |
| `read` | `120/min` per user | Default `GET` |
| `write` | `60/min` per user | Management `POST/PATCH/DELETE` |
| `export` | `5/hour` per user | CSV and privacy export |
| `webhook` | `600/min` per source IP | Hub webhook route (only when enabled) |

Redis-backed, per process-independent. Exceeding returns **429 `throttled`** with `Retry-After`.
The heartbeat rate leaves 7× headroom over design load so a client retrying after a network drop
is not locked out, while a scripted cursor-scrub loop is (it also trips
`progress_skip_rejected`).

## 10. Observability (D-039)

| Variable | Default | Notes |
|---|---|---|
| `ACADEMY_METRICS_ENABLED` | `true` in staging/production | Exposes `/metrics` on the internal network |
| `SENTRY_DSN` | empty | Error reporting; scrubs cookies/headers/bodies |
| `ACADEMY_TRACE_SAMPLE_RATE` | `0.05` | Trace propagation sample; 0 disables |
| `ACADEMY_SLOW_QUERY_MS` | `500` | Logs a warning with the SQL fingerprint (no parameters) |
| `ACADEMY_HEALTH_TIMEOUT_SECONDS` | `2` | `/healthz` dependency check budget |

## 11. Test profile overrides

`ACADEMY_ENV=test` forces: in-memory mail, eager Celery, media on a temp dir, storage adapter
`InMemoryStorage` or MinIO `academy-media-test`, throttling disabled
(`ACADEMY_THROTTLES_ENABLED=false`), fixed clock through the clock service, dev login allowed only
when `ACADEMY_DEBUG=true` **and** the test settings module is loaded, and lowered upload limits so
oversize tests do not write gigabytes. A test asserts that `ACADEMY_ENV=production` with
`ACADEMY_DEVELOPMENT_LOGIN=true` fails startup.

## 12. `.env.example` contract
Contains every variable of §1–§6 and §10 with placeholder values and a comment naming the owning
document. No secret, no real host, no legacy value. `git check-ignore .env` must pass. Adding a
variable updates this file in the same commit.

## 13. Logging and request ids
Every process writes one JSON object per line to stdout.

| Field | Meaning |
|---|---|
| `ts` | UTC ISO 8601 with milliseconds |
| `level` | `DEBUG` … `CRITICAL` |
| `logger` | Dotted logger name |
| `service` | `academy` |
| `env` | `ACADEMY_ENV` |
| `message` | Rendered message; never a token, cookie, email, name or media URL |
| `request_id` | Inside a request |
| `company_id` | Company context derived from the single membership, when known (UUID); platform route id when explicit |
| `user_id` | Actor UUID when known (never email) |
| `route` | URL name, not the raw path with ids |
| `duration_ms` | Request duration |
| `exception` / `stack` | Only when the record carries them |

A request id is accepted from `X-Request-ID` only when it matches `[A-Za-z0-9._-]{1,64}`;
anything else is replaced by a generated 32-character id, also returned in `X-Request-ID`.

## 14. Adapters and transports
External seams are named by `module.path:ClassName`, resolved on first use and cached per process.
An empty value means **not configured**: the loader raises `AdapterNotConfigured` instead of
substituting a default, so a deployment fails on first call rather than degrading silently.
`academy` never imports `host_stub` or a provider SDK (gate G7).

| Variable | Seam | Default | Notes |
|---|---|---|---|
| `ACADEMY_ADAPTER_IDENTITY` | `identity` | `host_stub.identity:DevelopmentIdentity` (dev/test), empty in production | Only used when `ACADEMY_ACCESS_MODE=hub` |
| `ACADEMY_ADAPTER_ORGANIZATION` | `organization` | `host_stub.organization:StubDirectory` (dev/test), empty | Hub directory; not used in standalone |
| `ACADEMY_ADAPTER_NOTIFY` | `notify` | `host_stub.notify:RecordingNotifier` (dev/test), empty | Optional Hub activity mirror; local mail is `ACADEMY_MAIL_TRANSPORT` |
| `ACADEMY_ADAPTER_STORAGE` | `storage` | `host_stub.storage:InMemoryStorage` (dev/test), empty in production | Presign/stat/delete (D-001) |

Each seam has a contract suite under `tests/contracts/`; an implementation is accepted when that
suite passes. Development/test fill empty values with the stubs so a fresh clone runs without Hub
or a bucket.
