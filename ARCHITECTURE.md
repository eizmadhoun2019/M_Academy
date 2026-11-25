# ARCHITECTURE — Target Design and Current Implementation

**Status:** Canonical architecture. Requirements are owned by `CHARTER.md`; this file owns the
design. Schema details: `docs/domain-model.md`. Permissions: `docs/access-control.md`.
Security controls: `docs/security.md`.
**Last reviewed:** 2026-11-25

## 1. Overview
Masheed Academy is a **modular monolith**: one Django + PostgreSQL service, one deployable
image, with explicit internal module boundaries. It serves a **public website** on `/` and an
authenticated **application** on `/academy/`, for **multiple companies** over one database.
Every company-owned row is scoped to an `Organization`; every tenant query resolves exactly one
company context from the caller's single membership (or, for platform-only routes, from an
explicit authorized company id) before it runs.

The platform is standalone-first: local accounts, local memberships, local authorization,
local mail. Hub is an optional integration behind adapters and a feature flag; it is disabled
by default and is not on the launch path.

Design principles: modular boundaries; API-first; server is the source of truth; configuration
over code; security by design; tenant isolation at every layer; append-only audit; i18n from
the start; documentation-driven delivery.

## 2. Context and actors
- **Visitor** → public site `/` (no session): content, languages, contact, login entry.
- **Account holder** → `/academy/` sign-in, verification and reset; after authentication the
  single membership selects the company server-side and the user lands on the dashboard their
  permissions allow. No company chooser or switcher is part of H1.5.
- **Member** → company-scoped app: learning, management or administration by permission.
- **Platform administrator** → company lifecycle, platform users/roles, platform audit,
  audited read access to company data with explicit company context.
- **Background workers** → media, notifications, reminders, retention; always run inside a
  company context derived from the record, never from a request.
- **External systems** (optional): Hub identity/directory/mail, object storage, SMTP provider.
- Trust boundaries: browser ↔ application; application ↔ storage (presigned, key-scoped);
  company ↔ company (hard boundary); platform role ↔ company data (explicit, audited
  context); application ↔ optional integration (signed, disabled by default).

## 3. Technology and runtime
Python 3.12, Django 5.2 LTS, DRF + drf-spectacular, PostgreSQL 16+, Celery + Redis,
S3-compatible storage, boto3/django-storages, ffmpeg/ffprobe, hls.js, pytest + factory_boy,
Playwright/axe, Locust. Server-rendered templates, vanilla ES modules, no build step. Arabic
(RTL, default) and English (LTR). Versions pinned in `pyproject.toml`. No new runtime
dependency is added without an approved need (`RULES.md`).

## 4. Modules and dependency rules
The current package layout is retained; these are **logical boundaries**, not a demand for one
Django app per row. No circular imports; a module may use only the layers below it.

| Module | Responsibility | May depend on |
|---|---|---|
| `academy.models` | Schema, constraints, indexes, state fields | Django, PostgreSQL |
| `academy.tenancy` (target, `academy/organizations/`) | Organization, Department, Membership, server-derived company context, company settings | models |
| `academy.accounts` (target) | User, invitations, verification/reset, sessions, MFA, login security | models, tenancy, adapters.notify |
| `academy.authorization` | Permission catalogue, roles, scopes, effective access, guards | tenancy, models |
| `academy.catalog` (`academy/services`, `selectors` for content) | Courses, versions, sections, lessons, publish rules | models, authorization |
| `academy.media` | Upload policy, processing, playback authorization | models, storage adapter, authorization |
| `academy.learning` (`academy/progress.py`) | Enrollment, heartbeat, gating, completion | models, authorization |
| `academy.assignments` | Target expansion, assignment lifecycle, roster | models, tenancy, authorization |
| `academy.reports` | Scoped read models, CSV, platform aggregation | selectors, authorization |
| `academy.notifications` | Message catalogue, queue, transport, reminders | models, tenancy, notify adapter |
| `academy.audit` | Append-only ledger and audit queries | models |
| `academy.api`, `academy.web` | Thin HTTP layer: parse, authorize, call a service/selector, render | all below |
| `academy.integrations` (`academy/hub`) | Optional Hub identity/directory/mail/webhooks | adapters only |
| `academy.adapters` | Protocols + loader for external seams | stdlib only |
| `config` | Settings, URLs, middleware, health, WSGI/ASGI | academy |

Rules:
1. Business rules live in services/selectors, never in views, serializers, templates, tasks or
   middleware.
2. `academy` never imports `host_stub`, a provider SDK, or `config`. Provider code lives behind
   an adapter.
3. Authorization is declared in the HTTP layer (permission + allowed scopes) and **rechecked**
   in the service with the object's company and scope.
4. Cross-module writes go through the owning module's service; no module updates another
   module's tables directly.
5. Background tasks receive record ids, reload the row, derive its company, and call the same
   service as a web request.
6. `docs/` is the only design input; no behavior is added because a legacy or third-party
   mockup contains it.

## 5. Tenancy and identity design
- `Organization` is a real row. `Membership` links one `User` to one `Organization` and carries
  its own status, roles and scope. Account status, membership status and company status are
  independent.
- Every tenant table has an `organization` FK (`PROTECT`). Cross-entity consistency is enforced
  with composite foreign keys `(organization_id, id)`, so a child can never point at another
  company's parent.
- One company context per request. For a normal user it is derived server-side from the single
  `Membership` (`UNIQUE (user_id)`); no client-supplied organization id is accepted and there is
  no switching path. A platform-only account has no membership and no tenant context; platform
  routes carry an explicit company id and are separately authorized and audited. Behind Hub, a
  verified assertion may map to that same single membership; Hub never creates a second one.
- Platform roles live in `PlatformRoleAssignment` and are separate from company roles; platform
  administrators never receive a synthetic membership or a company row.
- Account and membership lifecycle: invitation → active → suspended/removed; company status
  active/suspended/archived. There is at most one membership row per account. Removal preserves
  training history and is terminal for that account's tenant access; re-adding the same person
  in the same company reuses and restores that row only before anonymization, while a move to a
  different company is out of scope (D-043). A second membership is rejected at the database,
  service and test layers.
- Users are identified by UUID, never by email. Email is a unique, changeable login attribute;
  relations use the user/membership FK (`docs/domain-model.md`).

## 6. Authorization design
`docs/access-control.md` is the single source: permission codes, default roles, scopes, grant
rules, enforcement and test matrix. Summary: functional permissions; system roles plus custom
roles; multiple roles per membership; exceptional grants; scopes `PLATFORM`, `COMPANY`,
`DEPARTMENT(S)`, `SELF`; deny by default; last platform admin and last active company admin
protected; every permission change audited. UI navigation and actions are rendered from the
effective permission set, and the server rechecks every request. A hidden button is never the
control.

## 7. Data and information flows
**Canonical schema: `docs/domain-model.md`.** Summary: Organization → at most one Membership
per User → Role/Permission assignments; Department tree; Course → Version (immutable once published) → Section
→ Lesson; MediaAsset; Assignment → Enrollment → LessonProgress → CompletionRecord; quiz tables
(schema only); ReminderLog, NotificationLog; AuditEvent; optional Hub webhook receipts.

- Enrollment pins a published version; a later publish never changes an existing enrollment.
- Progress: server-clamped heartbeats, merged watched ranges, forward skips rejected, completion
  at the configured coverage threshold (algorithm: `docs/domain-model.md` §7).
- Media flows direct to object storage with presigned URLs; keys are
  `org/<organization_id>/media/<asset_id>/...`.
- Read models for reports are tenant- and scope-filtered; a platform aggregate requires the
  platform permission and names its company filter explicitly.

### Database and performance strategy
- UUID primary keys; existing v4 keys are kept. **UUIDv7 is adopted for new tables only when a
  standard/approved implementation is available** (D-041); until then v4 plus `created_at`
  indexes provide ordering for hot queries.
- Foreign keys with `PROTECT` by default for history-bearing rows; `SET NULL` only for optional
  references; soft lifecycle states instead of deleting history.
- Unique/check constraints enforce invariants in PostgreSQL; partial and composite indexes are
  added for measured query patterns and start with `organization_id` in tenant tables.
- Every list endpoint has a bounded page size and a query budget. N+1 is prevented with
  `select_related`/`prefetch_related` and caught by query-count tests. Plans are checked with
  `EXPLAIN (ANALYZE, BUFFERS)` for hot queries before the gate.
- Migrations are forward-only in production, reversible in development, reviewed for locks and
  backfills; large backfills run in batches.
- **Row-level security:** assessed and deferred (ADR-027). The application role owns the tables
  and workers/migrations share it; RLS would add a second, easily-bypassed policy layer without
  removing the need for scoped ORM access. Revisit at H2 or on a regulatory requirement.
- **Partitioning:** deferred. Trigger to revisit: audit or progress tables above ~50 M rows, or
  p95 degradation attributable to those tables. Candidate keys documented, not implemented.
- **Transactional outbox:** not adopted (ADR-028). Local state is the truth and the notification
  queue is durable; an outbox is introduced only when an external side effect must be
  exactly-once across a process boundary.

## 8. Interfaces and integrations
- REST API `/api/v1/academy/` — inventory, error codes, auth and compatibility policy:
  `docs/api.md`. Web pages share the same services.
- Public web routes are separate from the app (`/` vs `/academy/`), with their own URL
  namespace and templates; they share the design system.
- Mail: swappable transport, SMTP default (`docs/configuration.md`). Hub mail is optional.
- Storage adapter: presign upload/download, stat, prefix delete; player gets short-lived
  presigned HLS URLs.
- Hub integration: signed identity, directory, webhooks, mail/activity, retained and tested,
  **disabled by default**; routes return 404 and no task runs while disabled
  (`docs/hub-contract.md`). Reactivation is a decision + security review + acceptance run.
- No integration framework is built ahead of need; a new integration uses the adapter pattern.

## 9. Security and privacy
`docs/security.md` is canonical; this section states the architectural placement only:
defense in depth (route permission → service recheck → object/company check → query scope →
constraint), Django authentication with Argon2, session security and revocation, MFA for
sensitive roles, CSRF, CSP without inline code, secure cookies, throttling, upload validation,
formula-safe CSV, no secrets or tokens in logs, append-only audit, minimal PII with retention
and export/anonymization. Error responses never reveal another company's object or a user's
existence.

## 10. Reliability and operations
- Queues `default`, `media`, `notifications`; idempotent tasks; retries with bounded backoff;
  one beat process.
- Reminder evaluation runs per company time zone; the scheduler evaluates due companies once
  per hour and the task itself is idempotent (`docs/background-jobs.md`).
- `/healthz` checks DB, cache and storage. JSON logs with request id; metrics, tracing and error
  reporting per `docs/operations/environments.md` §9.
- Environments: development, test, staging, production; one image promoted; migrations run as a
  release step; rollback keeps the previous image and a compatible schema.
- Backups: daily encrypted, off-host; restore is rehearsed and recorded before the gate; RPO
  ≤ 24 h, RTO ≤ 4 h.
- Hub outage cannot stop the platform while it is disabled; while enabled it is bounded by
  timeouts, a circuit and caches, and never blocks local learning.

## 11. Constraints and trade-offs
- Server-rendered UI over an SPA: simpler operations and accessibility, no build step; accepted
  limitation for highly interactive flows.
- ffmpeg in Celery instead of a transcoding service: cost control and worker capacity planning.
- PostgreSQL-only: composite FKs, partial indexes, triggers; no SQLite fallback.
- One database for all companies with strict application scoping: simpler operations; isolation
  relies on the ORM discipline plus constraints and tests (RLS deferred).
- No local membership projection was the old design; it is replaced by first-class local
  membership because the platform must run without Hub.

## 12. Architecture decisions
Expanded records live in `docs/adr/`; the list below is normative for the summarized ADRs.
ADR numbers 15–22 are reserved legacy numbers and are never reused; new records start at ADR-023.

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Service layer: views/serializers/tasks thin, all business logic in services | Accepted |
| ADR-002 | Opaque `user_ref`, no user FK, names/emails never stored | **Superseded by ADR-023** |
| ADR-003 | `organization_id` on every tenant table; `for_org` scoping | Accepted (extended by ADR-026) |
| ADR-004 | Immutable course versions; enrollments pinned to a version | Accepted |
| ADR-005 | Server-authoritative progress (heartbeat + range coverage) | Accepted |
| ADR-006 | Direct-to-storage upload/playback; HLS; presigned playlist rewriting | Accepted |
| ADR-007 | Domain events via on-commit signals + Celery; handlers stay light | Accepted |
| ADR-008 | PostgreSQL-only with DB-enforced invariants | Accepted |
| ADR-009 | Append-only audit in the caller's transaction (DB trigger) | Accepted |
| ADR-010 | Hub reverse-proxy embedding as the public origin | **Superseded by ADR-024** |
| ADR-011 | Academy grants combined with Hub role defaults | **Superseded by ADR-025** |
| ADR-012 | Membership read from Hub on demand; no local membership | **Superseded by ADR-026** |
| ADR-013 | Watched coverage as merged ranges on one progress row | Accepted |
| ADR-014 | Dual-mode H1 access, `grants_only`, local suspension | **Superseded by ADR-023/024/025** |
| ADR-023 | Standalone-first platform with local accounts and stored PII (minimal, retained) | Accepted |
| ADR-024 | Public website on `/`, application under `/academy/`, own origin; Hub optional | Accepted |
| ADR-025 | Dynamic scoped RBAC replacing Hub roles + coarse capabilities | Accepted |
| ADR-026 | First-class organizations, memberships and departments with composite FKs | Accepted |
| ADR-027 | Row-level security assessed and deferred | Accepted |
| ADR-028 | Transactional outbox assessed and deferred until an external exactly-once need appears | Accepted |

## 13. Current versus target
**Implemented and verified (2026-11-25):** foundation, settings, adapters with contract suites,
tenant base model and isolation suite, domain events, full training schema (migrations 0001–
0007), audit ledger, authorization engine, API skeleton, sessions middleware, Hub integration,
content services, media pipeline, assignments, progress/completion, notifications/reminders,
reports/CSV; 590 tests, CI gates G1–G9 green on `main`.

**Current limitations, deliberately being replaced (T-026…T-034):**
- no `Organization`, `Department`, `Membership` or `User` table; `organization_id` is a UUID
  without FK and comes from `ACADEMY_ORGANIZATION_ID`;
- local sign-in is a development stub that accepts any password and a self-selected role;
- roles and identity come from Hub claims; five coarse capabilities, department-only scopes;
- no public website and no platform/company administration;
- Arabic catalogue only; no metrics, tracing or implemented alerting; no staging/CD;
- Hub is enabled by default in settings and its routes are always mounted.

The replacement sequence, acceptance criteria and evidence requirements are in `docs/plan.md`.
No task is complete until its evidence exists; older tasks are revalidated under H1.5 by
T-034 rather than assumed.
