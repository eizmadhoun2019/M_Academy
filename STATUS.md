# STATUS — Current Project State

> Current state only. Historical detail belongs in `LOG.md`.
> Task definitions and acceptance criteria live in `docs/plan.md`.

**Last updated:** 2026-11-27 (T-027 CP2 invitations and MFA implemented on `task/T-027-identity-cp2`)
**Updated by:** AI agent (T-027 CP2), under the owner's delegation
**Current phase:** H1.5 — Foundation (GATE-1)
**Project scale:** Medium (design envelope: 10 companies / 5,000 users)
**Sensitivity:** Sensitive
**Overall status:** Active — T-025 and T-035 are merged; the official UI/UX reference is the single design authority; T-026 CP1 (schema expand, nullable FKs, constraints, seed) is merged as `a5373c0`; CP2 (mapping/backfill and reconciliation report) is merged as `e3f9715` (branch `0ec430e`, CI 45769212077; merge CI run 45773205917), with the real-data mapping and reconciliation kept open as an acceptance condition until the owner's identity file arrives or the absence of rows requiring migration is proven; CP3 (company context from the single membership, `/me/organization`, expanded isolation) is merged as `5ae89f6` (CI 45776614160 success). The legacy-data audit of 2026-11-26 (`manage.py audit_legacy_data`) found **zero legacy rows** in the only existing database (development); the owner accepted that evidence on 2026-11-26, so the reconciliation condition is closed and **T-026 is `[x]`**. **T-027 CP1** (local email/password sign-in, email verification and password reset/change, hashed single-use tokens, session fingerprint, login failure lock, Argon2) is merged as `6d72a63` (branch `c157739`; CI 45786234699) with 18 tests and all gates green; **CP2** (session registry/listing/revocation and idle window, company invitations, TOTP MFA with recovery codes and role-enforced enrolment) is implemented on `task/T-027-identity-cp2` at `afe6084` (CI 45954587695 success) and **awaits the owner's approval to merge**; CP3 (dev-login removal, production guard, mail delivery) remains

## Snapshot
`main` carries the working H1 foundations: T-001…T-022 are implemented and tested (590 tests at
the T-022 merge; gates G1–G9 green on their merge commits), with two exceptions recorded below:
T-001's bucket evidence and T-013's English/accessibility completion. The code is still
**single-company** (fixed `ACADEMY_ORGANIZATION_ID`, opaque `user_ref`/`department_ref`) and its
production identity path is Hub-oriented; that is the gap T-026…T-033 close.

The canonical target is now charter 2.5: standalone-first, multi-company, **one company membership
per account**, local identity and dynamic scoped RBAC, with the Hub integration dormant and
optional. Mobile First and the binding visual-reference gate are recorded in D-044. T-025 rewrote the charter,
architecture, rules, decisions, access control, security, domain model, API, configuration,
plan, traceability, UI, notifications, reports, jobs, Hub contract, operations, performance,
migration, README, skills and ADRs to make «كمل» sufficient. The architecture correction removed
the company chooser/switcher and multi-membership paths, added `UNIQUE (user_id)`, platform-only
administration and the capability-preservation matrix, and fixed the evidence policy. **No code,
template, migration, API contract, Hub activation, infrastructure or dependency changed in T-025.**
T-025 is merged as `b592498` (CI run 45687216183, success). T-035 adopted the official
`Masheed-Academy-Official-UI-UX-v1.0` (D-045) and is merged as `47638b0` (CI run 45694757748,
success). T-026 CP1 adds the four tenancy tables, nullable backfill FKs on the existing tenant
tables, the database-level organization/composite FKs and the Masheed seed — with no read path,
API or UI change. CP2 adds `manage.py backfill_tenancy` (identity CSV → accounts, one membership
each, departments per legacy ref, batched FK backfill) with an abort-on-unresolved preflight and
a JSON reconciliation report, plus the `legacy_ref`/`must_set_email` columns; it creates no real
account until the owner supplies the identity file, so the real-data mapping and reconciliation
stay an open acceptance condition. CP3 derives the company from the account's single membership
(the session cannot name or switch it), adds `/me/organization` and the `membership_inactive`
refusal, makes the local sign-in select a seeded account, and expands the isolation suite; it is
merged, and the 2026-11-26 audit found no legacy row to migrate in the only database.

## Active work
| ID | Task | Status | Owner | Depends on | Acceptance / evidence |
|---|---|---|---|---|---|
| T-025 | Documentation and governance consolidation | `[x]` — merged in `b592498`; CI success 45687216183 | AI agent; owner approved 2026-11-25 | owner approval | `docs/plan.md` §4 T-025; `check_docs` green (38 files); 23-row capability matrix |
| T-035 | Official UI/UX reference adoption and repository hygiene | `[x]` — merged in `47638b0`; CI success 45694757748; owner approved 2026-11-25 | AI agent; docs only | T-025 | `docs/plan.md` §4 T-035; `docs/ui/design-reference.md`; restore rehearsal 14/14; `check_docs` green |
| T-026 | Tenancy and account foundation | `[x]` — CP1 `a5373c0` (CI 45700454330), CP2 `e3f9715` (CI 45773205917), CP3 `5ae89f6` (CI 45776614160); zero-row audit accepted by the owner 2026-11-26; staging re-audit before cutover | AI agent; owner approved 2026-11-26 | T-025 | `docs/plan.md` §4 T-026; `test_tenancy_constraints`, `test_tenancy_backfill`, `test_company_context`, `test_tenancy_audit`; `docs/migration-h1.5.md` §8 |
| T-027 | Local identity and account lifecycle | `[~]` — CP1 merged `6d72a63`; CP2 implemented on `task/T-027-identity-cp2` at `afe6084` (CI 45954587695 success), awaiting the owner's merge approval: `UserSession` registry, `GET /auth/sessions/`, `DELETE /auth/sessions/{id}/`, 30-minute idle window, revocation on reset/change; `Invitation` + `POST /auth/invitations/accept/` with `already_member`; TOTP MFA, 10 hashed recovery codes, single-use login challenges and `mfa_enrollment_required`; migration `0012`; CP3 pending | AI agent; owner approved CP1 2026-11-26 | T-026 `[x]` | `docs/plan.md` §4 T-027; `tests/test_auth.py` (22), `tests/test_invitations.py` (16), `tests/test_mfa.py` (11); gates G1, G3, G5, G7, G9 |
| T-033 | Hub quarantine | `[ ]` — unblocked by T-026 `[x]`; starts only on the owner's instruction | AI agent | T-026 `[x]` | `docs/plan.md` §4 T-033 |
| T-001 | Repository and stack bootstrap | `[~]` — bucket step evidence outstanding | Tech authority | — | `docs/operations/environments.md` §12 step 7 |
| T-013 | UI foundation | `[~]` — extended by T-029 | Tech authority | T-002 | en catalogue + axe evidence land in T-029 |
| T-023 | Learner + management UI (old scope) | `[–]` superseded by **T-031** | — | — | historical only |
| T-024 | Hardening + E2E + ops (old scope) | `[–]` superseded by **T-034** | — | — | historical only |
| GATE-1 | H1.5 gate | `[ ]` | Project owner | T-025…T-034 | `docs/plan.md` §5; capability matrix verified |

Completed: T-002…T-012, T-014…T-022 on `main` with their CI/LOG evidence. T-015 is completed code
that T-033 will quarantine; T-016/T-009 are completed v1 engines that T-028 replaces.

## Recently completed
- 2026-11-27 — **T-027 CP2 invitations and MFA implemented** on `task/T-027-identity-cp2` as
  `afe6084` (CI 45954587695 success); not merged. `Invitation` (migration `0012`) stores a
  SHA-256 token, a seven-day expiry and the role codes the accepted membership receives; one live
  invitation per address per company, re-inviting retires the previous token, and acceptance
  creates or reactivates the account, verifies the address and restores a removed membership
  rather than inserting a second one (409 `already_member` otherwise). `MFADevice` keeps the TOTP
  secret encrypted with `ACADEMY_MFA_ENCRYPTION_KEY`; confirmation issues ten hashed single-use
  recovery codes; a confirmed device makes `login/` answer 401 `mfa_required` with a five-minute
  single-use challenge, and a role in `ACADEMY_MFA_REQUIRED_ROLES` with no device is confined to
  the auth routes by 403 `mfa_enrollment_required` until it enrols. Membership `roles` is the
  provisional pre-RBAC carrier that T-028 replaces with `RoleAssignment`. Local suites: 16
  invitation tests and 11 MFA tests; gates G5/G7/G9 green, `ruff`/`mypy` (168 files) clean.
- 2026-11-26 — **T-027 CP2 sessions slice.** `UserSession` (migration `0011`) stores only a
  SHA-256 of the session key, an absolute expiry, a coarse last-seen and an optional revocation
  stamp; a session without a live row resolves to no principal, so revocation and the 30-minute
  idle window are server-side. Owners list their live sessions and revoke any of them; a reset or
  password change revokes the account's other rows. Invitations and MFA remain in CP2.
- 2026-11-26 — **T-027 CP1 merged** as `6d72a63` (`--no-ff`, branch `c157739`, CI 45786234699 success).
- 2026-11-26 — **T-027 CP1 implemented.** `academy/access/backends.py` is the only authenticator:
  email + password, case-insensitive, with a dummy-hash path so an unknown address costs the same
  as a wrong password. `academy/access/accounts.py` owns the rules — five failures per email+IP
  lock the window, responses never reveal an account, and sign-in rotates the session key. The
  session stores the account UUID and a password fingerprint, never a capability or secret, so a
  reset or change invalidates other sessions without extra bookkeeping. `AccountToken` stores
  only a SHA-256 digest with an expiry and a single-use claim; verification activates the account
  and `email_unverified` refuses tenant data until then. Seven `/auth/` endpoints follow
  `docs/api.md` §3. Argon2 is first in `PASSWORD_HASHERS` (D-033) with PBKDF2 kept for old hashes.
  CP2 (invitations, session listing/revocation, MFA) and CP3 (dev-login removal, production guard,
  mail transport) remain; the development stub is untouched and still gated by
  `DEVELOPMENT_LOGIN` until CP3.
- 2026-11-26 — **T-026 closed.** The owner accepted the 2026-11-26 audit as proof that the only
  existing database holds no legacy row, so CP2's reconciliation condition is satisfied and the
  task is `[x]` with CP1 `a5373c0`, CP2 `e3f9715` and CP3 `5ae89f6` on `main`. The closure changed
  no code, migration, guard or test. D-046 and the two data-integrity guards are unchanged. A
  fresh audit runs on staging when T-034 provisions it, before any cutover; a non-zero result
  blocks cutover until the owner's identity CSV is imported and the dry run reviewed.
- 2026-11-26 — **T-026 CP3 merged; legacy-data audit recorded.** The company is now derived from the caller's
  single membership on every request: `academy/access/tenancy.py` resolves the account by its
  legacy reference and requires one active membership, and a `membership_id` stored in the session
  is only cross-checked against that row — a tampered or stale value resolves nothing instead of
  switching tenants. `Principal` carries `user_id`/`membership_id`; `GET /me/organization/`
  returns the company and membership from that row, ignores a company in the query string or a
  header, and answers 403 `membership_inactive` for an account with no active membership (HTML
  shows the access-denied page). The development sign-in now selects a seeded account with an
  active membership and stores only its reference and membership id; the department comes from
  the membership. `test_company_context.py` (13 tests) proves derivation, tampering, two-company
  separation and a cross-company course as 404. `pytest -q` → 632 passed, 1 failed (D-046 only,
  unchanged and still enabled); `ruff`, `mypy` (155 files), `makemigrations --check`, G5, G7 and
  G9 (40 files) clean. Branch `task/T-026-tenancy-cp3` passed CI run 45775460129; the `--no-ff`
  merge `5ae89f6` passed CI run 45776614160 on `main`; the task then awaited the owner's
  acceptance of the audit evidence below and was closed later the same day (entry above). The same turn added `manage.py audit_legacy_data`, a read-only
  count-only report for this question and for the cutover rehearsal (3 tests, no reference value
  printed). Its run on the only database (development, `academy`, PostgreSQL 16.14) returned:
  organizations 1 (`masheed`, active); accounts 0, legacy refs 0, `must_set_email` 0; departments
  0; memberships 0; **17 tenant tables, 0 rows**; 0 rows with a `NULL` backfill link; 0 distinct
  legacy references across 21 `*_ref` columns; duplicate memberships 0 and accounts in more than
  one company 0 → `needs_migration: false`. No staging or production database exists yet
  (T-034/after the release decision), and no dump or backup is present. Full report:
  `docs/migration-h1.5.md` §8 and `docs/plan.md` §4 T-026 criterion 5.
- 2026-11-26 — **T-026 CP2 merged.** `manage.py backfill_tenancy` maps the owner's
  identity CSV to disabled accounts with exactly one active membership, creates one department
  per legacy ref, and fills every nullable tenancy link in 5,000-row batches. A strict preflight
  aborts on any missing learner/recipient ref, shared mailbox, blank ref or unexplained existing
  account before writing; unknown actor refs stay `NULL` and are reported, `system` actors stay
  null, and role targets plus legacy capability names are reported as deferred to T-028. The JSON
  report reconciles counts and prints the duplicate-membership and cross-company queries at zero.
  Migration 0009 adds the `legacy_ref`/`must_set_email` columns and permits the one documented
  `NULL`→value fill of the append-only audit and immutable completion links, refusing every
  other edit. `pytest -q` → 619 passed, 1 failed (D-046 only, unchanged and still enabled);
  migration 0009 applied → 0008 → 0009; `ruff`, `mypy` (153 files), G7, G9 (40 files) and
  `makemigrations --check` clean. Branch head `0ec430e` passed CI run 45769212077; the `--no-ff`
  merge `e3f9715` passed CI run 45773205917 on `main`. **The real-data mapping and reconciliation
  remain open** until the owner's identity file arrives or the absence of migratable rows is
  proven; D-046, the audit append-only guard and the immutable completion guard are unchanged.
- 2026-11-25 — **T-026 CP1 merged.** Four tenancy tables
  (`Organization`, `User`, `Department`, `Membership`) with D-043 constraints (`UNIQUE (user_id)`,
  active/removed stamps, one-company membership), nullable backfill FKs on the existing tenant
  tables, database `organization_id` FKs on every tenant table plus the two composite
  `(organization_id, id)` FKs, and an idempotent Masheed seed (`ACADEMY_ORGANIZATION_ID`,
  slug `masheed`, `ACADEMY_COMPANY_NAME`). Migration 0008 reverses cleanly (applied → 0007 →
  applied again). `pytest -q` → 606 passed, 1 failed (`test_the_digest_lists_every_overdue_learner_once`,
  pre-existing: reproduced unchanged on clean `main` with the local Celery worker running);
  `ruff check`, `ruff format --check`, `mypy .` and `makemigrations --check` clean. CP1 changes no
  read path, API, template or UI; screen groups remain pending approval. Owner approved CP1; merge
  commit `a5373c0` passed CI run 45700454330. The pre-existing reminder-digest failure is recorded
  as release-blocking debt **D-046** (fix before GATE-1; the test stays enabled and unweakened).
- 2026-11-25 — **T-035 merged (docs only).** The owner's official
  `Masheed-Academy-Official-UI-UX-v1.0` was verified (14/14 board fingerprints and dimensions), its
  text specifications and tokens were merged into `docs/ui/`, and it is now the single design
  authority (D-045). The superseded `Academy-UX-Handoff-v1.0` and `Masheed-Academy-UX-Batch-1-Review`
  packages, the interim PDF/page renders and the local document backup were removed from the active
  tree and archived in `../_design-archive/`; boards are Git-ignored and no design binary is
  tracked. Mobile First, the six verification widths (320/390/768/1024/1440/1920) and the master
  shell are permanent in `RULES.md` and `docs/ui/design-system.md`. No screen group gate was closed,
  and no code, template, stylesheet, migration, API or dependency changed. The archived ZIP was
  re-extracted as a restore rehearsal and all 14 boards re-hashed to `REFERENCE_INDEX.csv`
  (14/14); the superseded `INSTALLATION_AR.md` was archived with its content hash unchanged; the
  capability matrix was re-counted at 23 rows. Final branch head `6cb8776` passed CI run
  45694300738; merge commit `47638b0` passed CI run 45694757748; `check_docs` G9 passed (40 files).
  **T-035 is closed.**
- 2026-11-25 — T-025 H1.5 amendment: one company membership per account with `UNIQUE (user_id)`,
  no company chooser/switcher/selection APIs or screens, platform administration without a
  membership, D-043/D-044 and the capability-preservation matrix; Mobile First at 390/768/1440
  with 320+ testing and the binding visual-reference gate. Prior package commits `96f78d2`,
  `eb19fd1`, `15e0e53`, content amendment `e2e9c1b`; the capability matrix was completed to
  **23 rows** with company administration restored. Owner approved the architecture and merge on
  2026-11-25. Final branch head `e19f76c` passed CI run 45686699559; merge commit `b592498`
  passed CI run 45687216183; `check_docs` G9 passed (38 files). T-025 is closed.
- 2026-11-25 — T-022 reports: one selector module defines every number, department scope includes
  general courses and refuses a cross-department read, streamed BOM CSV with formula-safe cells
  and an audited export. See `LOG.md`.
- 2026-11-25 — T-021 notifications: seven ar/en messages through a durable queue, −3/0/+1
  reminders, due+3 manager digest, suppression codes and a repair sweep. See `LOG.md`.
- 2026-11-25 — T-020 heartbeat/completion: server-credited elapsed window, forward-skip refusal,
  idempotent completion and named blockers. See `LOG.md`.
- 2026-11-25 — T-019 assignments: one expansion selector, membership-driven enrol/cancel,
  server-enforced lesson lock. See `LOG.md`.
- 2026-11-25 — T-018 media: presigned tenant-key uploads, `stat` verification, ffmpeg→HLS and
  poster/playlists. See `LOG.md`.
- 2026-11-25 — T-017 content services; T-016 permission grants; T-015 Hub HTTP integration;
  T-014 sessions/auth lifecycle; T-013 UI foundation; T-012 append-only audit; T-011 API
  skeleton; T-010 test foundations; T-009 authorization v1; T-008…T-006 schema. See `LOG.md`.

## Blockers and risks
| Item | Impact | Owner | Next action | Review |
|---|---|---|---|---|
| D-001 production storage provider | Blocks production media only; dev/test use MinIO | Project owner | Decide before the production release decision | T-034 |
| D-005 production domain/TLS owner | Blocks production ingress only | Project owner + ops | Decide before production deploy | T-034 |
| D-009 KPI values | Blocks success measurement, not the build | Project owner | Set before the pilot | T-034 |
| T-001 bucket evidence | Holds T-001 `[~]` | Tech authority | Re-run the bucket check with the resolved MinIO image | T-034 |
| Legacy data re-audit on staging | The only database (development) is proven empty; staging does not exist yet, so no other dataset has been audited | Tech authority | When T-034 creates staging, run `manage.py audit_legacy_data` on the restored dump before cutover; if it reports rows, obtain the owner's identity file and run `backfill_tenancy --identities <file> --dry-run` first | T-034/GATE-1 |
| Reminder-digest test fails locally with a running Celery worker (D-046) | One red test in the local suite; CI is green, but the red result invites blindness to a real notification regression | Tech authority | Make the test process eager regardless of a running worker — no skip, xfail or weakened assertion — before final acceptance | GATE-1 |
| Two stacks on one host | Port/volume/cookie collision or legacy damage | Tech authority | Isolation rules enforced; only `m-academy-*` commands | ongoing |
| Public repository (D-023) | Leaking internal material | Project owner | No secrets in tracked files; assume every commit is public | ongoing |
| Hub contract (D-004/D-010) | No H1.5 impact; Hub dormant | Project owner + Hub owner | Revisit only at a reactivation decision | H2 |

## Decisions
Single register: [`docs/decisions.md`](docs/decisions.md). This file does not duplicate values.
- **Open:** D-001, D-005, D-009, D-010 (deferred H2).
- **Confirmed (2026-11-25):** D-031…D-046 (standalone/Hub dormant, tenancy, local identity, RBAC,
  public origin, mail, PII, settings, observability, environments, UUID strategy, outbox deferral,
  performance profile, one membership per account, Mobile First and visual reference; D-045 adopts
  the official package and amends D-044; D-046 records the reminder-test debt as release-blocking).
  Older confirmed decisions remain unless marked superseded.
- **Resolved:** D-025 (local MinIO image).
- **Superseded:** D-002→D-038, D-013/D-026→D-032, D-027→D-034; ADR-002/010/011/012/014 replaced by
  ADR-023…026.
- Retired numbers (D-018…D-022, ADR numbers 15–22) are mapped in the register and must not reappear.

## Next action
**T-027 CP1 is merged** as `6d72a63` and **CP2 is complete on `task/T-027-identity-cp2`** at
`afe6084` (CI 45954587695 success), **waiting for the owner's merge approval**; the next eligible
checkpoint after that approval is **T-027 CP3** (dev-login removal, production guard, mail
delivery, auth security suite). **T-033 is unblocked but not started** and waits for the owner's instruction. **Re-audit on staging:** when T-034 provisions it, run
`manage.py audit_legacy_data` against the restored dump before any cutover; a non-zero result
blocks cutover until the owner's identity CSV is imported and `backfill_tenancy --dry-run` is
reviewed. D-046 stays open, enabled and unweakened until paid before GATE-1.
D-001, D-005 and D-009 remain open. Screen groups remain **pending owner approval**; the official
logo, Rubik binaries and licensed photography are still missing assets, and no visual
implementation may start before its design gate is satisfied.

## Update rules
- Update when project state changes. Do not turn this file into a diary (`LOG.md` owns history).
- `[x]` requires a commit, a CI run and named evidence. Do not mark work complete because code
  exists locally.
- Keep task IDs and states consistent with `docs/plan.md` and `docs/traceability.md`.
