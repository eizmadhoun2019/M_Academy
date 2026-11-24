# STATUS — Current Project State

> Current state only. Historical detail belongs in `LOG.md`.

**Last updated:** 2026-11-23 (H1 documentation alignment)
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
targets — no code implements them yet. The build specifications are complete: `docs/domain-model.md` (schema, constraints, progress algorithm),
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
| T-006 | Catalog models + migrations (Course/Version/Section/Lesson/MediaAsset) | `[~]` in progress/review (AI agent, 2026-11-23; branch `task/T-006-catalog` HEAD `9531d22`; 171 tests, ruff/format/mypy/migrations and G7/G9 clean; CI run `45174870900` green; awaiting owner merge) | Tech authority | T-003 | Migrations apply/reverse; constraint tests |
| T-007 | Assignment/progress models + constraints (Assignment/Enrollment/LessonProgress/CompletionRecord) | `[ ]` | Tech authority | T-006 | Constraints + indexes tested |
| T-008 | Quiz + operational models (Quiz…AttemptAnswer, ReminderLog, NotificationLog, AuditEvent) | `[ ]` | Tech authority | T-007 | Meta-test: every model is a TenantModel |
| T-009 | Authorization layer: capabilities, DRF permissions, web mixin, scope handling | `[ ]` | Tech authority | T-004 | Allow/deny/scope matrix tests for `role_plus_grants` and `grants_only` (H1 default, D-027); local suspension denies |
| T-010 | Test foundations: factories, two-org fixtures, tenant-isolation suite | `[ ]` | Tech authority | T-008 | Isolation suite runs; leak-detection proven |
| T-011 | API skeleton: versioned routes, auth, error format, pagination, OpenAPI, `/healthz` | `[ ]` | Tech authority | T-009 | Schema builds with 0 warnings |
| T-012 | Audit trail: model + append-only trigger + `audit.record` service | `[ ]` | Tech authority | T-008 | DB blocks UPDATE/DELETE; record joins caller transaction |
| T-013 | UI foundation: tokens, RTL/LTR shell, showcase, error pages, wireframes, Arabic font | `[ ]` | Tech authority | T-002 | Renders at 360/768/1280 in ar+en; axe clean |
| T-014 | Sessions/auth lifecycle (dev login, inactive handling, capability cache, throttles) | `[ ]` | Tech authority | T-004 | Unauthenticated/inactive/role-change tests; access modes `hub`/`standalone` (local sign-in, D-026) and `AccessSuspension` enforcement (D-028) |
| T-015 | Hub HTTP integration: signed identity, webhooks, HubHttp adapters, loopback fake | `[ ]` | Tech authority | T-004, T-014 | Contract + integration suites pass vs fake |
| T-016 | Permission grants: model, grant/revoke services, enforcement, audit, last-admin protection | `[ ]` | Tech authority | T-009 | REQ-13 matrix tests in DRF + web, both modes; H1 `grants_only`, suspended grants ineffective but retained |
| T-017 | Content services/API: course CRUD, draft clone, sections/lessons, reorder, publish | `[ ]` | Tech authority | T-011, T-016 | REQ-06; immutability + publish validation |
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
T-006 (catalog models + migrations) is complete on `task/T-006-catalog` (HEAD `9531d22`,
CI `45174870900`) and waits for the owner merge; start **T-007** (assignment/progress models per
`docs/domain-model.md`) after it. The H1 documentation alignment lands on `docs/h1-alignment`
and changes no task status. T-001 stays open until the owner resolves D-025 (storage image) and the CI run on the
authorized first push is green. Say «كمل» to authorize the agent; the agent completes one
task/checkpoint, commits, pushes, reports evidence, stops.

## Update rules
- Update when project state changes. Do not turn this file into a diary (LOG.md owns history).
- Do not mark work complete without merge-commit + CI evidence.
