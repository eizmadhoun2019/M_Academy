# STATUS — Current Project State

> Current state only. Historical detail belongs in `LOG.md`.

**Last updated:** 2026-11-24 (T-013 UI foundation)
**Updated by:** Project owner (with AI agent assistance)
**Current phase:** Phase 0 — Foundation (rebuild from scratch)
**Project scale:** Medium
**Sensitivity:** Sensitive
**Overall status:** Active

## Snapshot
The project is being rebuilt from scratch with a UPDS 1.0.0-rc2 documentation baseline
(seven core documents + performance profile, seeded from the legacy requirements set on
2026-11-22). The **T-001 scaffold** now exists: a Django 5.2 `config` project with `dev`/`test`/`prod`
profiles, an isolated compose stack (`m-academy`) running six of seven services, pinned
dependencies, the CI gate definitions and the docs check. The storage service stays down
until the owner resolves D-025. The `academy` package now exists (T-003): the tenant
base model with `for_org` scoping, the adapter loader and the domain exceptions, registered in
`INSTALLED_APPS` and inspected by gate G7. The four host seams are specified (T-004) as Protocols
with their value types, the development/test stubs behind them, and one contract suite per
seam that any future Hub or bucket implementation must pass. Domain events now have their
emitter (T-005): an event is queued through `transaction.on_commit` and dispatched to its
subscribers only after the write commits. The documentation also records the owner-approved **H1
target** (charter 2.3; decisions D-026…D-030): Masheed only, one record set with Hub-integrated
or standalone local sign-in, `grants_only` management authority, an Academy-owned dashboard and
sidebar, and screens specified in `docs/ui/screen-specification.md`. Those are documented
targets — no code implements them yet. The catalog schema exists (T-006): Course →
CourseVersion → Section → Lesson plus MediaAsset, with every documented check, partial unique
index, deferrable position constraint and the two freeze triggers in the database itself. The
assignment/progress schema (T-007) follows it: Assignment → Enrollment → LessonProgress →
CompletionRecord, with the active-enrollment and active-target partial unique indexes, the
watched-number checks and a trigger that makes a completion row immutable. T-008 completes the
Phase 1–2 schema with the quiz tables (no endpoint yet) and the operational logs: `ReminderLog`
and `NotificationLog` carry the idempotency keys, and `AuditEvent` is the append-only ledger
whose trigger and `audit.record` service arrived with T-012. The authorization layer (T-009) resolves
effective capabilities from a principal and the stored grants: H1 `grants_only` keeps learning
for active members and requires a grant for every management capability, the compatibility
`role_plus_grants` union stays testable, and an Academy-local suspension denies everything with
`access_suspended`. The test foundation (T-010) is generic: one factory per table builds a
valid row, and the isolation suite writes each table in two organizations, asserts that
`for_org` returns only its own row, and proves the detector fails on an unscoped query. The API
skeleton (T-011) now serves `/api/v1/academy/` with one error envelope, page/page_size
pagination, a 401 without identity, the `me/capabilities/` route backed by the authorization
layer, and a generated OpenAPI document that validates with zero warnings. The audit service
(T-012) is the accountability floor: `audit.record` appends one row inside the caller's
transaction, validates the action name and ids-only metadata, and returns an existing row when
the same `event_id` arrives twice, while a PostgreSQL trigger refuses every UPDATE and DELETE. `docs/domain-model.md` (schema, constraints, progress algorithm),
`docs/api.md` (endpoint inventory), `docs/decisions.md` (decision register) and
`docs/traceability.md` (IDs, gates, sources of truth). The rebuild has its **own repository** (`M_Academy`) and its **own runtime stack**
(compose project `m-academy`: own containers, PostgreSQL, Redis, MinIO buckets, volumes,
Celery broker, secrets and host ports). It runs beside the legacy deployment without
sharing anything; the legacy stack and repository are reference only
(`docs/operations/environments.md`). The legacy implementation (17/42 tasks
complete: foundation through permission grants) remains available in the legacy repository
as reference and history — nothing in it is claimed for this rebuild until re-implemented
and verified here.

## Active work
| ID | Task | Status | Owner | Depends on | Acceptance / evidence |
|---|---|---|---|---|---|
| T-001 | Repository and stack bootstrap: `git init` + `origin` = `M_Academy` + first commit (push after D-023); pyproject (pinned deps), ruff/mypy/pytest, pre-commit, Makefile, Dockerfile, isolated compose (project `m-academy`: web/db/redis/minio/worker/beat/mailhog), env example with generated secrets, CI gates, docs check | `[~]` in progress/evidence (AI agent, 2026-11-23; gates G1–G9 green in CI run `45138282623` on `main`; the bucket step still waits on D-025) | Tech authority | — | Isolation checklist in `docs/operations/environments.md` §7 all pass: only `m-academy-*` containers, `/healthz` 200 on `http://localhost:8101`, legacy stack still up, gates G1–G9 green in CI |
| T-002 | Settings profiles + Celery queues + JSON logging + i18n (ar/en) | `[x]` done on main (commit `8168477`, merged 2026-11-23 on owner instruction; CI run `45148819610` on `main` green on that commit; `tests/test_settings.py` — 26 tests; ruff/format/mypy clean locally) | Tech authority | T-001 | Worker ping task via Redis; settings tests |
| T-003 | `academy` app skeleton: TenantModel/manager, adapter loader, exceptions; import-boundary test | `[x]` done on main (commit `3b7d450`, merged 2026-11-23 on owner instruction; CI run `45154163445` on `main` green on that commit; 47 tests, ruff/format/mypy/migrations clean locally) | Tech authority | T-002 | Loader + `for_org` tests; `academy` ⊄ host test |
| T-004 | Adapter interfaces + `host_stub` + 4 contract suites | `[x]` done on main (commit `928e7da`, merged 2026-11-23 on owner instruction; CI run `45159244272` green on the branch commit and `45159847845` green on `main` at that commit; 123 tests at merge) | Tech authority | T-003 | All contract suites pass |
| T-005 | Domain events (signals, on-commit emitter, handlers) | `[x]` done on main (commit `0204cac`, merged 2026-11-23 on owner instruction; CI run `45162780071` on `main` green on that commit; 145 tests at merge) | Tech authority | T-003 | Events fire only after commit |
| T-006 | Catalog models + migrations (Course/Version/Section/Lesson/MediaAsset) | `[x]` done on main (merge commit `7fe4b32`, merged 2026-11-23 on owner instruction with a merge commit because `main` had advanced with the documentation change; CI run `45346681425` on `main` green; 171 tests at merge) | Tech authority | T-003 | Migrations apply/reverse; constraint tests |
| T-007 | Assignment/progress models + constraints (Assignment/Enrollment/LessonProgress/CompletionRecord) | `[x]` done on main (commit `8d30403`, merged 2026-11-23 on owner instruction with a fast-forward; CI run `45350592242` on `main` green; 196 tests at merge) | Tech authority | T-006 | Constraints + indexes tested |
| T-008 | Quiz + operational models (Quiz…AttemptAnswer, ReminderLog, NotificationLog, AuditEvent) | `[x]` done on main (commit `52798e5`, merged 2026-11-24 on owner instruction with a fast-forward; CI run `45353814514` on `main` green; 219 tests at merge) | Tech authority | T-007 | Meta-test: every model is a TenantModel |
| T-009 | Authorization layer: capabilities, DRF permissions, web mixin, scope handling | `[x]` done on main (commit `a48768c`, merged 2026-11-24 on owner instruction with a fast-forward; CI run `45357518339` on `main` green; 242 tests at merge) | Tech authority | T-004 | Allow/deny/scope matrix tests for `role_plus_grants` and `grants_only` (H1 default, D-027); local suspension denies |
| T-010 | Test foundations: factories, two-org fixtures, tenant-isolation suite | `[x]` done on main (commit `968ee4a`, merged 2026-11-24 on owner instruction with a fast-forward; CI run `45361612343` on `main` green; 281 tests at merge) | Tech authority | T-008 | Isolation suite runs; leak-detection proven |
| T-011 | API skeleton: versioned routes, auth, error format, pagination, OpenAPI, `/healthz` | `[x]` done on main (commit `bdab55e`, merged 2026-11-24 on owner instruction with a fast-forward; CI run `45367468113` on `main` green; 289 tests at merge) | Tech authority | T-009 | Schema builds with 0 warnings |
| T-012 | Audit trail: model + append-only trigger + `audit.record` service | `[x]` done on main (commit `6e08296`, merged 2026-11-24 on owner instruction; the merge dropped the branch's files and `f2dc808` restored them; 311 tests at merge) | Tech authority | T-008 | DB blocks UPDATE/DELETE; record joins caller transaction |
| T-013 | UI foundation: tokens, RTL/LTR shell, showcase, error pages, wireframes, Arabic font | `[~]` in progress/review (AI agent, 2026-11-24; `static/css/academy.css` tokens, `templates/academy/`, preview at `/academy/preview/{ar,en}/`, `/academy` error pages, local Noto Sans Arabic with OFL licence, gettext catalogue compiled by `scripts/compile_messages.py`; 331 tests, ruff/format/mypy and G7/G9 clean; no migration; CI run `45382616992` green on `main`) | Tech authority | T-002 | Renders at 360/768/1280 in ar+en; axe clean |
| T-014 | Sessions/auth lifecycle (dev login, inactive handling, capability cache, throttles) | `[x]` done on main (commit `cb1edda`, merged 2026-11-25 on owner instruction with a fast-forward; CI run `45568418999` on `main` green at that commit; `AccessSuspension` migration `0005`, `academy.access` middleware, X1 sign-in and X2 access-denied pages, fingerprint-keyed capability cache, documented DRF scopes; 360 tests, ruff/format/mypy and G7/G9 clean) | Tech authority | T-004 |
| T-015 | Hub HTTP integration: signed identity, webhooks, HubHttp adapters, loopback fake | `[x]` done on main (commit `f4eea00`, merged 2026-11-25 on owner instruction with a fast-forward; CI run `45573329413` on `main` green at that commit; 399 tests, ruff/format/mypy and G7/G9 clean) | Tech authority | T-004, T-014 |
| T-016 | Permission grants: model, grant/revoke services, enforcement, audit, last-admin protection | `[x]` done on main (commit `17fe415`, merged 2026-11-25 on owner instruction with a fast-forward; CI run `45577563757` on `main` green at that commit; `PermissionGrant` migration `0007`, grant/revoke services with audit, `manage/grants/` API with idempotency, `provision_admin`, last-admin guard; 423 tests, ruff/format/mypy and G7/G9 clean) | Tech authority | T-009 |
| T-017 | Content services/API: course CRUD, draft clone, sections/lessons, reorder, publish | `[~]` implemented on `task/T-017-content` (scope-aware course/version/section/lesson services, publish validator with per-item reasons, `manage/courses/`+`manage/versions/`+`manage/sections/`+`manage/lessons/` routes; 21 new tests (444 total), ruff/format/mypy and G7/G9 clean locally; CI run `45585336949` green on the branch at `8b5ecc1`) | Tech authority | T-011, T-016 | REQ-06; immutability + publish validation |
| T-018 | Media upload/processing/playback (presigned PUT, stat verify, ffmpeg→HLS, playlists) | `[ ]` | Tech authority | T-004, T-017 | REQ-07 end-to-end; slow HLS integration test; upload/HLS policy in `docs/configuration.md` §3–§4 |
| T-019 | Assignments + auto-enroll (`member_changed`) + gating/outline selector | `[ ]` | Tech authority | T-017 | REQ-08, sequential-lock matrix |
| T-020 | Heartbeat/anti-skip + completion flow (server frontier, idempotent completion) | `[ ]` | Tech authority | T-019 | REQ-09 matrix; double-submit = one record |
| T-021 | Notifications + reminders (localized templates, digest, idempotency, beat) | `[ ]` | Tech authority | T-020 | REQ-10, REQ-11 with frozen time; copy per `docs/notifications.md`, schedule per `docs/background-jobs.md` §4 |
| T-022 | Reports + CSV export (scoped selectors, formula-safe CSV) | `[ ]` | Tech authority | T-020 | REQ-12; query-count + scope tests; columns and CSV per `docs/reports.md` |
| T-023 | Learner + management web UI (bilingual, responsive, accessible, player) | `[ ]` | Tech authority | T-020, T-022 | REQ-14 + screens L1–L4, S1, X1–X2 per `docs/ui/screen-specification.md`; manual checks recorded in LOG |
| T-024 | Journey test + E2E + accessibility + load test + ops (deploy/backup/restore/alerts) + security review + privacy tooling + pilot | `[ ]` | Tech authority | T-023 | REQ-15…REQ-20 evidence in LOG; alert thresholds in `docs/operations/environments.md` §8 |
| GATE-1 | Phase 1 gate: all REQ-01…REQ-20 verified; release `v1.0.0` | `[ ]` | Project owner | T-001…T-024 | [RELEASE] entry in LOG with per-REQ evidence |

Schema tasks (T-006…T-008, T-012) are specified by `docs/domain-model.md`; endpoint tasks
(T-011, T-016…T-022) by `docs/api.md`; the task/branch naming rule uses these IDs only.

## Recently completed
- 2026-11-25 — T-017 content services: courses, versions, sections and lessons through
  scope-checked services, draft clone, publish validation with every reason, and the
  `manage/…` routes behind `academy.manage_content`. See LOG.md.
- 2026-11-25 — T-016 permission grants: `PermissionGrant` with its scope checks, audited
  grant/revoke services, last-admin protection, the `manage/grants/` API and a request path
  that now unions live grants into effective capability. See LOG.md.
- 2026-11-25 — T-015 Hub HTTP integration: verified signed identity in `hub` mode, signed
  membership webhooks with durable receipts, HTTP directory and delivery transports with
  retries, circuit and cache invalidation, and a loopback Hub fake the contract suites run
  against. See LOG.md.
- 2026-11-25 — T-014 sessions/auth lifecycle: one middleware resolves the caller in both
  access modes and publishes a single `Access`, `AccessSuspension` denies on the next request
  even with a warm cache, and the X1 sign-in plus the X2 access-denied screen are reachable
  in `standalone` mode only. See LOG.md.
- 2026-11-25 — T-013 follow-up: the development stack serves its own static files,
  the stylesheet is never cached stale, the drawer opens on phones without hiding the
  desktop sidebar, and no width overflows at 360 or 768. See LOG.md.
- 2026-11-24 — T-013 UI foundation: design tokens, one RTL/LTR shell, the component
  showcase with five sample states, 403/404/500 pages, the locally hosted Noto Sans Arabic
  font and a dependency-free catalogue compiler. See LOG.md.
- 2026-11-24 — T-012 audit trail: `audit.record` joins the caller's transaction,
  rejects free-text metadata and duplicate-inconsistent `event_id`s, and migration `0004`
  makes `AuditEvent` append-only in PostgreSQL. See LOG.md.
- 2026-11-24 — T-011 API skeleton: `/api/v1/academy/` with the documented error
  envelope, pagination, an access-context authenticator, `me/capabilities/` and a clean
  OpenAPI document. See LOG.md.
- 2026-11-24 — T-010 test foundations: one factory per table, two-organization
  fixtures, and a generic tenant-isolation suite that also proves the leak detector fires.
  G7's tenant half is now active. See LOG.md.
- 2026-11-24 — T-009 authorization layer: capabilities, scopes, grant-aware effective
  access, the two documented modes, `AccessSuspended`/`InactiveAccount`, a DRF permission and
  a web mixin; the matrix is tested without a view. See LOG.md.
- 2026-11-24 — T-008 quiz and operational schema: five quiz tables, `ReminderLog`,
  `NotificationLog` and `AuditEvent` with their idempotency unique keys and checks; migration
  `0003` reverses cleanly. See LOG.md.
- 2026-11-24 — T-007 assignment/progress schema: `Assignment`, `Enrollment`,
  `LessonProgress` and `CompletionRecord` with their partial unique indexes, checks, lookup
  indexes and the completion-immutability trigger; migration `0002` reverses cleanly. See LOG.md.
- 2026-11-23 — T-006 catalog schema: `Course`, `CourseVersion`, `Section`, `Lesson` and
  `MediaAsset` with the documented checks, partial unique indexes, deferrable position
  constraints, and the `courseversion_immutable` / `version_content_frozen` triggers in
  `academy/migrations/0001_initial.py`; the migration applies, reverses and re-applies. See
  LOG.md.
- 2026-11-23 — T-005 merged to `main`: the on-commit event emitter and its handler registry.
  See LOG.md.
- 2026-11-23 — T-005 domain events: `academy.events` emits through `transaction.on_commit`, so a
  rolled-back write dispatches nothing; handlers subscribe by event name, a failing handler is
  logged without stopping the rest, and the envelope is frozen with a JSON payload. See LOG.md.
- 2026-11-23 — T-004 merged to `main`: the four host-seam Protocols, the `host_stub`
  implementations and their contract suites. See LOG.md.
- 2026-11-23 — T-004 adapters: the four seams are Protocols (`IdentityAdapter`,
  `OrganizationAdapter`, `NotifyAdapter`, `StorageAdapter`) with stdlib-only value types, the
  `host_stub` implementations behind them, and one contract suite per seam under
  `tests/contracts/` (76 assertions). See LOG.md.
- 2026-11-23 — T-003 merged to `main`: tenant base model, adapter loader and domain exceptions;
  CI run `45154163445` green on the merge commit `3b7d450`. See LOG.md.
- 2026-11-22 — T-001 scaffold: own repository initialised, Django 5.2 project with
  dev/test/prod profiles, isolated stack answering `http://localhost:8101/healthz` 200 with
  live DB and cache checks, gates G1/G2/G4/G5/G9 green locally, Celery worker answered
  `pong`. Storage service blocked by D-025. Evidence in LOG.md.
- 2026-11-22 — Rebuild repositioned onto a new repository (`M_Academy`) with a fully isolated
  stack (containers, PostgreSQL, Redis, MinIO, Celery, secrets, ports). Isolation contract
  and safety rules written in `docs/operations/environments.md`; RULES and CHARTER 2.2
  updated; port 8001 (legacy web) dropped in favour of 8101 (see LOG.md).
- 2026-11-22 — Documentation strengthened for a from-scratch build: decision register,
  traceability map, domain model (with the progressive-watch/anti-skip algorithm) and API
  inventory written; legacy `P0-/P1-` IDs retired; CHARTER 2.1 and ARCHITECTURE references
  corrected (see LOG.md).
- 2026-11-22 — UPDS documentation baseline created and seeded from the legacy requirements set (see LOG.md).

## Blockers and risks
| Item | Impact | Owner | Next action | Review date |
|---|---|---|---|---|
| Hub contract unconfirmed (D-004 identity format, D-010 Hub implementation, D-005 domain/TLS) | Blocks live integration; not blocking Academy-side build (fakes) | Project owner + Hub owner | Confirm contract after T-015 | T-015 |
| Video storage provider (self-hosted vs managed) | Blocks production media deploy only | Project owner | Decide before T-018 production config | T-018 |
| Employee-data retention/legal basis needs legal confirmation | Blocks go-live | Management + legal | Advise before GATE-1 | GATE-1 |
| MinIO development image is unavailable: `minio/minio` is gone from Docker Hub, `ghcr.io/minio/minio` is denied and `quay.io/minio/minio` returns 401 (checked 2026-11-22) | The storage service of the dev stack cannot start, so uploads and the bucket checks cannot run | Project owner | Decide D-025: load a MinIO image into the local engine (`docker save`/`load`) or approve an S3-compatible development substitute behind the existing `StorageAdapter` | T-018 |
| Two stacks on one host (legacy `masheed-academy` + new `m-academy`) | Port/volume/cookie collision, or accidental destruction of legacy data | Tech authority | Isolation table + safety rules in `docs/operations/environments.md`; checklist §7 at T-001 | T-001 |
| Repository is public and the baseline is published (D-023 Confirmed: public) | Future internal material leaking into a tracked file | Project owner | Keep secrets in the untracked `.env`; assume every commit is public | ongoing |

## Decisions
Single register: [`docs/decisions.md`](docs/decisions.md). STATUS does not duplicate values.

- **Open:** D-001 (video storage provider), D-005 (upstream domain/TLS), D-009 (KPI values),
  D-010 (Hub implementation owner), D-025 (object-storage image for the development stack).
  Only D-025 blocks a Phase 0 acceptance item — the bucket step of T-001; none blocks Phase 0
  implementation work.
- **Confirmed:** D-023 (repository stays public; the documentation baseline is published);
  D-011 (Academy-owned navigation); D-026 (H1 scope and access modes), D-027 (`grants_only`),
  D-028 (local suspension), D-029 (linked-membership reconciliation), D-030 (H1 UI boundary).
- **Defaulted** (build proceeds on the documented value; owner may override): D-002, D-003,
  D-004, D-006, D-007, D-008, D-012, D-013, D-014, D-015, D-016, D-017, D-024.
- Retired legacy numbers (D-018…D-022, plus the four CHARTER 2.0 collisions) are mapped in
  that file and must not reappear.

## Next action
T-017 (content services and API) is implemented on its branch and waits for CI evidence and
owner review; **T-018** (media upload and processing) follows it.
The H1 documentation alignment is merged to `main`
(commit `fa75e87`, CI run `45345097262` green) and changed no task status. T-001 stays open until the owner resolves D-025 (storage image) and the CI run on the
authorized first push is green. Say «كمل» to authorize the agent; the agent completes one
task/checkpoint, commits, pushes, reports evidence, stops.

## Update rules
- Update when project state changes. Do not turn this file into a diary (LOG.md owns history).
- Do not mark work complete without merge-commit + CI evidence.
