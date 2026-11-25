# PLAN — Task Map, Dependencies and Acceptance Criteria

**Status:** Canonical execution plan. `STATUS.md` reports state; this file defines work.
**Last updated:** 2026-11-25
**Implements:** all CHARTER requirements; gate composition in §5.
**Depends on:** `CHARTER.md`, `ARCHITECTURE.md`, `RULES.md`, `docs/access-control.md`,
`docs/security.md`, `docs/domain-model.md`, `docs/api.md`.

## 1. How to read this plan
- A task is the unit of a branch and a report. A large task is split into **checkpoints (CP1,
  CP2…)**; each checkpoint is independently testable and ends with a commit, but the task closes
  only when every checkpoint and acceptance criterion is verified.
- Status lives in `STATUS.md`, not here. This file carries the definition, dependencies and
  acceptance criteria; editing scope here is an owner-approved change.
- A task is eligible when all dependencies are `[x]` and it is not `[!]` blocked.
- No task may be skipped because a later one is more interesting; dependency order wins.
- Each card lists the evidence that must exist before the task closes. “Tests pass” without a
  test name or command output is not evidence.

## 2. Task map
| ID | Task | Status owner | Depends on | Gate |
|---|---|---|---|---|
| T-001 | Repository and stack bootstrap | `[~]` (bucket check outstanding) | — | GATE-1 |
| T-002 | Settings profiles, Celery queues, JSON logging, i18n foundation | `[x]` | T-001 | GATE-1 |
| T-003 | `academy` skeleton: TenantModel, adapters, exceptions, import boundary | `[x]` | T-002 | GATE-1 |
| T-004 | Adapter interfaces + stub + contract suites | `[x]` | T-003 | GATE-1 |
| T-005 | Domain events on commit | `[x]` | T-003 | GATE-1 |
| T-006 | Catalog models and migrations | `[x]` | T-003 | GATE-1 |
| T-007 | Assignment/progress/completion models | `[x]` | T-006 | GATE-1 |
| T-008 | Quiz, reminder, notification, audit models | `[x]` | T-007 | GATE-1 |
| T-009 | Authorization engine v1 (capabilities, scopes, DRF/web guards) | `[x]` (replaced by T-028) | T-004 | GATE-1 |
| T-010 | Test foundations, two-company fixtures, isolation suite | `[x]` | T-008 | GATE-1 |
| T-011 | API skeleton, errors, pagination, OpenAPI, health | `[x]` | T-009 | GATE-1 |
| T-012 | Append-only audit ledger | `[x]` | T-008 | GATE-1 |
| T-013 | UI foundation: tokens, RTL/LTR shell, showcase, error pages | `[~]` (extended by T-029) | T-002 | GATE-1 |
| T-014 | Session/auth lifecycle v1 (dev login, suspension, throttles) | `[x]` (replaced by T-027) | T-004 | GATE-1 |
| T-015 | Hub HTTP integration (identity, webhooks, adapters, fake) | `[x]` (quarantined by T-033) | T-004, T-014 | GATE-1 |
| T-016 | Permission grants v1 + last-admin guard | `[x]` (migrated by T-028) | T-009 | GATE-1 |
| T-017 | Content services and API | `[x]` | T-011, T-016 | GATE-1 |
| T-018 | Media upload, HLS, playback | `[x]` | T-004, T-017 | GATE-1 |
| T-019 | Assignments, auto-enroll, gating | `[x]` (adapted by T-026/T-032) | T-017 | GATE-1 |
| T-020 | Heartbeat/anti-skip, completion | `[x]` | T-019 | GATE-1 |
| T-021 | Notifications and reminders v1 | `[x]` (adapted by T-032) | T-020 | GATE-1 |
| T-022 | Reports and CSV | `[x]` (adapted by T-032) | T-020 | GATE-1 |
| **T-023** | Learner + management web UI (old scope) | `[–]` **superseded by T-031** | — | — |
| **T-024** | Hardening + E2E + ops + pilot (old scope) | `[–]` **superseded by T-034** | — | — |
| **T-025** | Documentation and governance consolidation | `[x]` (merged `b592498`) | owner approval | GATE-1 |
| **T-026** | Tenancy and account foundation | `[~]` CP1 on branch `task/T-026-tenancy-schema`; CP2/CP3 pending | T-025 | GATE-1 |
| **T-027** | Local identity and account lifecycle | `[ ]` | T-026 | GATE-1 |
| **T-028** | Dynamic scoped RBAC and administration API | `[ ]` | T-027 | GATE-1 |
| **T-029** | Public website, auth screens and application shell (ar/en) | `[ ]` | T-028 | GATE-1 |
| **T-030** | Platform and company administration consoles | `[ ]` | T-029 | GATE-1 |
| **T-031** | Learner and management application UI (was T-023) | `[ ]` | T-028, T-029 | GATE-1 |
| **T-032** | Tenant-aware notifications, reminders and reports | `[ ]` | T-027, T-028 | GATE-1 |
| **T-033** | Hub quarantine as an optional integration | `[ ]` | T-026 | GATE-1 |
| **T-034** | Release hardening, operations, security/privacy evidence, pilot (was T-024) | `[ ]` | T-030…T-033 | GATE-1 |
| **T-035** | Official UI/UX reference adoption and repository hygiene | `[x]` (merged in `47638b0`; docs only) | T-025 | — |

Dependency graph:
```
T-025 → T-026 → T-027 → T-028 → T-029 → T-030 ─┐
                    │        └────→ T-031 ──────┤
                    └────→ T-032 ───────────────┼→ T-034 → GATE-1
T-026 → T-033 ─────────────────────────────────┘
```
T-031 and T-032 may run in parallel after T-028; T-033 may run in parallel with T-027/T-028.
T-035 is a documentation prerequisite for the UI tasks (T-029–T-031) and does not block backend
checkpoints.

## 3. Impact on completed work (no duplicate delivery)
| Task | Kept | Needs revalidation / extension | Where |
|---|---|---|---|
| T-001 | Repository, image, compose, CI | Bucket check evidence; CI gains G10–G12 | T-034 |
| T-002 | Settings profiles, logging, ar catalogue | English catalogue, per-company locale, new settings | T-029, T-032 |
| T-003 | TenantModel, adapter loader, exceptions | Org FK instead of opaque UUID; approved exceptions for global models | T-026 |
| T-004 | Identity/organization/notify/storage seams + contract suites | Local mail transport; Hub seams become optional | T-027, T-033 |
| T-005 | On-commit events | Handlers resolve company/membership; no Hub dependency | T-026, T-032 |
| T-006–T-008 | Catalog/learning/audit schema | User/department refs become FKs; composite tenant FKs; new tenancy tables | T-026 |
| T-009 | Permission guard structure, scope patterns | Permission catalogue, role assignments, company scope, platform scope | T-028 |
| T-010 | Two-org isolation fixture | Third fixture state (suspended company, removed membership), cross-company FK tests | T-026, T-028 |
| T-011 | API skeleton, errors, pagination, OpenAPI | Auth/me/org/member/role endpoints; error codes | T-027, T-028, T-030 |
| T-012 | Append-only ledger + `record` service | Nullable company (platform events), actor UUID, platform audit view | T-026, T-030 |
| T-013 | Tokens, shell, error pages, font | Public shell, en, auth pages, dynamic nav, accessibility evidence | T-029 |
| T-014 | Suspension middleware, throttle scopes | Replaced by real auth; dev login removed; session list/MFA | T-027 |
| T-015 | Hub client, verifier, webhook receipts, tests | Disabled by default, routes unmounted, no jobs; reactivation runbook | T-033 |
| T-016 | Grant/revoke + last-admin transaction pattern | New grant model, scope semantics, escalation rules; data migration | T-028 |
| T-017–T-022 | Content, media, learning, notifications, reports logic | Permission codes, membership recipients, per-company time zone, org settings, platform aggregate | T-028, T-032 |
| T-023/T-024 | UX acceptance ideas only (reference) | Superseded; not merged work | T-031, T-034 |

No completed task is silently reopened: the change is a new task, and the old acceptance
evidence remains in `LOG.md`.

## 4. Task cards

### T-025 — Documentation and governance consolidation
**Goal:** a single, consistent governance and specification set that makes «كمل» sufficient.
**Scope:** charter 2.5; architecture target; rules and «كمل» protocol; decision register; tenancy,
identity, RBAC, security, API, schema, configuration, migration, UI, notifications, reports, jobs,
hub, operations, performance, traceability, status, log, skills. No code/template/migration/
contract/library change.
**Depends on:** owner approval of this consolidation.
**Outputs:** updated documents; `check_docs` green; branch and commit; final report.
**Acceptance criteria:**
1. No contradictory statement between CHARTER/ARCHITECTURE/RULES/decisions/specs on scope,
   identity, tenancy, permissions or Hub.
2. Every H1.5 requirement has a task and a criterion; every task cites a requirement.
3. Superseded decisions and tasks are marked, not deleted; no duplicate IDs.
4. `python scripts/check_docs.py` passes; links resolve; no retired identifier is revived.
5. Cross-document review recorded in the final report; automated gaps named as plan items.
6. The H1.5 model states at most one company membership per normal account (D-043), removes every company
   chooser/switcher API, screen and setting, and keeps platform administration membership-free.
7. Mobile first and the visual-reference gate are recorded once in the owning documents (D-044),
   and the capability-preservation matrix in `docs/traceability.md` covers every earlier function.
8. `STATUS.md`/`LOG.md` evidence points to the content commit and its CI run, with the evidence
   policy preventing a self-referential commit id.
**Tests:** documentation checker, link/identifier grep, manual consistency pass.
**Risks:** docs drift from code; mitigated by T-026+ updating owning docs and T-034 revalidating.
**Evidence:** commit + CI docs job + report.

### T-026 — Tenancy and account foundation
**Checkpoints:** CP1 schema expand (four tables, nullable FKs, constraints, seed Masheed); CP2 mapping/backfill and reconciliation report; CP3 server company context from the single membership, `/me/organization`, isolation suite green.
**Goal:** replace the fixed organization id and opaque refs with real companies, accounts,
memberships and departments, without changing authentication behaviour yet.
**Scope:** `Organization`, `Department`, `User`, `Membership` models and migrations; org FK on
every tenant table; composite tenant FKs; company context derived server-side from the single
membership; seed
Masheed as the first company; legacy data migration command (org id → Organization, `user_ref` →
`User`/`Membership`, `owner_department_ref`/`target_ref` → Department/Membership);
`UNIQUE (user_id)` on `Membership` (D-043); `/me/organization`; updated `Principal`; dev login
selects a seeded **user** (its membership supplies the company), never a company.
**Out of scope:** password login/MFA (T-027), roles/permission catalogue (T-028), UI consoles.
**Acceptance criteria:**
1. A fresh migration creates the four tables with `UNIQUE (user_id)` on `Membership`; reverse
   migration succeeds in development.
2. Every tenant table has a non-null `organization_id` FK; a cross-company parent insert fails
   with an integrity error (tested).
3. The company comes only from the caller's single membership, never from a request body, session
   selection or client header; no switch endpoint exists; a tampered id returns 404/403 and writes
   an audit denial.
4. Two companies with identical data cannot read each other's courses, enrollments, progress,
   reports, media keys or audit (isolation suite expanded).
5. Legacy org id and user refs migrate idempotently; duplicate memberships are reported and the
   migration aborts for manual resolution; counts reconcile; training/progress rows remain
   attached to the same learner.
6. Masheed exists once as an active company; its departments mirror the legacy department list.
7. A second membership insert for any user fails at the database; the service maps it to
   `already_member`; a platform-only account has no membership and no synthetic company.
**Tests:** `test_tenancy_constraints`, `test_single_membership`, `test_org_context`, expanded
`test_isolation`, migration rehearsal on a snapshot.
**Risks:** data mapping errors or hidden duplicate memberships; mitigated by dry-run + duplicate
report + reconciliation + backup.
**Docs:** domain-model, api, configuration, migration-h1.5, decisions, STATUS.
**Evidence:** migration output, isolation suite, reconciliation counts, CI.

### T-027 — Local identity and account lifecycle
**Checkpoints:** CP1 email/password core, verification and reset; CP2 invitations, session management and MFA; CP3 dev-login removal, production guard, mail delivery and auth security suite.
**Goal:** secure, independent authentication with real accounts, replacing the development stub.
**Scope:** Django auth + Custom User; login/logout; email verification; password reset/change;
invitations; session listing/revocation and idle/absolute policy; TOTP MFA + recovery codes;
login throttling/enumeration-safe errors; Argon2 verification; security audit events; local mail
transport for account mail; dev login removed outside dev/test with a startup guard.
**Depends on:** T-026.
**Acceptance criteria:**
1. Only email+password authenticates; a wrong password never creates a session; a self-selected
   role is impossible.
2. Verification, reset, invitation and password change flows work end-to-end with the test mail
   transport; tokens are single-use, hashed and expire as documented. Accepting an invitation
   when the email already has a membership in another company returns `already_member`; no second
   membership is created.
3. TOTP is enforced for `super_admin`/`company_admin`; recovery codes work once; disabling MFA
   requires a second factor.
4. Five failed logins lock the pair for the window; the response never reveals whether an email
   exists; failures are audited with a truncated IP.
5. Session revocation and password change invalidate other sessions; idle timeout works.
6. `ACADEMY_DEVELOPMENT_LOGIN=true` with `ACADEMY_ENV=production` or `DEBUG=false` fails startup (test).
7. No password, token, secret or email appears in logs, audit metadata, error reports or API
   responses (tests/greps).
8. Login redirects directly to the first permitted dashboard; there is no company chooser, and a
   platform-only account lands in platform administration without a synthetic membership.
**Tests:** auth flow matrix, token replay, MFA, throttling, enumeration, session revocation,
second-membership invitation rejection, login redirect, production-settings guard, audit
assertions.
**Risks:** mail deliverability; MFA lockout. Mitigations: recovery codes, admin reset runbook,
staging mail test.
**Docs:** security §2–§3, api §3, configuration §2/§4, domain-model §2.0, operations.
**Evidence:** test names + CI, staging mail transcript, guard test.

### T-028 — Dynamic scoped RBAC and administration API
**Checkpoints:** CP1 catalogue/models/default roles; CP2 resolver, scope enforcement, escalation and last-admin guards; CP3 member/role/grant/department API, legacy grant migration, capabilities v2.
**Goal:** one permission engine for platform, company and department scopes, used by API and UI.
**Scope:** `Permission` catalogue; system + custom `Role`; `RoleAssignment`, `PermissionGrant`,
`PlatformRoleAssignment`; effective-access resolver; company/department/self scope enforcement;
last-admin and escalation guards; role/member/department endpoints; migration of legacy
capabilities/grants; `/me/capabilities` v2; audit events.
**Depends on:** T-027.
**Acceptance criteria:**
1. The catalogue matches `docs/access-control.md` §2 exactly (data test), and every default role
   matches §3.
2. For each default role, allow/deny/scope matrix passes on representative API and web routes;
   cross-company access is 404; a department manager cannot read a sibling department.
3. A Company Admin cannot grant a platform permission, a permission they lack, or a broader
   scope; self-escalation returns 403 `escalation_denied` and changes nothing.
4. Removing/demoting the last platform or company admin returns 409 `last_admin` and leaves state
   unchanged.
5. Legacy `academy.*` capability names and old grants are migrated once and no runtime check uses
   them afterwards.
6. Every role/grant/suspension change writes one audit event with actor, company and target.
7. `/me/capabilities` returns exactly the documented shape and never leaks another member's data;
   a platform-only account has `organization: null`, `membership: null` and only its platform
   permissions.
8. Authorization always resolves the company from the one membership; role and scope tests reject
   any assumption of multiple memberships or client-selected companies.
**Tests:** `test_role_matrix`, `test_catalogue_integrity`, `test_escalation`,
`test_last_admin`, `test_scope_department`, `test_capabilities_payload`, audit assertions.
**Risks:** over-broad COMPANY scope; mitigated by matrix tests. Permission sprawl; catalogue is
capped and reviewed.
**Docs:** access-control (canonical), api §2/§10, domain-model §2.0, security, traceability.
**Evidence:** matrix output, catalogue test, CI.

### T-029 — Public website, auth screens and application shell (ar/en)
**Checkpoints:** CP1 public pages P1–P5 on `/`; CP2 auth screens X1–X5 and direct post-login routing; CP3 application shell, dynamic navigation, en catalogue, UI state contract and accessibility.
**Goal:** a professional public site on `/`, independent auth pages, and a permission-aware
bilingual application shell under `/academy/`.
**Scope:** public pages P1–P5 (home, about, programmes, contact, privacy/terms) with no session;
login, reset, verification and invitation-accept pages; app shell with dynamic sidebar and
header; English catalogue; RTL/LTR; mobile-first layouts; state contract (loading/empty/error/
forbidden/…); accessibility fixes; public SEO basics (title/description, no analytics).
Each screen group records its approved reference and owner approval (or an explicit waiver) in
`docs/ui/wireframes.md` before implementation; the official package and its gaps are in
`docs/ui/design-reference.md` (D-044/D-045).
**Depends on:** T-028.
**Acceptance criteria:**
1. Every P/X/shell screen renders in Mobile-first order and passes at 320, 390, 768, 1024, 1440
   and 1920 px in ar and en with no unjustified page-level horizontal overflow; content reflows
   instead of shrinking, and core functions remain reachable by touch and keyboard.
2. Public pages contain no application data and no UUID; login button targets `/academy/login/`.
3. Auth pages complete the T-027 flows and land directly on the permitted dashboard; no company
   chooser exists; errors use the documented states; no success message before a server response.
4. Sidebar groups and actions match effective permissions for each default role; direct URL
   access is still denied server-side.
5. Language switch persists (session/profile) and all new strings are in both catalogues.
6. axe reports zero critical/serious issues on P1, X1, L1 and N1; keyboard-only navigation works
   and touch targets meet the documented minimum.
7. The design gate for this group records the approved reference or owner waiver; no screen claims
   pixel compliance without it.
**Tests:** route/render tests, permission-to-nav matrix, axe smoke, six-width snapshots
(320/390/768/1024/1440/1920) in both languages, visual baselines where an approved reference exists.
**Risks:** design drift; mitigated by the binding reference/tokens, screen spec and visual
regression. Missing translations; CI check for untranslated new msgids.
**Docs:** ui/screen-specification, wireframes, api §13, configuration, security CSP.
**Evidence:** axe output, viewport renders, nav matrix.

### T-030 — Platform and company administration consoles
**Checkpoints:** CP1 company administration N1–N4/S1; CP2 platform administration N5–N8/S2, including audited read-only company access.
**Goal:** let a Super Admin run companies/platform users and a Company Admin run their company
without touching the database.
**Scope:** N5 platform overview, N6 companies (create/suspend/reactivate/archive, first admin),
N7 platform users/roles, S2 platform audit, platform read-only access; N1 members/invitations,
N2 roles/grants, N3 departments, N4 settings, S1 company audit; audit visibility and disabled-
action reasons.
**Depends on:** T-029.
**Acceptance criteria:**
1. A Super Admin creates a company, invites its first Company Admin, suspends and reactivates it;
   every action is audited and reflected in the member's access immediately.
2. A Company Admin manages only their company; another company's ids are 404 in UI and API.
3. Member invitation → acceptance → role assignment works end-to-end; removal cancels open
   enrollments and preserves history.
4. Department tree create/re-parent/archive works with cycle and non-empty guards.
5. Role editor cannot include platform permissions; last-admin guards surface as disabled actions
   with a reason.
6. Platform access is read-only and visibly marked; write attempts are refused and audited.
7. All screens implement the documented states and pass axe at 320/390/768/1024/1440/1920 px, mobile-first,
   with no horizontal overflow; each administration group has an approved visual reference or
   recorded owner waiver.
8. Platform company access uses an explicit company id on platform routes, creates no membership,
   and invitation of an already-affiliated email is refused with `already_member`.
**Tests:** permission matrix per screen, lifecycle integration tests, last-admin UI, audit
assertions, single-membership invitation rejection, axe.
**Risks:** destructive admin actions; confirmations + reason + audit + soft lifecycle.
**Docs:** ui spec, api §10–§11, access-control §6/§8, operations.
**Evidence:** integration test names, axe results, audit samples.

### T-031 — Learner and management application UI (was T-023)
**Checkpoints:** CP1 learner L1–L4/E with player states; CP2 training management A–D and reports F; CP3 responsive/accessibility/journey evidence.
**Goal:** deliver the learning and training-management screens on the new tenancy and RBAC.
**Scope:** L1 dashboard, L2 my courses, L3 course details, L4 achievements, E player, A academy
home, B/C course authoring, D assignment, F team training, X6 access denied; mobile-first ar/en;
player states (loading, stalled, ended, locked, offline); CSV export UI.
**Depends on:** T-028, T-029.
**Acceptance criteria:**
1. A learner completes a full course through the UI: open, watch to threshold, complete lessons
   in order, acknowledge, complete enrollment; the server state matches the UI.
2. Locked lessons cannot be opened by direct URL or API; playback URLs are short-lived.
3. A training manager creates a course with two sections and video lessons, publishes it,
   assigns it, and sees the roster/report.
4. Empty/loading/error/forbidden/offline states follow the screen contract; no duplicate submit.
5. All screens work keyboard-only and at 320/390/768/1024/1440/1920 px in ar and en with no overflow; axe
   zero critical/serious; each group records an approved visual reference or owner waiver and
   visual baselines where the reference exists.
6. No raw UUID is shown where a name exists; dates/numbers follow the active locale and company
   time zone.
**Tests:** Playwright journey, permission-to-action matrix, axe, six-width responsive and visual
snapshots, API state assertions.
**Risks:** video UX on mobile; device testing. Scope creep into quiz UI; explicitly excluded.
**Docs:** ui spec, wireframes, api §5–§8, notifications links.
**Evidence:** journey recording/output, axe, screenshots per viewport (stored in LOG reference).

### T-032 — Tenant-aware notifications, reminders and reports
**Checkpoints:** CP1 local recipients, per-user/company locale, SMTP transport and account mail; CP2 per-company reminder schedule and manager resolution; CP3 platform aggregate report and CSV adaptation.
**Goal:** remove the remaining single-company/Hub assumptions from mail, reminders and reporting.
**Scope:** mail recipients from `User`/`Membership`; per-user/company locale; per-company sender
and time zone; reminder scheduler by local hour; manager resolution by role/department; links
from `ACADEMY_PUBLIC_BASE_URL`; platform aggregate report with explicit company filter; report
columns/labels from company settings.
**Depends on:** T-027, T-028.
**Acceptance criteria:**
1. Verification/reset/invitation/completion/reminder mail is delivered through SMTP with the
   recipient's language and the company's sender/time zone; no Hub call is made.
2. Reminders fire at the company's local hour, once per local day, across a DST change and a
   duplicate beat tick (idempotency proven).
3. Manager escalation resolves to the assigned manager, else a training manager of the
   learner's department, else the Company Admin; one digest per recipient per day.
4. Platform summary reports require `platform.organization.view`, filter by company explicitly
   and never merge companies without a label; company reports stay scoped.
5. CSV export remains formula-safe and audited.
**Tests:** frozen-clock reminder matrix with two companies/time zones, mail rendering per locale,
manager resolution, platform report permission/scope, idempotency.
**Risks:** DST and locale edge cases; fixed-clock tests. Deliverability; staging check.
**Docs:** notifications, reports, background-jobs, configuration §7, domain-model §7.8.
**Evidence:** test names, rendered mail samples, scheduler output.

### T-033 — Hub quarantine as an optional integration
**Checkpoints:** CP1 flag, route removal and config independence; CP2 task/registry isolation and contract tests; CP3 reactivation runbook and documentation.
**Goal:** keep the integration code and tests while making Hub impossible to depend on by
accident.
**Scope:** `ACADEMY_HUB_ENABLED=false` default; conditional URL mounting; no startup requirement
for Hub keys/URLs; no beat tasks or reconciliation when disabled; adapters return “not
configured”; admin-visible state (platform settings, read-only); tests for 404 routes and absence
of jobs; reactivation runbook; docs status Dormant.
**Depends on:** T-026.
**Acceptance criteria:**
1. With defaults, the app boots without any Hub variable; `/internal/hub/webhooks/` is 404; no
   Hub Celery task is registered/scheduled; no outbound request is attempted (test with a blocking
   transport).
2. Enabling the flag mounts routes and registers jobs; disabling it again leaves no scheduled
   work.
3. Existing Hub contract tests still pass when enabled against the loopback fake.
4. A written reactivation checklist exists (decision, security review, keys, contract version,
   acceptance tests).
5. No authentication, mail, learning or reporting path imports Hub code in standalone mode.
**Tests:** flag on/off route tests, task registry inspection, outbound-call assertion, contract
suite.
**Risks:** dead code drift; kept tests + reactivation checklist. Accidental enablement; flag
requires platform permission and is audited.
**Docs:** hub-contract, configuration, background-jobs, api §12, decisions D-031.
**Evidence:** flag-off test run, task list, contract suite.

### T-034 — Release hardening, operations and pilot (was T-024)
**Checkpoints:** CP1 staging/CD, observability and alerts; CP2 backup/restore drill, load/security/privacy evidence; CP3 E2E/axe/visual regression, capability revalidation, pilot, consistency audit and GATE-1 evidence.
**Goal:** prove the platform is operable, secure and usable, then close GATE-1.
**Scope:** staging environment and CD; backup + restore drill; metrics/tracing/error reporting and
alerts; load test at D-042 profile; E2E and accessibility across the journey; security review
(ASVS L1), dependency/image scans; privacy export/anonymization test; performance query plans;
pilot with a real company; visual regression against approved references; documentation/consistency
audit; gate evidence.
**Depends on:** T-030, T-031, T-032, T-033.
**Acceptance criteria:**
1. Staging deploys from CI with one image; production deployment procedure and rollback are
   rehearsed; secrets are not in the image.
2. A backup is restored into a clean environment and verified row-for-row for a sample company;
   RPO/RTO targets are met and the drill is recorded.
3. `/healthz`, metrics, error reporting and every alert threshold are live and tested by
   induced failure (stop DB/Redis, fail a task, force a 5xx).
4. Load test meets API p95 < 300 ms, heartbeat p95 < 150 ms at the design profile, or an
   owner-accepted deviation is recorded.
5. ASVS L1 checklist complete; `pip-audit` and image scan clean or an approved exception exists;
   CSP/HSTS/cookies verified on staging.
6. Privacy export and anonymization tests pass; retention jobs dry-run produces the expected
   counts.
7. Full journey E2E passes in ar/en at 320/390/768/1024/1440/1920 px, mobile-first; axe zero
   critical/serious; visual regression passes against every approved implemented baseline (or its
   recorded waiver).
8. Pilot completes a real course with ≥ 1 company and ≥ 10 learners; feedback triaged.
9. All gates G1–G12 green on `main`; documentation check passes; `STATUS.md` links every evidence
   item; `LOG.md` has a `[RELEASE]` entry.
10. The capability-preservation matrix in `docs/traceability.md` is verified row by row against the
    H1.5 tenancy/RBAC model; no earlier capability is missing without an explicit owner decision.
**Tests:** E2E, axe, Locust, restore script, alert drills, ASVS checklist, privacy tests.
**Risks:** staging cost, pilot availability, external provider (D-001/D-005). Owner decisions
required before production go-live, not before staging.
**Docs:** operations, performance-profile, security, traceability, STATUS, LOG.
**Evidence:** CI run, restore transcript, load report, ASVS checklist, axe report, pilot notes.

### T-035 — Official UI/UX reference adoption and repository hygiene
**Goal:** one approved design source of truth, a clean repository root and permanent Mobile First
/ responsive / single-shell governance before UI work starts.
**Scope:** adopt the owner's `Masheed-Academy-Official-UI-UX-v1.0`; verify reference fingerprints;
merge its text specifications and tokens into `docs/ui/`; record provenance, archive and restore;
archive the superseded UX packages, interim PDF and local document backups outside the repository;
Git-ignore local visual references; reconcile screen IDs with tasks and the gate record; update
RULES, ARCHITECTURE, decisions, traceability, README, skills, STATUS and LOG.
**Out of scope:** UI implementation, T-026 CP1, code/templates/stylesheets, data model,
migrations, API/Hub contracts, infrastructure, gate weakening.
**Depends on:** T-025.
**Acceptance criteria:**
1. The package is intact: all 14 boards match the published SHA-256 and dimensions, and no file is
   missing from the 24-file manifest.
2. `docs/ui/design-system.md` and `design-tokens.json` are the only visual authority; no second
   design system, token set or conflicting wireframe remains in the active tree.
3. Superseded packages, the interim PDF and the local document backup are removed from the active
   repository but preserved outside it, with hashes and a restore procedure recorded.
4. No design binary or package is tracked; `.design-references/` and root-level ZIPs are ignored.
5. Every screen group maps to a reference board, a plan task and a pending owner gate; no gate is
   recorded as passed.
6. Mobile First, the six verification widths, the single master shell and rendered-baseline visual
   regression are binding in `RULES.md` and the UI documents, without duplicating values.
7. `python scripts/check_docs.py` passes, links resolve, and the root contains no untracked design
   material other than the documented local references; no code, migration or dependency changed.
**Tests:** documentation checker, link/retired-identifier scan, reference hash verification,
`git status`, manual consistency pass across the UI documents.
**Risks:** losing a visual reference; mitigated by the external archive + fingerprints. Accidentally
publishing mockups; mitigated by ignore rules and the public-repository warning.
**Docs:** design-system, design-tokens, design-reference, wireframes, screen-specification, RULES,
ARCHITECTURE, decisions D-045, traceability, README, SKILLS, STATUS, LOG.
**Evidence:** commit + CI docs job, hash table, before/after root listing, final report.

## 5. GATE-1 — H1.5 foundation
GATE-1 closes when:
1. T-025…T-034 are `[x]` with their evidence; every row of the capability-preservation matrix
   in `docs/traceability.md` is verified under the new tenancy/identity model; replaced or
   quarantined tasks (T-009/T-014/T-016/T-015) are covered by T-027/T-028/T-033 and their
   regression evidence.
2. REQ-01…REQ-28 are verified in `docs/traceability.md` with evidence links; no orphan requirement.
3. Gates G1–G12 pass on `main`; no bypassed/skipped/silenced check.
4. `python scripts/check_docs.py` passes and the cross-document consistency audit is recorded.
5. The owner has seen the pilot demo and approved the gate in `LOG.md` (`[RELEASE]`).
6. Open decisions that block production (D-001 storage provider, D-005 domain/TLS) are resolved or
   explicitly accepted by the owner for the pilot environment.

GATE-1 is **pilot-ready on staging**, not automatic production go-live. Production release
requires a separate owner decision that closes D-001/D-005 and accepts the operational baseline.

## 6. Deferred backlog (do not start before GATE-1)
| Item | Horizon | Trigger |
|---|---|---|
| Billing, plans, subscriptions, company self-registration | H2 | Commercial decision + D-031 review |
| White-label branding, custom domains | H2 | First paying company requiring it |
| SSO (SAML/OIDC), SCIM | H2/H3 | Customer requirement; security review |
| WebAuthn/passkeys | H2 | MFA adoption + library review |
| Quiz UI, certificates, SCORM/xAPI | H2/H3 | Learning requirement |
| Malware scanning, WAF/CDN, RLS, partitioning, outbox | H2 or measured trigger | Security/scale evidence |
| Hub live integration | H2 | D-010 + reactivation checklist |
| Advanced analytics, data warehouse | H3 | Volume + decision need |

A deferred item enters the plan only with an owner-approved requirement, a task ID and acceptance
criteria; it is never implemented “while nearby”.
