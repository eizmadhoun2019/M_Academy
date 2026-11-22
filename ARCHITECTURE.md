# ARCHITECTURE — Current and Approved Design

**Last reviewed:** 2026-11-22
**Status:** Current (design approved; implementation starting from scratch)

## 1. Overview
Academy is a reusable Django app (`academy/`) deployed as a standalone Django + PostgreSQL
service on its own server. Masheed Hub owns the browser origin: it authenticates users,
reverse-proxies `/academy/*`, and injects a signed identity assertion. The browser talks
video bytes directly to private S3-compatible storage via presigned URLs; Academy processes
media in background workers (ffmpeg→HLS). All Academy data is tenant-scoped by
`organization_id` (single org in Phase 1, multi-tenant schema from day one).

Design principles: adapters are the only host seams; server is the source of truth for
progress; API-first (web and API share the same services); events over direct calls;
privacy by minimization (opaque `user_ref` only).

## 2. Context and actors
- Browser → Hub origin → (proxy `/academy/*`, strip prefix, inject signed identity) → Academy.
- Academy → Hub API (directory, mail, activity log) over HTTPS with service token.
- Hub → Academy: signed membership webhooks (`member_changed`, `member_deactivated`).
- Browser ↔ storage: presigned PUT uploads, presigned HLS playback (with `Range`).
- Actors: employee (learner), department_manager, platform_admin; HR via Academy grants.
- Trust boundaries: Hub↔Academy (signature-verified), browser↔storage (short-lived presigned),
  tenant boundary enforced in every query.

## 3. Technology and runtime
Python 3.12, Django 5.2 LTS, DRF + drf-spectacular, PostgreSQL 16+, Celery + Redis,
S3-compatible storage (MinIO dev), boto3/django-storages, ffmpeg/ffprobe, hls.js, pytest +
factory_boy, Playwright/axe, Locust. Server-rendered templates, vanilla ES modules, no build
step; Arabic (RTL, default) + English. Versions pinned in `pyproject.toml`.

## 4. Components and responsibilities
| Component | Responsibility | Depends on | Owner |
|---|---|---|---|
| `academy/models/` | Schema + constraints only | Django, Postgres | Tech authority |
| `academy/services/` | All business logic / write path | models, selectors, adapters, events | Tech authority |
| `academy/selectors/` | Read-only tenant-scoped queries | models | Tech authority |
| `academy/adapters/` | Identity/Org/Notify/Storage Protocols + loader | stdlib only | Tech authority |
| `academy/events/` | Signals + handlers (enqueue Celery) | services, adapters | Tech authority |
| `academy/api/v1/`, `academy/web/` | Thin views; declare capability, call services | services, selectors | Tech authority |
| `academy/tasks.py`, `academy/hooks.py` | Thin Celery entry points; host lifecycle hooks | services | Tech authority |
| `host_stub/` | Dev/test adapter implementations + Hub HTTP fake | (never imported by `academy/`) | Tech authority |
| Hub (external) | Sign-in, proxy, signed identity, webhooks, directory/mail API | — | Hub owner |

## 5. Data and information flows
**Canonical specification: `docs/domain-model.md`** (fields, types, constraints, indexes,
state machines, the progress algorithm and the retention table). This section is a summary
only; when the two disagree, `docs/domain-model.md` wins.

Key tenant-scoped entities: Course → CourseVersion (immutable once published) → Section →
Lesson; MediaAsset (awaiting_upload→uploaded→processing→ready|failed); Assignment
(user/department/role/organization target) → Enrollment (pinned to version); LessonProgress
(server frontier + merged watched ranges); CompletionRecord (immutable); Quiz tables (schema
only, Phase 2); ReminderLog, NotificationLog; AuditEvent (append-only, DB trigger);
PermissionGrant.
Enrollment gating: a lesson is accessible when all earlier required lessons are completed.
Completion: all required lessons + optional acknowledgment + explicit learner confirmation
(idempotent). Progress: server-clamped heartbeats, merged watched ranges, coverage threshold
(default 90%), forward skips rejected — algorithm in `docs/domain-model.md` §7.
Retention defaults: completion/audit 5 y, watched_ranges compaction 12 mo,
notification/reminder logs 90 d, stale uploads 24 h. Names/emails are never stored.
Schema additions adopted before T-006: course owner department, cover image, `organization`
assignment target, lesson summary (D-013…D-016).

## 6. Interfaces and integrations
- REST API `/api/v1/academy/` (error shape `{code, detail, fields}`; page size 25).
  Canonical endpoint inventory, capability per route, throttles and the complete error-code
  list: **`docs/api.md`**. Web pages are listed there in §10 and share the same services.
- Proposed Hub contract: `docs/hub-contract.md` — signed identity header (HMAC-SHA256
  proposal, key rotation, ~60 s lifetime, nonce replay protection), webhook envelope with
  signature over raw body, directory/mail/activity endpoints, idempotency keys. **Status:
  proposed — Hub-team confirmation pending.**
- Storage adapter Protocol: presign upload/download, stat, prefix delete; browser gets
  presigned PUT; playlists rewritten with presigned variant/segment URLs (TTL
  `max(30 min, 3×duration)`).
- Media pipeline: ffprobe validation → ffmpeg HLS 360p/720p, 6 s segments, H.264/AAC →
  `media_ready` event; 3 retries with backoff; stale `awaiting_upload` purged hourly.

## 7. Security and privacy design
Authorization in depth: view-declared capability → service recheck → object-level
(enrollment ownership / department scope) → tenant scope on every query. Capabilities:
`academy.learn | manage_content | assign | view_reports | admin`; effective access = Hub role
defaults ∪ active individual grants; optional grants-only mode; last-active-admin
protection; grant/revoke audited in the same transaction; denied admin actions audited.
Audited actions (canonical list — extend here first, per `docs/skills/audited-action.md`):
`course.created`, `course.updated`, `course.archived`, `version.published`,
`version.discarded`, `section.created|updated|deleted|reordered`,
`lesson.created|updated|deleted|reordered`, `media.upload_created`, `media.retry`,
`assignment.created`, `assignment.cancelled`, `enrollment.cancelled`,
`enrollment.completed_override`, `grant.created`, `grant.revoked`, `grant.denied`,
`settings.updated`, `user.exported`, `user.anonymized`.
Identity: only verified Hub assertions accepted (signature, issuer, audience, freshness,
single-use nonce via shared store); standalone dev uses database-backed sessions.
Secrets from env/secret manager; TLS everywhere; HSTS, CSP, `check --deploy` in CI;
CSV formula-injection neutralization; no PII in logs; audit immutability enforced by
PostgreSQL trigger.

## 8. Reliability and operations
Queues `default` / `media` / `notifications` + beat scheduler; all tasks idempotent and
retry-safe. Hub-dependency failure policy: short timeouts, bounded retries with idempotency
keys, circuit breaker; heartbeat/progress keep working during Hub API outage as long as the
proxy can issue identities. `/healthz` checks DB, Redis, storage; JSON logs with request IDs;
alerts on 5xx, p95, queue depth/age, media failures, backups, certificate expiry. Backups:
daily encrypted full DB backup off-host, 30-day retention; quarterly restore drills; RPO ≤ 24 h,
RTO ≤ 4 h. Two-server topology and proxy/TLS/Django settings per `docs/hub-contract.md`.
Development and test run in the project's own stack (compose project `m-academy`, own
ports, database, cache, buckets and volumes) beside the legacy deployment; the isolation
contract and safety rules are in `docs/operations/environments.md`.

## 9. Performance and scalability
Approved targets and workload assumptions: `docs/performance-profile.yaml` (owned by CHARTER).
Measured constraints will be recorded here after T-024 load testing; do not restate profile
values in this file.

## 10. Constraints and trade-offs
- Server-rendered UI + vanilla JS chosen over SPA: faster to ship, accessible, no build step;
  accepted UX limitation for highly interactive flows.
- ffmpeg processing in Celery (not external transcoding service): cost control, adds worker
  capacity planning (media queue, low concurrency).
- PostgreSQL-only: enables composite FKs, partial unique indexes, triggers; sacrifices
  easy SQLite fallback (dev/test use Postgres via Docker).
- Single-organization Phase 1 on a multi-tenant schema: slight modeling overhead, enables H2.

## 11. Architecture decisions
Consequential decisions (ADR-NNN). Expanded records live in `docs/adr/` when one is needed;
the text below is authoritative for ADR-001…ADR-011.
1. ADR-001 — Service layer: views/serializers thin, all logic in services.
2. ADR-002 — Opaque `user_ref`, no user FK; names/emails fetched, never stored.
3. ADR-003 — `organization_id` UUID on every table; `for_org` scoping.
4. ADR-004 — Immutable course versions; enrollments pinned to a version.
5. ADR-005 — Server-authoritative progress (heartbeat + range coverage).
6. ADR-006 — Direct-to-storage upload/playback; HLS; presigned playlist rewriting.
7. ADR-007 — Events via on-commit signals + Celery; handlers never do heavy work.
8. ADR-008 — PostgreSQL-only with DB-enforced invariants.
9. ADR-009 — Append-only audit in the caller's transaction (DB trigger).
10. ADR-010 — Hub reverse-proxy embedding (option A): Hub origin serves `/academy/*`;
    standalone deployment remains possible (option B API-first).
11. ADR-011 — Academy-stored individual permission grants combined with Hub role defaults.
12. ADR-012 — Membership is read from Hub on demand (60 s tenant cache) with no local
    membership projection; `member_changed` carries the refs needed for auto-enrollment.
13. ADR-013 — Watched coverage is stored as merged ranges on one `LessonProgress` row;
    no per-heartbeat rows (volume and privacy).

## 12. Current versus planned
**Current (2026-11-22):** documentation baseline only — this rebuild starts from scratch.
**Planned, in order:** foundation scaffold (T-001) → adapters/stub (T-002…T-004) → schema
(T-006…T-008, specified by `docs/domain-model.md`) → events/audit (T-005, T-012) →
authorization (T-009) → API foundation (T-011, specified by `docs/api.md`) → UI foundation
(T-013) → Hub HTTP integration (T-015) → Phase 1 features (content T-017, media T-018,
playback within T-018, assignments T-019, gating T-019, heartbeat T-020, completion T-020,
notifications T-021, reminders T-021, reports T-022, grants T-016) → hardening, E2E, ops,
security, privacy, pilot, release `v1.0.0` (T-024, GATE-1).
Labels: the Hub contract and identity format remain **proposed** until Hub-team confirmation.
