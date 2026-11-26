# LOG — Significant Project Events

> Append-only historical record. Do not silently edit or delete old entries. Correct
> mistakes with a new entry referencing the original.

## Entry template

### [YYYY-MM-DD] — Event title

- **Type:** Milestone | Change | Decision | Release | Incident | Dependency | Verification | Exception
- **Status:** Proposed | Approved | Implemented | Tested | Verified | Merged | Released | Rejected | Superseded
- **Summary:** What happened.
- **Impact:** What changed or is affected.
- **Evidence:** Commit, PR, test report, deployment or other evidence. Required for
  Implemented, Tested, Verified, Merged and Released entries.
- **Approved by:** Required when approval applies.
- **References:** Task, ADR, issue, release, exception record or superseding entry.
- **Corrects:** Optional.

---

## Entries

### [2026-11-26] — T-027 CP1 merged

- **Type:** Milestone
- **Status:** Merged
- **Summary:** The owner approved CP1 and it merged into `main` with `--no-ff` as `6d72a63`
  after its branch passed CI.
- **Impact:** Local email/password sign-in, verification and reset are now on `main`. T-027 stays
  `[~]`; CP2 (invitations, session listing/revocation, MFA) is the next eligible checkpoint and
  CP3 (dev-login removal, production guard, mail transport) follows it. No other task moved.
- **Evidence:** Branch `task/T-027-identity-cp1` at `c157739`, CI run 45786234699 success; merge
  commit `6d72a63`.
- **Approved by:** Project owner (2026-11-26): «معتمد CP1، ادمج وفق الحوكمة».
- **References:** T-027 CP1, D-033, D-043, `STATUS.md`, `docs/plan.md` §4 T-027.

### [2026-11-26] — T-027 CP1: local email/password identity, verification and reset

- **Type:** Change
- **Status:** Implemented (branch `task/T-027-identity-cp1`; merge awaits owner approval)
- **Summary:** Local accounts now authenticate with email + password through
  `academy.access.backends.EmailPasswordBackend`, the only configured backend. The email is
  matched case-insensitively, an unknown address pays one dummy hash verification, and a disabled
  or unverified-import account is refused with the same generic `invalid_credentials` response.
  Five failures per email+IP within `ACADEMY_LOGIN_WINDOW_SECONDS` lock the pair (429), every
  failure and lock is logged with a truncated address and no email, and a success clears the
  counter. Sign-in rotates the session key and stores only the account UUID, a password
  fingerprint and default roles; a password reset/change therefore invalidates other sessions
  without a second registry. `AccountToken` (migration `0010`) stores only a SHA-256 digest with
  an expiry and a single-use claim; issuing a new token of the same purpose retires the previous
  one. Email verification activates the account and `email_unverified` (403) refuses tenant data
  until then. Password policy is Django's four validators at `ACADEMY_PASSWORD_MIN_LENGTH=12`;
  Argon2 is first in `PASSWORD_HASHERS` with PBKDF2 retained for older hashes (D-033). Seven
  `/api/v1/academy/auth/` endpoints follow `docs/api.md` §3. The development stub is unchanged
  and still gated by `DEVELOPMENT_LOGIN`; its removal is CP3.
- **Impact:** The session can now identify a real account in standalone mode; `Principal` derives
  the company from that account's single membership and refuses an unverified address. Grants are
  still resolved from `user_ref`, which keeps the T-028 work unchanged. No existing test was
  weakened: the two model-classification tests now name `AccountToken` as the third global table
  (`docs/domain-model.md` §1.1/§2.0.10). D-046 is untouched and still the only local failure.
- **Evidence:** `tests/test_auth.py` (18 tests: credential-only sessions, enumeration equality,
  case folding, disabled accounts, the five-failure lock, hashed/single-use/expired tokens,
  reset invalidation, weak-password refusal, change-password session semantics, unverified
  refusal, logout, no-secret log grep); `pytest -q` → 653 passed, 1 failed (D-046 only);
  `ruff check`, `ruff format --check`, `mypy .`, `makemigrations --check`, G5, G7 and G9 green.
- **Approved by:** Project owner (2026-11-26, «كمل» after T-026 closure authorises the next
  checkpoint); the merge itself still needs explicit approval.
- **References:** T-027 CP1, REQ-22, D-033, D-037, D-043, `docs/security.md` §2–§3, `docs/api.md`
  §3/§14, `docs/domain-model.md` §2.0.2/§2.0.10.

### [2026-11-26] — T-026 closed: reconciliation condition accepted, staging re-audit required

- **Type:** Milestone / Decision
- **Status:** Closed (Accepted)
- **Summary:** The owner accepted the 2026-11-26 audit as proof that the only existing database
  (development `academy`) holds no legacy row, closing CP2's reconciliation condition and T-026.
  The task is `[x]` with CP1 `a5373c0`, CP2 `e3f9715` and CP3 `5ae89f6` on `main` and their CI
  runs green. The closure changed no code, migration, guard or test. The audit is a standing
  requirement, not a waiver: when T-034 provisions staging, `manage.py audit_legacy_data` runs on
  the restored dump before cutover and its counts join the release evidence; a non-zero result
  blocks cutover until the owner's identity CSV is imported, the `--dry-run` report is reviewed
  and the duplicate-membership queries stand at zero.
- **Impact:** T-027 and T-033 are unblocked but **not started**; both wait for the owner's
  instruction, and T-033 may run in parallel with T-027/T-028. D-046 stays open, enabled and
  unweakened until paid before GATE-1; the audit append-only guard and the immutable completion
  guard are unchanged. D-001, D-005 and D-009 remain open, and screen groups remain pending
  owner approval.
- **Evidence:** `STATUS.md` task table and next action; `docs/plan.md` §4 T-026 row, criterion 5
  and evidence line; `docs/migration-h1.5.md` §8; `docs/operations/environments.md` §1.
- **Approved by:** Project owner (2026-11-26): «معتمد التدقيق والأدلة، أغلق شرط المطابقة وأغلق
  T-026 رسميًا وفق الحوكمة».
- **References:** T-026, REQ-21, REQ-28, D-043, D-046, T-034.

### [2026-11-26] — T-026 CP3 merged; legacy-data audit finds nothing to migrate

- **Type:** Milestone / Verification
- **Status:** Merged; T-026 closure pending owner acceptance of the audit
- **Summary:** The owner approved CP3 and asked for a documented check of whether real legacy
  data requires migration. `task/T-026-tenancy-cp3` (`cbd6e52`, CI run 45775863497 success) merged
  with `--no-ff` as `5ae89f6` (CI run 45776614160 success). The new
  `manage.py audit_legacy_data [--json]` counts, read-only and without printing any reference
  value, every tenant table's rows, every nullable backfill link still `NULL`, the distinct
  `*_ref` values per column and their union, and the duplicate-membership queries. Run against
  the only existing database (development `academy`, PostgreSQL 16.14) it reported: 1 active
  `masheed` company, 0 accounts, 0 departments, 0 memberships, 17 tenant tables with **0 rows**,
  0 rows holding a `NULL` backfill link, 0 distinct legacy references across 21 `*_ref` columns,
  0 duplicate memberships and 0 accounts in more than one company → `needs_migration: false`.
  No staging or production database exists yet (T-034 / after the release decision) and no dump
  or backup is present or tracked, so no other dataset was left unaudited.
- **Impact:** CP2's command has no input to transform in this database and the identity CSV is
  not required for it; the reconciliation condition can close on the owner's acceptance. T-026
  remains `[~]` and T-027/T-033 do not start until then. D-046, the audit append-only guard and
  the immutable completion guard are unchanged; nothing was written to any database.
- **Evidence:** Merge `5ae89f6`; branch CI 45775863497 and `main` CI 45776614160 success;
  `academy/management/commands/audit_legacy_data.py` with `tests/test_tenancy_audit.py` (3 tests,
  one asserting no reference value is printed); `docs/migration-h1.5.md` §8; `docs/plan.md` §4
  T-026 criterion 5; `STATUS.md`.
- **Approved by:** Project owner (2026-11-26): «معتمد CP3، ادمج وفق الحوكمة» with the audit
  request; acceptance of the audit is still pending.
- **References:** T-026 CP3, `docs/migration-h1.5.md` M2–M3 and §8, D-043, D-046.

### [2026-11-26] — T-026 CP3 implemented: company context from the single membership

- **Type:** Change
- **Status:** Implemented; awaiting owner merge approval
- **Summary:** The company is no longer read from `ACADEMY_ORGANIZATION_ID` on the request path.
  `academy/access/tenancy.py` resolves the account by its legacy reference, requires exactly one
  active membership, and returns the membership's company; a `membership_id` stored in the session
  is cross-checked against that row, so a tampered or stale id resolves no identity instead of
  switching tenants. `Principal` now carries `user_id`/`membership_id` (the access-cache key
  includes the membership). `GET /me/organization/` answers from the membership, returns
  `private, no-store`, ignores any company in the query string or a header, and a signed-in
  account with no active membership gets 403 `membership_inactive` on the API and the
  access-denied page on the web. The development sign-in now offers only seeded accounts with an
  active membership, stores just the account reference and membership id, and takes the
  department from the membership instead of accepting a free department reference.
- **Impact:** The single-company default is now a seed value, not the source of tenant context;
  no table, migration, service signature or read path changed. Hub mode still maps its signed
  claim (dormant, T-032 quarantines it). T-026 stays `[~]` pending this merge and the open
  real-data reconciliation; T-027/T-033 remain gated. D-046 stays enabled and unchanged.
- **Evidence:** Branch `task/T-026-tenancy-cp3`, head `a6264ba`, CI run 45775460129 success;
  `tests/test_company_context.py` (13 tests) plus updated `test_sessions`/`test_hub_identity`;
  `pytest -q` → 632 passed and only D-046 failed; `ruff check`, `ruff format --check`, `mypy .`
  (155 files), `makemigrations --check`, G5, G7 and G9 (40 files) clean.
- **Approved by:** Implementation under the owner's standing «كمل»; merge approval still pending.
- **References:** T-026 CP3, D-032, D-043, `docs/api.md` §4, `docs/access-control.md` §4.

### [2026-11-26] — T-026 CP2 merged; real-data reconciliation kept as an open acceptance condition

- **Type:** Milestone / Decision
- **Status:** Merged; acceptance condition open
- **Summary:** The owner approved CP2's implementation («معتمد CP2 من ناحية التنفيذ البرمجي») and
  asked for a governed merge while explicitly keeping the actual mapping and reconciliation of
  legacy data open until the real identity file is supplied or the absence of rows requiring
  migration is proven. `task/T-026-tenancy-cp2` (head `0ec430e`, CI run 45769212077 success) merged
  into `main` with `--no-ff` as `e3f9715`; CI run 45773205917 on `main` succeeded. The merge
  changed no code, migration, guard or test — only the approved branch content.
- **Impact:** `manage.py backfill_tenancy`, migration 0009 and their tests are on `main`. T-026
  stays `[~]`: CP3 has not started and the real-data reconciliation is not yet demonstrated, so
  T-027/T-033 remain gated. D-046 stays open, enabled and unweakened; the audit append-only guard
  and the immutable completion guard keep exactly one permitted `NULL`→value fill and still refuse
  any other edit or rewrite; no data was written to any real database.
- **Evidence:** Merge `e3f9715`; branch CI 45769212077 success; `main` CI 45773205917 success;
  `STATUS.md`, `docs/plan.md` (§4 T-026 acceptance 5) and `docs/migration-h1.5.md` (§4 M2) record
  the open condition; the empty dev database dry run still writes a complete report with every
  count at zero.
- **Approved by:** Project owner (2026-11-26): «معتمد CP2 من ناحية التنفيذ البرمجي، ادمج وفق
  الحوكمة».
- **References:** T-026 CP2, `docs/migration-h1.5.md` M2–M3, D-043, D-046.

### [2026-11-26] — T-026 CP2 implemented: legacy mapping/backfill and reconciliation

- **Type:** Change
- **Status:** Implemented; awaiting owner merge approval
- **Summary:** `manage.py backfill_tenancy` implements `docs/migration-h1.5.md` M2–M3. It reads
  the owner's `legacy_user_ref,email,display_name` CSV (strict header, unique refs, no shared
  mailbox), creates one disabled `User` per ref plus exactly one active `Membership`, creates one
  `Department` per distinct legacy ref, and fills every nullable tenancy link in batches of
  5,000 rows with one transaction per batch. An account without an address gets a
  `pending+<uuid>@invalid.masheed` placeholder and `must_set_email`; nothing is guessed. All
  learner/recipient/department refs must resolve or the run aborts before writing; unknown actor
  refs stay `NULL` and are reported, and `system` actors stay null. The JSON report reconciles
  distinct refs against created rows, names every unresolved ref and prints the
  duplicate-membership/cross-company queries at zero. Role targets and legacy capability names
  are reported as deferred to T-028, never dropped. Migration 0009 adds `User.legacy_ref`,
  `User.must_set_email` and `Department.legacy_ref` with their conditional unique constraints,
  and lets the append-only audit and immutable completion guards accept exactly one fill of
  their new nullable links from `NULL` (any other edit, and any rewrite of a filled link, is
  still refused; reversing 0009 restores the strict guards).
- **Impact:** CP2 is code-complete on its branch; no read path, API, template, permission or UI
  changed, and no real account was created — the owner's identity CSV is still required. T-026
  remains `[~]` until CP2 is merged and CP3 lands.
- **Evidence:** Branch `task/T-026-tenancy-cp2`, head `565a87c`, CI run 45768707833 success;
  `tests/test_tenancy_backfill.py` (11 tests) plus two constraint tests; local `pytest -q` →
  619 passed and only D-046 failed; migration 0009 applied → 0008 → 0009 on the dev database;
  `makemigrations --check`, `ruff check`, `ruff format --check`, `mypy .` (153 files), G7 and G9
  (40 files) clean; dry run against the empty dev database wrote a complete report with every
  count at zero.
- **Approved by:** Project owner (2026-11-26): «كمل» authorized CP2; merge approval still pending.
- **References:** T-026 CP2, `docs/migration-h1.5.md` M2–M3, D-043, D-046.

### [2026-11-25] — T-026 CP1 merged; reminder-test debt recorded

- **Type:** Milestone / Decision
- **Status:** Merged; debt open
- **Summary:** The owner approved CP1. The branch (`691abc5`) passed CI run 45699655726 and merged
  with `a5373c0`; the merge commit passed CI run 45700454330 on `main`. The pre-existing
  failure of `tests/test_reminders.py::test_the_digest_lists_every_overdue_learner_once` (local
  Celery is not eager when a worker is running; the suite reads Celery configuration before Django
  test settings) is recorded as **D-046**, release-blocking technical debt that must be fixed
  before final acceptance. The test stays enabled, unmodified and unweakened; the fix is
  configuration-only.
- **Impact:** CP1 is closed on `main`; T-026 remains `[~]` until CP2/CP3. No read path, API, template,
  permission or UI changed. Screen groups remain pending owner approval.
- **Evidence:** Merge `a5373c0`; CI on `main` 45700454330 success; CI on branch 45699655726 success;
  `docs/decisions.md` D-046; `STATUS.md` blockers.
- **Approved by:** Project owner (2026-11-25): “معتمد CP1، ادمج وفق الحوكمة”.
- **References:** T-026 CP1, D-046, `docs/plan.md` §4 T-026, GATE-1.

### [2026-11-25] — T-026 CP1 schema expand implemented

- **Type:** Change
- **Status:** Implemented (tested; awaiting owner review — not merged)
- **Summary:** CP1 of T-026, per `docs/migration-h1.5.md` M1, adds the four tenancy tables —
  `Organization`, `User`, `Department`, `Membership` — with D-043's `UNIQUE (user_id)` on
  `Membership`, the active/removed lifecycle checks, department sibling uniqueness including
  roots (`NULLS NOT DISTINCT`), and `UNIQUE (organization_id, id)` on both tenant tables. The
  existing tenant tables gain nullable `owner_department`/`created_by`/`published_by`/
  `target_membership`/`target_department`/`assigned_by`/`membership`/`recipient_membership`/
  `recipient_user`/`suspended_by`/`lifted_by`/`scope_department`/`granted_by` columns and the
  audit UUID snapshots; the legacy `*_ref` strings remain authoritative, so no read path changes.
  Migration 0008 also adds a database `organization_id` FK on every tenant table (the model field
  stays a UUID, as M1 permits) and the composite `(organization_id, department_id)` /
  `(organization_id, parent_id)` FKs, plus an idempotent seed of the deployment company
  (`ACADEMY_ORGANIZATION_ID`, slug `masheed`, `ACADEMY_COMPANY_NAME`, language and business
  timezone). The seed's reverse refuses to delete a company that already has memberships or
  departments.
- **Impact:** Schema is expanded and ready for CP2; no API, service, template, permission or
  authentication behaviour changed, and no visual implementation started. `T-026` is `[~]` on
  its branch. The import-boundary gate now allows the Academy's own identity model by name while
  still forbidding host/Django user models, and the two registry tests that asserted “every
  Academy model is a TenantModel” now name `Organization` and `User` as the approved global
  exceptions (§1.1).
- **Evidence:** Migration applied, reversed to 0007 and re-applied on the development database;
  `makemigrations --check` reports no changes; `pytest -q` → **606 passed, 1 failed**; the failure
  is `tests/test_reminders.py::test_the_digest_lists_every_overdue_learner_once`, reproduced with
  the same assertion on a clean `main` worktree (local Celery is not eager when a worker is
  running), so it is pre-existing and out of CP1 scope. `ruff check`, `ruff format --check` and
  `mypy .` (151 files) pass. New tests: `tests/test_tenancy_constraints.py` (12 constraint/seed
  cases), plus factories for `Department`/`Membership` and the session fixture that seeds both
  fixed companies.
- **Approved by:** Project owner (2026-11-25): «كمل» — CP1 only.
- **References:** T-026, `docs/plan.md` §4 T-026 criteria 1/6/7, `docs/migration-h1.5.md` §2–§3,
  `docs/domain-model.md` §1.1/§2.0.1–§2.0.4, D-026, D-043.

### [2026-11-25] — T-035 merged and closed

- **Type:** Change
- **Status:** Merged
- **Summary:** The owner approved the adoption of `Masheed-Academy-Official-UI-UX-v1.0` (D-045),
  the external archive of superseded design material and the permanent UI rules. Before closure the
  archive restore procedure was rehearsed: the archived ZIP was extracted again and all 14 boards
  re-hashed to `REFERENCE_INDEX.csv` (14/14 match, dimensions unchanged), then the scratch copy was
  removed. The untracked, superseded `INSTALLATION_AR.md` document-package note was moved to
  `../_design-archive/superseded/` with its SHA-256 unchanged. D-044 remains `Confirmed (amended by
  D-045)` and the owning documents agree; D-001, D-005, D-009 and D-010 stay open, the asset gaps
  stay recorded and every screen group stays **pending owner approval**. The capability matrix is
  still 23 rows and no gate was weakened.
- **Impact:** T-035 is closed on `main`; the single design authority and permanent Mobile First /
  responsive / master-shell / no-internal-banner rules now apply to all UI tasks. No code, template,
  stylesheet, migration, API or dependency changed and no visual implementation started.
- **Evidence:** Final branch head `6cb8776` passed CI run
  [45694300738](https://github.com/eizmadhoun2019/M_Academy/actions/runs/45694300738); merge commit
  `47638b0` passed CI run
  [45694757748](https://github.com/eizmadhoun2019/M_Academy/actions/runs/45694757748);
  `check_docs` G9 passed (40 files); no pull request or review comment was open on the branch.
- **Approved by:** Project owner, 2026-11-25 (adoption, archive and merge).
- **References:** T-035, D-044/D-045, `docs/plan.md` §4, `docs/ui/design-reference.md`.

### [2026-11-25] — T-035 official UI/UX reference adopted; legacy design material archived

- **Type:** Change
- **Status:** Verified
- **Summary:** The owner delivered `Masheed-Academy-Official-UI-UX-v1.0` as the official visual.
  The archive was verified intact: 24 files, 14 reference boards, every SHA-256 and pixel dimension
  matching `REFERENCE_INDEX.csv`. Its text specifications were merged into the owning documents
  instead of duplicating the package: `docs/ui/design-system.md` (identity, master shell,
  components, responsive rules, visual acceptance V01–V11), `docs/ui/design-tokens.json` (canonical
  values), `docs/ui/design-reference.md` (provenance, fingerprints, archive, gaps),
  `docs/ui/wireframes.md` (screen → board → task → gate) and an updated
  `docs/ui/screen-specification.md`. D-045 records the adoption and amends D-044. The superseded
  `Academy-UX-Handoff-v1.0.zip`, `Masheed-Academy-UX-Batch-1-Review.zip`, the interim
  `masheed-academy-screens.pdf` with its page renders, and the local `.docs-package-backup/` were
  removed from the active tree and preserved in `../_design-archive/` outside the repository. Boards
  are now Git-ignored under `.design-references/`; root-level ZIPs are ignored. The untracked,
  superseded `INSTALLATION_AR.md` document-package note (2026-11-23) was archived with its content
  hash unchanged. `RULES.md` makes
  Mobile First (Mobile 390 → Tablet 768 → Desktop 1440 → Large Desktop), verification at
  320/390/768/1024/1440/1920 px in ar/en, the single master shell, token-only styling, shared
  components and rendered-baseline visual regression permanent; CHARTER REQ-05/REQ-15, plan
  acceptance and traceability were aligned. A UI implementation/review skill was added.
- **Impact:** One design authority and no conflicting visual reference in the active tree. **No
  screen-group gate was closed** and no group is recorded as approved; the official logo, Rubik
  binaries and licensed photography remain owner-supplied gaps. No code, template, stylesheet,
  migration, API, Hub contract, dependency or infrastructure changed. T-026 CP1 has **not**
  started and still needs «كمل» after this task merges.
- **Evidence:** Reference hash/dimension verification output and `REFERENCE_INDEX.csv` (all 14
  match); before/after root listing; `python scripts/check_docs.py` → `G9 documentation check passed
  (41 markdown files)`; `git status` showed no design binary tracked. Restore rehearsal: the
  archived ZIP was extracted to a scratch directory and all 14 boards were re-hashed against
  `REFERENCE_INDEX.csv` (14/14 match); the scratch copy was deleted. The capability matrix was
  re-counted at 23 rows. Content commit `165d261` on
  `task/T-035-design-reference-adoption` passed CI run
  [45692372567](https://github.com/eizmadhoun2019/M_Academy/actions/runs/45692372567).
- **Approved by:** Owner delivered and approved the package (D-045); merge to `main` pending owner
  approval.
- **References:** T-035, D-044/D-045, `docs/plan.md` §4, `docs/ui/design-system.md`,
  `docs/ui/design-reference.md`, `docs/ui/wireframes.md`.

### [2026-11-25] — T-025 approved, merged and closed

- **Type:** Milestone
- **Status:** Merged
- **Summary:** The project owner approved the H1.5 direction, D-043/D-044 and the T-025
  corrections, and authorized the merge under the governance rules. The capability-preservation
  matrix was completed to **23 rows** by restoring company administration (users, invitations,
  departments, roles and settings, from G5/REQ-21/REQ-25); no capability was removed or weakened.
  Final branch head `e19f76c` passed CI run 45686699559. T-025 was merged into `main` with merge
  commit `b592498`, which passed CI run 45687216183. The repository had no open pull request and no
  review threads or commit comments for this branch, so no review remark remains unresolved.
- **Impact:** T-025 is `[x]` on `main`. T-026 CP1 is the next eligible checkpoint and has **not**
  started. T-033 remains `[ ]` and may start only after T-026 is `[x]`, in parallel with T-027/T-028;
  the earlier “after T-026 CP1” note was corrected because CP1 alone does not satisfy its
  dependency. D-001, D-005 and D-009 remain **Open** with no closure evidence or owner decision, and
  D-010 remains deferred to H2. No application code, template, migration, dependency or
  infrastructure changed.
- **Evidence:** Source head `e19f76c`; workflow `CI` run
  https://github.com/eizmadhoun2019/M_Academy/actions/runs/45686699559 — `completed` / `success`.
  Merge commit `b592498`; workflow `CI` run
  https://github.com/eizmadhoun2019/M_Academy/actions/runs/45687216183 — `completed` / `success`.
  `python scripts/check_docs.py` → G9 passed (38 markdown files); capability matrix = 23 rows;
  `git diff --check` clean.
- **Approved by:** Project owner (2026-11-25): architecture, D-043/D-044 and merge to `main`.
- **References:** T-025, D-043, D-044, `docs/traceability.md` §4.1, `docs/plan.md` §4 T-025/T-033,
  `STATUS.md`, `RULES.md` task lifecycle and definition of done.
- **Corrects:** The “T-025 remains `[~]`” and “T-033 may run after T-026 CP1” statements in the
  previous entries and the prior `STATUS.md` next action.

### [2026-11-25] — T-025 H1.5 amendment evidence (content commit and CI)

- **Type:** Verification
- **Status:** Verified
- **Summary:** Recorded the content commit and CI run for the H1.5 architecture amendment. The
  documentation content is `e2e9c1b` on `task/T-025-docs-consolidation`; GitHub Actions workflow
  `CI` completed with **success** for that exact SHA. This evidence-only entry updates the
  citations without changing the content commit or embedding its own hash in it.
- **Impact:** `STATUS.md` now cites `e2e9c1b` and run 45684270950. T-025 remains `[~]` because owner
  review/approval is still required; CI is no longer an open evidence gap.
- **Evidence:** Commit `e2e9c1b`; `CI` run
  https://github.com/eizmadhoun2019/M_Academy/actions/runs/45684270950 — `completed` / `success`;
  `python scripts/check_docs.py` → G9 passed (38 markdown files).
- **Approved by:** Project owner (delegation for this T-025 correction).
- **References:** T-025, the amendment entry below, `STATUS.md`, `RULES.md` evidence policy.
- **Corrects:** The “CI pending” evidence line in the amendment entry below.

### [2026-11-25] — T-025 H1.5 architecture simplification amendment

- **Type:** Decision | Change
- **Status:** Implemented (CI pending)
- **Summary:** Corrected the H1.5 target to **one company membership per account**: `Membership`
  carries `UNIQUE (user_id)`, services and tests enforce it, invitations reject a second company
  and there is no company chooser, switcher, selection API or setting. Platform administrators are
  handled by `PlatformRoleAssignment` with no synthetic company; platform screens take an explicit
  company id under platform permission and audit. The account/membership/company/authority
  separation, tenant isolation and all earlier training capabilities are preserved. Added D-043 and
  D-044, amended D-032/D-007/D-008/D-030, corrected ADR-024/025/026 and the ADR index, and added
  the capability-preservation matrix to `docs/traceability.md`. Mobile First (390/768/1440, test
  from 320) and the binding visual-reference/visual-regression gate are now mandatory. Recorded the
  evidence policy that avoids a self-referential commit id. Added a historical banner to the
  untracked `INSTALLATION_AR.md` without deleting owner content; UX archives remain untracked.
- **Impact:** The documentation set no longer promises multi-membership UX or client-selected
  company context. T-026…T-034, GATE-1 and G8/G10 carry the new constraints and the capability
  matrix; T-030 keeps platform administration membership-free. T-025 remains `[~]` until CI is
  observed and the owner approves; `main` is untouched.
- **Evidence:** Content commit carrying this entry on `task/T-025-docs-consolidation`; its SHA and
  the GitHub Actions run are recorded in the immediately following evidence entry, per the
  `RULES.md` evidence policy. `python scripts/check_docs.py` → G9 passed (38 markdown files);
  cross-document grep for chooser/switcher/multi-membership/old viewport/font references was clean
  apart from explicit prohibitions and historical text. No application tests were run because no
  code changed.
- **Approved by:** Project owner (H1.5 correction prompt, 2026-11-25).
- **References:** T-025, D-043, D-044, D-032/D-007/D-008/D-030, ADR-024…ADR-026,
  `docs/traceability.md` §4.1, `docs/plan.md` T-025…T-034/GATE-1.

### [2026-11-25] — T-025 documentation and governance consolidation

- **Type:** Change
- **Status:** Implemented
- **Summary:** Rebuilt the project's governance set around charter 2.4 and H1.5: standalone-first
  architecture with Hub dormant, first-class organizations/memberships/departments, local
  accounts with Django Auth, dynamic scoped RBAC, public site on `/` and application under
  `/academy/`, per-company settings/time zone/mail, tenant-aware jobs and reports, migration and
  operations plans. Added `docs/plan.md` (T-025…T-034, checkpoints, acceptance criteria, GATE-1),
  `docs/traceability.md` (G1–G12, REQ-01…REQ-28, sources of truth), `docs/security.md`,
  `docs/access-control.md`, `docs/migration-h1.5.md`, ADR-023…ADR-028 and the permission-change
  skill. Marked T-023/T-024 superseded rather than deleting them; no application code, template,
  migration, API contract, Hub activation, infrastructure or dependency was changed.
- **Impact:** A new agent can start from `README.md` → `RULES.md` → `STATUS.md` → `docs/plan.md`
  and continue with «كمل». Implementation begins at T-026 only after owner approval; current
  single-company/Hub code is explicitly documented as the pre-H1.5 state.
- **Evidence:** Branch `task/T-025-docs-consolidation`, commit `96f78d2`; `python
  scripts/check_docs.py` → G9 passed (38 markdown files); cross-document review covered
  scope/tenancy/permissions/API/UI/tasks; no application tests were run because no code changed.
- **Approved by:** Project owner (delegation in the consolidation prompt, 2026-11-25).
- **References:** T-025, D-031…D-042, ADR-023…ADR-028, `docs/plan.md`, `STATUS.md`.

### [2026-11-25] — T-022 reports and CSV export

- **Type:** Milestone
- **Status:** Implemented
- **Summary:** `academy/reports/selectors.py` now owns every definition in `docs/reports.md`:
  `summary()` groups enrollments by course or by department from one annotated query, `overdue()`
  returns the active rows past `due_at` with `days_overdue` and `progress_percent`, and
  `completion()` adds the pinned version and the `CompletionRecord` method. The §6 scope is
  applied as a queryset condition (granted departments plus `owner_department_ref IS NULL`), and a
  `department_ref` or `course` filter naming something outside it raises `403 forbidden` rather
  than returning an empty page, so a manager learns the boundary instead of reading a zero. The
  window is `[from, to)` in UTC on the date §1 names per endpoint, and `from > to` is the new
  `400 invalid_range` code. `academy/reports/csv_export.py` writes the §5 file: UTF-8 BOM, CRLF,
  snake_case header in the requested order, ISO-8601 UTC timestamps, one-decimal numbers,
  empty cells for null, and a preceding `'` for any cell that starts with `= + - @`, tab or
  carriage return; `manage/reports/export.csv` streams it, writes one `report.exported`
  `AuditEvent` with the filter set and no learner identifier, and keeps the `5/hour` throttle
  scope. `ACADEMY_CURSOR_PAGE_SIZE` (default 50) backs the opt-in cursor paging of the completion
  list, and `docs/reports.md` §1/§2/§5 now state the two readings the code had to choose: the
  average time is taken over the completed rows of the same filtered set, and an absent window
  bound becomes the literal `all` in the filename.
- **Impact:** REQ-12 is implemented end to end on the definitions T-023's dashboard will reuse.
  The department boundary of reports differs deliberately from content management (general
  courses stay visible to a department-scoped report reader), which the selector comments and
  §6 of the document record.
- **Evidence:** 30 new tests in `tests/test_reports.py` — every column of §2–§5, totals summed
  instead of averaged, the null average, the window on `created_at`/`completed_at`/`due_at`,
  the general-course bucket and the organization-name label, the directory fallback, the
  fixed query count, cross-department `403`, `invalid_range`, cursor paging, the CSV
  formula fixture (`=1+1`, `@SUM`, `-2+3`, tab), the BOM and CRLF bytes, the filename, the
  `Cache-Control` header and the audit row; 590 tests at merge; ruff, format, mypy,
  `makemigrations --check`, OpenAPI validation, G3/G7/G9 green locally; CI run `45663543806`
  green on `81d422f`, fast-forwarded to `main` as `81d422f`.
- **Approved by:** Project owner («تمام كمل 22» instruction of 2026-11-25).
- **References:** T-022, REQ-12, `docs/reports.md`, `docs/api.md` §6/§11,
  `docs/configuration.md` §5.

### [2026-11-25] — T-021 notifications, reminders and the escalation digest

- **Type:** Milestone
- **Status:** Implemented
- **Summary:** `academy/notifications/` now owns the seven messages of
  `docs/notifications.md`: one catalogue renders every ar/en subject and body from the ids in the
  dedupe key, so copy is drawn at send time and a message that waited in the queue still names
  the course as it is. `service.queue()` writes the `NotificationLog` row and enqueues the send
  `on_commit`, `service.deliver()` is the only sender and the row's status is the gate: a
  duplicate key, a second worker, a retried task or the repair sweep all find the row already
  `sent` or `pending` and stop, and a message that became unnecessary is marked `skipped` with
  its code (`recipient_inactive`, `already_completed`, `enrollment_cancelled`,
  `context_missing`, `directory_unavailable`). The enrollment events subscribe to the existing
  domain signals (`N-1`, `N-2`, `N-3`); `academy/notifications/reminders.py` evaluates the
  business-date offsets −3 / 0 / +1 (`N-4`…`N-6`) once a day, refuses to remind an enrollment
  that is acknowledged, completed or cancelled, and escalates at due+3 (`N-7`) to the human
  assigner or else the Hub manager, skipping the learner when they are their own manager. The
  `ReminderLog` insert is the escalation's gate and `send_digest` groups the owing rows by
  manager and due date, so several escalations of one day leave in one digest; the bare
  `academy.escalations.digest` task re-sends every batch still owed, which repairs a run that
  died between evaluation and delivery. Delivery goes through the `NotifyAdapter` only. Beat
  gained the sweep (15 min) and the two 08:00-business-time entries, converted to the UTC hour at
  start-up, and `ACADEMY_ORGANIZATION_NAME` names the sender (default `مشيد`).
- **Impact:** REQ-10 and REQ-11 are implemented end to end with frozen-time evidence, so T-022
  reports and T-023's screens can rely on a delivery trail that cannot send twice. Removing the
  deprecated `queue=` task attribute in favour of the existing `CELERY_TASK_ROUTES` also made the
  first test that touches a task finalize the Celery app without a deprecation error, which
  exposed a wall-clock race in two T-020 progress tests; their clock is now pinned per test, so
  the documented numbers are asserted exactly.
- **Evidence:** 32 new tests in `tests/test_notifications.py` and `tests/test_reminders.py` (the
  catalogue and its length limits, idempotency across retries and workers, every suppression
  code, an unreachable directory, both enrollment events, the full date matrix with frozen
  time, one digest per manager-day, the bare-task repair, the beat entries); 560 tests at merge;
  ruff, format, mypy, `makemigrations --check`, OpenAPI validation, G3/G7/G9 green locally; CI
  run `45652976135` green on `4aafd75`, fast-forwarded to `main` as `4aafd75`.
- **Approved by:** Project owner («كمل» instruction of 2026-11-25).
- **References:** T-021, D-002, `docs/notifications.md`, `docs/background-jobs.md` §1/§4,
  `docs/configuration.md` §1.

### [2026-11-25] — T-017 content services and API

- **Type:** Milestone
- **Status:** Implemented
- **Summary:** Courses, versions, sections and lessons now go through
  `academy/content/service.py`: every write checks `academy.manage_content`, then the course's
  department scope, and treats a general course (`owner_department_ref` NULL, D-013) as
  administrator-only; an out-of-scope object answers 404 like a missing one. Creating a course
  opens draft version 1, cloning copies the whole tree into the next draft number and refuses a
  second open draft (409 `draft_exists`), publishing validates the draft and either returns every
  reason (422 `publish_invalid` with `{code, section_id?, lesson_id?}` items) or archives the
  previous published version and stamps the new one atomically, and archive, discard, reorder and
  lesson edits each append their audit row in the same transaction. Published versions stay
  immutable: the services answer 409 `version_published` before the trigger would. The
  `manage/courses/`, `manage/versions/`, `manage/sections/` and `manage/lessons/` routes expose
  the inventory of `docs/api.md` §4, and `access.granted()` lets a department-scoped grant pass
  the class-level permission while the service still enforces the object's department.
- **Impact:** REQ-06 is implemented end to end: authoring, cloning, reordering and publishing
  are covered by one decision path with audit evidence, and T-018 can attach media to the same
  lesson rows.
- **Evidence:** 21 new tests in `tests/test_content.py` (service scope matrix, clone numbering and
  draft guard, every publish reason, immutable published versions, archive/discard, reorder
  mismatch, owner-department lock, API create/list/patch/404/403/422 and section-lesson round
  trip); ruff, format, mypy, `makemigrations --check`, OpenAPI validation and G7/G9 green
  locally; CI run `45585336949` green on `8b5ecc1`, fast-forwarded to `main` as `6cc59c9` with
  CI run `45586286539` green.
- **Approved by:** Project owner («كمل» instruction of 2026-11-25).
- **References:** T-017, D-013, D-014, D-016, `docs/domain-model.md` §2.1–§2.4, `docs/api.md`
  §4/§8.

### [2026-11-25] — T-016 permission grants

- **Type:** Milestone
- **Status:** Implemented
- **Summary:** `PermissionGrant` (migration `0007`) stores one live capability per user and
  scope, with the documented shape checks, a partial unique index that treats organization
  scope as one value (`nulls_distinct=False`) and a revocation that must name its actor.
  Grants are read on every request by the access middleware and passed into the authorization
  layer, whose fingerprint-keyed cache already includes them; a blocked account skips the read
  because its effective capability is empty anyway. The grant service appends `grant.created`
  and `grant.revoked` audit rows in the caller's transaction, refuses duplicate live grants
  with 409, and protects the final active administrator with 409 `last_admin`. `manage/grants/`
  lists (tenant-scoped filters and pagination), creates (Idempotency-Key replay within 24 h,
  conflict on a changed body) and revokes; `provision_admin` is the one guarded way to create
  the first administrator, and a suspension keeps every grant row while removing capability.
- **Impact:** H1 `grants_only` is now operable end to end: a Hub role alone gives nothing, a
  grant gives exactly its scope, and `role_plus_grants` still unions role defaults with grants.
- **Evidence:** 22 new tests in `tests/test_grants.py` (service matrix, both modes, last admin,
  expiry, suspension retention, API list/create/revoke, idempotency, tenant isolation,
  provision command), plus the tenant-isolation suite over the new table; ruff, format, mypy,
  `makemigrations --check`, OpenAPI validation and G7/G9 green locally; CI run `45576806853`
  green on `1cc1467`, fast-forwarded to `main` as `17fe415` with CI run `45577563757` green.
- **Approved by:** Project owner («كمل» instruction of 2026-11-25).
- **References:** T-016, D-027, D-028, `docs/domain-model.md` §2.14, `docs/api.md` §2/§7.

### [2026-11-25] — T-015 Hub HTTP integration

- **Type:** Milestone
- **Status:** Implemented
- **Summary:** Academy now accepts the Hub proxy's signed identity in `hub` mode: the configured
  verifier proves the HMAC signature, and the request path enforces issuer, audience, lifetime,
  clock skew, the signed method and target, the 24-byte single-use nonce and this deployment's
  organization UUID. A rejected assertion is treated exactly like a missing one, so the API
  answers 401 and a valid inactive member answers 403 `account_inactive`. Membership webhooks
  arrive at `/internal/hub/webhooks/` with the separate webhook key ring and audience
  `masheed-academy:webhooks`, a five-minute window and `body_sha256` binding; a durable
  `HubWebhookEvent` receipt (migration `0006`) makes a repeat with a fresh nonce a duplicate
  and a reused event id with different bytes a conflict, and the receipt commits with the
  directory-cache invalidation and the deactivation hook. The Hub service transports are a
  `host_hub` package: an stdlib HTTP client with the documented 0.5 s connect/1 s read
  timeouts, one retry with backoff, no redirects and a shared 3-failure/30-second circuit, a
  directory adapter that caches each tenant lookup for 60 s under an invalidation generation,
  and a notifier that carries `Idempotency-Key` on every write. A loopback fake speaks the
  whole §3 API over real HTTP and signs identity and webhook assertions for tests.
- **Impact:** The `ACADEMY_HUB_*` settings are documented in `docs/configuration.md` §1 and
  `.env.example`; the production profile refuses to start without the Hub origin, service URL,
  token and both key rings, and rejects keys shorter than 32 bytes. `docs/domain-model.md`
  gains §2.16 for the receipt table (the previous §2.16 becomes §2.17).
- **Evidence:** Branch `task/T-015-hub-http`; 399 tests including `tests/test_hub_identity.py`
  (valid, tampered, expired, wrong audience, wrong tenant, misrouted, replayed, inactive),
  `tests/test_hub_webhooks.py` (duplicate, conflict, replay, bad signature, wrong tenant,
  malformed body, 405, 413, invalidation, deactivation hook) and
  `tests/contracts/test_hub_transports.py` (directory and notification contract over the fake,
  caching and invalidation, idempotency, unreachable Hub); ruff, format, mypy,
  `makemigrations --check`, OpenAPI validation and G7/G9 green locally; CI run `45572535250`
  green on `41d0dc0` (the first run `45572186106` failed G6 because the deploy check lacked the
  now-mandatory Hub settings, supplied in `41d0dc0`), fast-forwarded to `main` as `f4eea00`
  with CI run `45573329413` green.
- **Approved by:** Project owner («كمل» instruction of 2026-11-25).
- **References:** T-015, D-004, D-010, `docs/hub-contract.md` §1–§5.

### [2026-11-25] — T-014 sessions and auth lifecycle

- **Type:** Milestone
- **Status:** Implemented
- **Summary:** One request middleware now resolves the caller into a `Principal` — from a
  verified Hub claim set in `hub` mode, or from the standalone session that stores only the
  identity (`user_ref`, role, departments, active flag) and never a capability — and publishes
  the resolved `Access` on `request.academy_access` for the API and the pages alike. The
  answer is cached in Redis under a key that carries the authorization mode, the role and
  department fingerprint and the suspension flag, so a role change or a new suspension is
  visible on the very next request even with a warm cache. `AccessSuspension` (migration
  `0005`) adds one live suspension per user with a non-blank reason and a lift that must name
  its actor; a suspended or inactive member gets `access_suspended` or `account_inactive` from
  every API route and the X2 page from every `/academy/` page. The X1 sign-in form writes the
  local identity for `standalone` mode only, is disabled by `ACADEMY_DEVELOPMENT_LOGIN`, can
  preview an inactive membership, and is throttled at `10/min`; the DRF scopes of
  `docs/configuration.md` §6 are configured with the documented rates and keyed by the verified
  `user_ref`.
- **Impact:** `ACADEMY_ACCESS_MODE`, `ACADEMY_ORGANIZATION_ID`, `ACADEMY_DEVELOPMENT_LOGIN`
  and `ACADEMY_THROTTLES_ENABLED` are now read by the code and listed in
  `docs/configuration.md` §1. Middleware order puts the resolver after sessions and locale
  selection. Suspended grants are untouched, so lifting a suspension restores them (D-028).
- **Evidence:** Branch `task/T-014-sessions-auth`; 360 tests including `tests/test_sessions.py`
  (middleware, both access modes, suspension, role change, cache, sign-in/out, throttle, model
  constraints); ruff, format, mypy, `makemigrations --check`, OpenAPI validation and G7/G9 green
  locally; CI run `45567646962` green on `5baa76a` (the first run `45566819646` failed G1 on two lint findings, fixed in `5baa76a`), fast-forwarded to `main` as `cb1edda` with CI run `45568418999` green.
- **Approved by:** Project owner («كمل» instruction of 2026-11-25).
- **References:** T-014, D-026, D-027, D-028, `docs/configuration.md` §1/§6, `docs/domain-model.md` §2.15.

### [2026-11-22] — Rebuild from scratch with UPDS documentation baseline

- **Type:** Milestone
- **Status:** Approved
- **Summary:** The project restarts from a clean repository governed by UPDS 1.0.0-rc2.
  The seven core documents (README, RULES, STATUS, CHARTER, ARCHITECTURE, LOG, SKILLS)
  were created from the UPDS core templates and seeded with the Masheed_Academy
  requirements: charter scope and REQ-01…REQ-20 condensed from legacy charter 1.3;
  architecture decisions from the legacy design; open decisions D-001…D-009 consolidated;
  a fresh 24-task + gate plan in STATUS; performance targets moved to
  `docs/performance-profile.yaml`. Live requirement references (`hub-contract.md`,
  wireframes, email templates, visual-baseline PDF and renders) were carried into `docs/`.
- **Impact:** Establishes the authoritative documentation interface for the rebuild.
  The legacy repository and its history remain available as reference; none of its
  implementation state is claimed here until re-implemented and verified.
- **Evidence:** This documentation baseline (initial package creation).
- **Approved by:** Project owner
- **References:** UPDS package (external, not vendored) adoption guide section A; legacy LOG.md
  (history, kept in the legacy repository).

### [2026-11-22] — Documentation baseline adopted as starting state

- **Type:** Milestone
- **Status:** Proposed
- **Summary:** Initial UPDS project documentation created; project-specific facts remain
  to be confirmed as implementation starts (env values, exact pinned versions, CI details).
- **Impact:** Defines the documentation baseline for T-001 onward.
- **Evidence:** Initial repository/package creation.
- **Approved by:** Pending
- **References:** UPDS adoption checklist; STATUS.md → Next action (T-001).

### [2026-11-22] — Build specifications completed before T-001

- **Type:** Change
- **Status:** Implemented
- **Summary:** A readiness review of the baseline found four gaps that would have stalled
the build at the schema tasks: scattered/conflicting decision IDs, legacy `P0-/P1-` plan
IDs with no mapping, no field-level schema (and no specification of the anti-skip progress
algorithm), and no API inventory. All four are closed. New canonical documents:
`docs/decisions.md` (D-001…D-017 plus a mapping for the retired D-018…D-022 and four
CHARTER 2.0 collisions), `docs/traceability.md` (ID scheme, legacy→task map, CI gates
G1–G9, REQ→task evidence, sources of truth), `docs/domain-model.md` (entities with fields
and constraints, state machines, invariants, and the normative heartbeat/gating/completion
algorithm in §7), `docs/api.md` (endpoints, capabilities, error codes), and
`docs/adr/README.md` (ADR index and template). CHARTER 2.1 corrects decision IDs with no
scope change; ARCHITECTURE §5/§6 now defer to the canonical specs, §7 gains the audited
action list, §11 numbers ADR-001…ADR-013, §12 maps the plan to task IDs; RULES numbers the
CI gates and fixes the TODO example; STATUS and README point at the new documents;
SKILLS no longer points at unvendored UPDS files; wireframes and hub-contract use current
IDs and resolvable section references.
- **Impact:** Phase 0 tasks T-006…T-008 (schema) and T-011, T-016…T-022 (API) can now be
implemented from documents instead of design decisions made inside code. D-013…D-017 are
now tracked as Defaulted, and no task waits on an open decision.
- **Evidence:** New files committed as documentation; `grep -rn "P0-[0-9]\|P1-[0-9]"
--include=*.md .` returns no matches; every `D-NNN`, `§` and ADR reference resolves.
- **Approved by:** Project owner (requested and authorized this work).
- **References:** `docs/decisions.md`, `docs/traceability.md`, `docs/domain-model.md`,
  `docs/api.md`, ADR-012, ADR-013; next action T-001.

### [2026-11-22] — Rebuild moves to a new repository with an isolated stack

- **Type:** Decision
- **Status:** Approved
- **Summary:** The rebuild will live in its own repository, `M_Academy`, with its own
history and no dependency on the legacy repository, its images, volumes, database, cache,
credentials or containers. The legacy deployment keeps running unchanged and is
reference-only. The new stack is defined as compose project `m-academy` with its own
PostgreSQL, Redis, MinIO buckets, Celery broker, volumes and host ports. While checking the
host, the legacy stack was found to hold `8001` (web), `9000`/`9001` (MinIO) and `8026`
(MailHog); the previously documented `localhost:8001` was therefore wrong for a
side-by-side setup. New bindings were verified free and reserved: web `8101`, PostgreSQL
`5433`, Redis `6390`, MinIO `9100`/`9101`, MailHog `8126`/`1126`.
- **Impact:** README setup, STATUS T-001 acceptance and ARCHITECTURE §8 now reference the
isolated stack. Cookies are namespaced (`m_academy_sessionid`) because browsers scope
cookies by host, not port, and the legacy app runs on the same `localhost`. RULES gained
prohibitions on Docker commands that can reach other projects. CHARTER 2.2 records the
repository and environment constraints without changing product scope. Initial push is
gated on D-023 (repository visibility), because the baseline is internal material.
- **Evidence:** `docker ps`, `docker compose ls` and `netstat` checks recorded in
`docs/operations/environments.md` §3 (legacy `masheed-academy` running; candidate ports
free).
- **Approved by:** Project owner (requested the new repository and full isolation).
- **References:** `docs/operations/environments.md`, D-023, T-001, CHARTER 2.2, RULES.

### [2026-11-22] — Build-blocking gaps closed: configuration, jobs, copy, reports

- **Type:** Documentation
- **Status:** Done
- **Summary:** Four remaining specifications were written so no task has to invent a
number or a sentence: `docs/configuration.md` (core settings, data stores, upload policy,
HLS ladder 360p/720p with 6 s segments, pagination 25/100, throttle table, test-profile
overrides), `docs/background-jobs.md` (eight Celery tasks with queue, schedule, retry and
idempotency key, plus what is deliberately synchronous), `docs/notifications.md` (seven
message types with Arabic and English copy, dedupe keys, suppression and directory-outage
behaviour, built on the approved `docs/ui/emails/escalation-digest.html`), and
`docs/reports.md` (metric definitions, columns for all four report endpoints, UTF-8 BOM
CSV with formula neutralisation, scope rule, query budget).
- **Impact:** `docs/operations/environments.md` gained §8 service targets and alert
thresholds. T-018, T-021, T-022 and T-024 acceptance now cite these files. The defaults are
recorded once as D-024 (Defaulted, cheap to reverse). Traceability and README list the new
canonical files.
- **Evidence:** Every new file is linked from README and traceability; no value contradicts
`docs/performance-profile.yaml` (page size 25, RPO 24 h, RTO 4 h, 200 concurrent viewers)
or the `renditions` example in `docs/domain-model.md` §2.5.
- **Approved by:** Project owner («سدها»).
- **References:** D-024, T-018, T-021, T-022, T-024, `docs/ui/emails/`.

### [2026-11-22] — T-001: repository and isolated stack bootstrapped

- **Type:** Implementation
- **Status:** Implemented (evidence below). Not yet verified in CI: the first push is gated
  by D-023, so the workflow is committed but has not run on GitHub.
- **Summary:** The repository was initialised with its own history (`git init -b main`,
  `origin` = `M_Academy`) and the scaffold added on `task/T-001-scaffold`. Contents: pinned
  `pyproject.toml` (Django 5.2.19, DRF 3.18.3, drf-spectacular 0.30.0, psycopg 3.3.9,
  Celery 5.7.0, redis 8.1.0, boto3 1.44.9, django-storages 1.14.6, gunicorn 27.0.1, plus
  pinned dev tooling), `config` project with `settings/{base,dev,test,prod}.py`
  (`config.settings.prod` as named in `docs/hub-contract.md` §7), `/healthz` checking the
  database and the cache, namespaced cookies from `docs/configuration.md`, a multi-stage-free
  Dockerfile with ffmpeg/ffprobe, the isolated compose file (project `m-academy`, ports
  8101/5433/6390/9100/9101/8126/1126), `.env.example` with every documented variable, a
  generated untracked `.env`, Makefile, pre-commit, the three gate scripts and the nine-job
  CI workflow.
- **Evidence:** `docker compose -p m-academy up -d --build --wait web db redis mailhog worker
  beat` → six services healthy; `curl http://localhost:8101/healthz` → `200` with
  `{"database": true, "cache": true}`; `celery -A config inspect ping` → `pong`, 1 node;
  `ruff check` + `ruff format --check` clean (41 files); `mypy` clean (16 files);
  `makemigrations --check` → no changes; `migrate` applied; `spectacular --validate
  --fail-on-warn` → 0 warnings; `pytest` → 2 passed. Isolation: only `m-academy-*`
  containers started, volumes `m-academy_{media,pgdata,redisdata}` created, network
  `m-academy_default` created, and the legacy `masheed-academy-*` containers stayed `Up`
  untouched. `.env`, `.venv`, `.build.log` and `celerybeat-schedule` are ignored.
- **Blocked:** the object-storage service. `minio/minio` no longer resolves on Docker Hub,
  `ghcr.io/minio/minio` returns denied and `quay.io/minio/minio` returns 401, so
  `m-academy-minio-1` was not started and the bucket step of the isolation checklist is
  unverified. Raise as D-025 (owner decision) rather than substituting a provider silently.
- **Not yet active by design:** G3's 85% threshold and G7's tenant half activate with T-003;
  G8 activates when `tests/e2e/` exists (T-023). Each script prints that state instead of
  reporting a pass.
- **References:** T-001, D-023, D-025, `docs/operations/environments.md` §7,
  `docs/configuration.md`, `.github/workflows/ci.yml`.

### [2026-11-22] — D-023 confirmed: repository stays public, history published

- **Type:** Decision
- **Status:** Approved
- **Summary:** The owner confirmed that `M_Academy` stays **public** and authorized
  publishing. The remote held only GitHub's placeholder `Initial commit` (`README.md` =
  `# M_Academy`) and shared no history with the local repository, so both local branches were
  rebased onto `origin/main` (`git rebase origin/main`, ours kept for `README.md`) and `main`
  was pushed normally — no force-push, no commit destroyed. The project `README.md` supersedes
  the placeholder one.
- **Impact:** The documentation baseline and the T-001 scaffold are on GitHub and the nine CI
  jobs run there. Everything pushed is public from now on, so no secret may enter a tracked
  file and future internal material must be assumed world-readable.
- **Evidence:** `git rebase origin/main -X theirs` on `main` left a tree identical to the
  pre-rebase baseline; the same on `task/T-001-scaffold` left a tree identical to the
  pre-rebase T-001 commit (`git diff --stat 24e7b71` empty). Push and CI receipts are in the
  checkpoint report.
- **Approved by:** Project owner (2026-11-22): stays public, proceed as is; path = rebase
  then normal push.
- **References:** D-023, T-001, `docs/operations/environments.md` §1.

### [2026-11-22] — Record-keeping defects corrected (no earlier entry edited)

- **Type:** Change
- **Status:** Implemented
- **Summary:** A consistency review of the documentation found four defects in the record:
  two LOG entries use a type or status outside the lists in RULES, `CHARTER.md` §10 and
  `docs/configuration.md` §7 attributed retention to the wrong decision, STATUS omitted D-025
  from its open list while calling it a blocker elsewhere, and `docs/skills/closing.md` cited a
  sync table that did not exist.
- **Impact:** Nothing was deleted or rewritten (append-only). The two superseded entries keep
  their text and are corrected here; retention is D-003; `RULES.md` now carries the document
  sync table, the definition of done, the commit-message format, the UI rules and the
  dependency policy that other documents were already referring to; `ARCHITECTURE.md` §7 gained
  an explicit tenant-isolation statement; `docs/traceability.md` §3 gained the gate activation
  column that records which gates are live at each task.
- **Evidence:** `python scripts/check_docs.py` passes; the corrected references resolve to
  `docs/decisions.md` rows D-003 and D-008; every rule referenced by `docs/skills/closing.md`
  now exists under that name.
- **Corrects:** `[2026-11-22] Documentation baseline adopted as starting state` (Status
  `Proposed`, `Approved by: Pending`) and `[2026-11-22] Build-blocking gaps closed:
  configuration, jobs, copy, reports` (Type `Documentation`, Status `Done`).
- **Approved by:** Project owner (2026-11-22: «أصلح كل ما سبق»).
- **References:** RULES (LOG status values, Document sync table, Definition of done, Commit
  messages, UI and frontend rules, Dependencies), CHARTER §10, `docs/configuration.md` §7,
  `docs/decisions.md` D-003, `docs/traceability.md` §3, `docs/skills/closing.md`.

### [2026-11-23] — G6: the image's setuptools finding (CVE-2025-47273)

- **Type:** Fix
- **Status:** Implemented
- **Summary:** G6's image scan was the only red gate. The report showed a single
  finding — setuptools 70.3.0 in `python:3.12-slim`, CVE-2025-47273, fixed in 78.1.1 — with
  Debian at zero and every other Python package clean. Upgrading setuptools inside the image
  did not clear it, and nothing in the app or its runtime dependencies imports either
  setuptools or pip, so the package and its leftovers are now removed from the image after
  the dependency install. A build-time assertion fails the image build if a later change
  brings it back, so the finding cannot reappear silently.
- **Impact:** The production and development images no longer ship build tooling. `pip install`
  still works during the build because it uses build isolation. The gate keeps its severity,
  `--ignore-unfixed` and exit-code rules: nothing was waived or narrowed.
- **Evidence:** The image rebuilt from the same commit with `--no-cache --pull` contains no
  `setuptools`, `pkg_resources` or `_distutils_hack` path outside pip's own vendored copy, and
  `pip list` reports `pip==26.3` only; `pip uninstall` left no dist-info behind. All 83
  Python packages in that image return zero advisories from the OSV API, and the repository
  contains no secret patterns the scanner looks for.
- **Approved by:** Project owner (2026-11-23): fix G6 before continuing.
- **References:** T-001, `docs/traceability.md` §3 G6, `Dockerfile`.

### [2026-11-23] — G6 verified green: the finding came from pip's bundled SBOM

- **Type:** Fix
- **Status:** Verified
- **Summary:** The remaining red gate was not the image's own content. CI runs each step as
  `bash -e`, so the failing trivy pipeline ended the step before any diagnostics ran; once
  the exit code was captured and re-raised, the step reported `setuptools` /
  `CVE-2025-47273` while the image contained no such package and the build assertion proved
  it could not be imported. The step then named the matching files: the only declaration of
  setuptools 70.3.0 was `pip/_vendor/bom.cdx.json`, the bill of materials that ships inside
  pip and that trivy reads as a source of truth (hence its own warning about third-party
  SBOMs). The runtime image needs no installer, so pip and setuptools are both removed after
  the dependency install; the build fails if either is importable again.
- **Impact:** The gate keeps its severity, `--ignore-unfixed` and exit-code rules — nothing was
  waived, narrowed or silenced, and no exception record was needed. A failing scan now explains
  itself in a run annotation that anyone can read without an account.
- **Evidence:** CI run `45138282623` on `main` (commit `076af2d`): ten jobs, nine success, one
  skipped by design (g8-e2e, guard), **G6 security green**; `python scripts/check_docs.py`
  passes.
- **Approved by:** Project owner (2026-11-23): «اصلح كل ما سبق وبعدها نعودلحسم مشكلتنا ci:g6».
- **References:** T-001, `docs/traceability.md` §3 G6, `Dockerfile`, `.github/workflows/ci.yml`.

### [2026-11-23] — T-002: settings profiles, Celery queues, JSON logging, i18n

- **Type:** Feature
- **Status:** Implemented
- **Summary:** The Celery app now has the queue topology its catalogue assumes: `default`,
  `media` and `notifications` are declared explicitly, `academy.media.*` routes to `media`,
  `academy.notifications.*` and `academy.escalations.*` to `notifications`, and anything else —
  including a misnamed task — to `default`, with implicit queue creation off so a typo cannot
  open a queue no worker reads. The beat schedule stays with the tasks it names
  (`docs/background-jobs.md` §4), because scheduling a task that does not exist yet would only
  fill queues with unroutable messages. Logging is one JSON object per line
  (`config/logging.py`) with a request id that `RequestIdMiddleware` takes from an
  `X-Request-ID` header only when it is short and safe, generates otherwise, and echoes back.
  `LocaleMiddleware` is installed in Django's required order, the default language `ar` is
  validated against the supported list, and the language cookie is `django_language`.
- **Impact:** Every process logs machine-readable lines with a traceable request id; a task name
  is routed by code rather than by whoever typed the worker command. No new environment
  variable was introduced, so `docs/configuration.md` §1–§9 is unchanged; its new §10 documents
  the log fields and the header.
- **Evidence:** `tests/test_settings.py` (26 tests overall in the suite) covers the routing of
  every documented task name, the default-queue fallback, the declared queue set, `ping`
  returning `pong`, a real publish through this project's Redis broker landing on `default`
  (probe on a spare database so the development worker cannot consume it first), the JSON
  fields, request-id validation and echo, the Arabic default, English availability, locale
  middleware order, the cookie switching the active language, and the production profile
  refusing a missing `ACADEMY_ALLOWED_HOSTS` or a short `DJANGO_SECRET_KEY` while loading with
  the required values. Locally `ruff check`, `ruff format --check`, `mypy .` and `pytest -q`
  pass; `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «كمل» after G6 went green.
- **References:** T-002, `docs/configuration.md` §10, `docs/background-jobs.md` §1–§4,
  `docs/operations/environments.md` §4, `config/settings/base.py`, `config/celery.py`.

### [2026-11-23] — T-002 merged to main

- **Type:** Feature
- **Status:** Merged
- **Summary:** The owner merged `task/T-002-settings` into `main` (fast-forward, no rewrite) at
  the owner's instruction «ادمج», so the queue routes, the JSON log format and the locale
  middleware are now part of the mainline rather than a branch.
- **Impact:** `main` carries the settings work; the status row moved from review to done.
- **Evidence:** `main` = `8168477`; CI run `45141974756` green on that exact commit (g1–g7 and
  g9 pass, g8-e2e skipped by its guard); `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «ادمج ثم كمل».
- **References:** T-002, `STATUS.md`, `config/settings/base.py`.

### [2026-11-23] — T-003: academy skeleton (tenant base model, adapter loader, exceptions)

- **Type:** Feature
- **Status:** Implemented
- **Summary:** The `academy` package now exists as a Django app with the three pieces every
  later task builds on. `TenantModel` (abstract) carries the documented shared columns —
  UUID primary key generated in Python, a plain `organization_id` UUID (never a foreign key,
  because the organization lives in the Hub), and the two timestamps — plus a `for_org`
  manager that refuses anything that is not an organization UUID, so an unscoped read is a
  failing test rather than a global query. `academy.adapters.loader` resolves each host seam
  from an `ACADEMY_ADAPTER_*` `module:Class` value, caches it, and raises on an unknown,
  unset, malformed or non-class path instead of substituting a default. `academy.exceptions`
  defines the base error with the stable wire code and the four shapes services will raise
  (validation, not found, forbidden, conflict; adapters add "unavailable").
- **Impact:** Gate G7 is now real work: `academy/` exists, so the import boundary inspects
  every module, and `tests/test_import_boundary.py` runs the same script CI runs and proves it
  fails on a planted host import — a green gate can no longer mean "nothing was checked".
  Four new environment variables are documented in `docs/configuration.md` §11 and listed in
  `.env.example`; empty values are valid and mean "not configured".
- **Evidence:** `tests/test_tenant_model.py` (abstract columns, Python-side UUID, default
  manager, `for_org` returns only its organization while the unscoped manager still sees every
  row, `for_org` rejects `None`/str/int), `tests/test_adapter_loader.py` (resolution, caching,
  reset, unconfigured seam per name, unknown seam, five malformed configurations),
  `tests/test_import_boundary.py` (gate active, passes on the tree, detects a planted
  violation). Locally: 47 tests pass, `ruff check`, `ruff format --check`, `mypy .` and
  `makemigrations --check --dry-run` clean; `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «ادمج ثم كمل ثم نظف جذر المشروع».
- **References:** T-003, `docs/domain-model.md` §1.1,
  `ARCHITECTURE.md` §4,
  `docs/configuration.md` §11, `docs/traceability.md` §3 G7, `academy/`.

### [2026-11-23] — T-003 merged to main

- **Type:** Feature
- **Status:** Merged
- **Summary:** The owner merged `task/T-003-academy-skeleton` into `main` (fast-forward, no
  rewrite) on the standing instruction «ادمج ثم كمل», so the tenant base model, the adapter
  loader and the domain exceptions are mainline rather than a branch.
- **Impact:** `main` carries the T-003 skeleton; the status row moved from review to done.
- **Evidence:** `main` = `3b7d450`; CI run `45154163445` green on that exact commit
  (g1–g7 and g9 pass, g8-e2e skipped by its guard); `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «ادمج ثم كمل».
- **References:** T-003, `STATUS.md`, `academy/models/base.py`, `academy/adapters/loader.py`.

### [2026-11-23] — T-004: the four host seams, their stubs and their contract suites

- **Type:** Feature
- **Status:** Implemented
- **Summary:** The host boundary is now specified as code instead of prose. `academy.adapters`
  holds four `Protocol`s — `IdentityAdapter.verify(token, keys)`, the six directory reads of
  `OrganizationAdapter`, `NotifyAdapter.send_mail/record_activity`, and
  `StorageAdapter.presign_put/presign_get/stat/delete_prefix` — with stdlib-only value types
  (`Department`, `DirectoryUser`, `Role`, `MailMessage`, `MailReceipt`, `ActivityEvent`,
  `ObjectStat`). Two rules are enforced at the seam rather than left to each caller: storage
  keys must sit under `org/<organization_id>/media/` with no traversal and deletion only at a
  directory boundary, and a notification carries an opaque `recipient_ref` with channels from
  `docs/notifications.md` and a Hub-origin-relative link. `host_stub/` implements all four for
  development and tests: HMAC-SHA256 identity with a token signer, an in-memory directory that
  expands department descendants and hides inactive memberships, a recording transport that
  deduplicates by idempotency key and event id (conflicting reuse raises `Conflict`), and an
  in-memory bucket with `put`/`get` helpers. The development and test profiles now default the
  empty `ACADEMY_ADAPTER_*` values to those stubs, so a fresh clone runs with no Hub and no
  bucket while production still fails loudly on the first call.
- **Impact:** REQ-02's evidence now exists: one contract suite per seam under `tests/contracts/`
  (adding an implementation to `IMPLEMENTATIONS` runs the whole suite against it), plus a
  wiring test that loads every seam through `load_adapter` in the test profile and checks the
  instance against its `Protocol`. T-015's Hub transports and T-018's bucket implementation
  plug in without touching callers. `docs/configuration.md` §11 records the stub defaults and
  the acceptance rule.
- **Evidence:** `pytest -q` → 123 passed (76 new); `ruff check`, `ruff format --check`, `mypy .`
  and `makemigrations --check --dry-run` clean; `python scripts/check_docs.py` passes. The
  suites cover signature, key-ring rotation, tampering, malformed tokens, unknown organization
  isolation, descendant membership, the 50-reference batch cap, idempotent mail and activity
  delivery, conflicting key reuse, presign lifetime, key traversal and prefix-delete scope.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-004, REQ-02, `ARCHITECTURE.md` §4/§6, `docs/configuration.md` §11,
  `docs/hub-contract.md` §2–§3, `docs/notifications.md` §1, `academy/adapters/`, `host_stub/`.

### [2026-11-23] — T-004 merged to main

- **Type:** Feature
- **Status:** Merged
- **Summary:** The owner merged `task/T-004-adapters` into `main` (fast-forward, no rewrite) on
  the standing instruction «كمل», so the four host-seam Protocols, the development stubs and
  their contract suites are mainline.
- **Impact:** `main` carries the adapters; T-005 can build on them and T-015/T-018 have their
  acceptance suites in place.
- **Evidence:** `main` = `928e7da`; CI run `45159847845` green on that exact commit (g1–g7 and
  g9 pass, g8-e2e skipped by its guard); `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-004, REQ-02, `academy/adapters/`, `host_stub/`, `tests/contracts/`.

### [2026-11-23] — T-005: domain events dispatched only after commit

- **Type:** Feature
- **Status:** Implemented
- **Summary:** `academy.events` is the write path's event vocabulary. A service builds a event
  with `emit_on_commit(name, organization_id=…, actor_ref=…, payload=…)` inside its transaction;
  the event is queued through `transaction.on_commit`, so it fires once the outermost
  transaction commits and never at all when that transaction rolls back. The envelope
  (`DomainEvent`) is frozen, carries a generated `event_id` and a UTC `occurred_at`, and its
  payload is validated as JSON-serializable because the same shape is the Celery argument.
  Handlers subscribe by name (`subscribe`/`unsubscribe`/`handlers_for`), are called in
  subscription order through one module-level receiver, and a handler that raises is logged
  with the event name and id while the remaining handlers still run — a committed fact cannot
  be undone by a broken listener, and a post-commit failure must not surface as a failed write.
  Task-enqueueing handlers stay with the tasks they enqueue (T-018, T-021), so nothing schedules
  a task that does not exist yet.
- **Impact:** REQ-04's event half has its evidence; the service skill's step 4
  (`emit_on_commit`) is now executable code. Audit immutability (the other half of REQ-04) is
  T-012.
- **Evidence:** `tests/test_events.py` (22 tests) proves the event waits for the outermost
  commit, a rollback dispatches nothing, an event outside a transaction is dispatched
  immediately, every subscriber receives it in order, unrelated names are not called,
  unsubscribing stops delivery, a failing handler is logged without blocking the next, a
  handler may emit a follow-up event, the envelope is frozen with an immutable payload, and the
  name/actor/organization/payload/timestamp validations hold. `pytest -q` → 145 passed;
  `ruff check`, `ruff format --check`, `mypy .` and `makemigrations --check --dry-run` clean;
  G7 and G9 pass.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-005, REQ-04, ADR-007, `docs/skills/service.md` step 4, `ARCHITECTURE.md` §4,
  `academy/events/`.

### [2026-11-23] — T-005 merged to main

- **Type:** Feature
- **Status:** Merged
- **Summary:** The owner merged `task/T-005-events` into `main` (fast-forward, no rewrite) on
  the standing instruction «كمل», so the on-commit emitter and the handler registry are
  mainline.
- **Impact:** Services can emit events from inside their transactions; T-018 and T-021 add their
  task-enqueueing handlers against a stable emitter.
- **Evidence:** `main` = `0204cac`; CI run `45162780071` green on that exact commit (g1–g7 and
  g9 pass, g8-e2e skipped by its guard); `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-005, REQ-04, ADR-007, `academy/events/`.

### [2026-11-23] — T-006: catalog schema (Course, CourseVersion, Section, Lesson, MediaAsset)

- **Type:** Feature
- **Status:** Implemented
- **Summary:** The catalog of `docs/domain-model.md` §2.1–§2.5 now exists as a migration. Every
  entity is a `TenantModel`; the documented rules live in the database rather than in the
  promise of a future service: status enums with `CheckConstraint`s, non-blank titles,
  positive positions, `required_watch_percent` between 50 and 100, the `pdf`-needs-a-body rule,
  `UNIQUE(course, version_number)`, the partial unique index that allows at most one
  `published` version per course (with `published_at`/`published_by_ref` required by a check),
  the partial `(organization_id) WHERE status='published'` index, and the media rules
  (`ready` needs a `storage_key`, a `ready` video needs a positive duration, `failed` needs an
  `error_code`). Section and lesson positions use `UNIQUE ... DEFERRABLE INITIALLY DEFERRED` so
  a reorder can move several rows in one transaction, and the two freeze rules are PostgreSQL
  triggers: `courseversion_immutable` (a published version keeps its content, only
  `published → archived`, and an archived version never returns) and `version_content_frozen`
  (inserts, updates and deletes under a published version are refused for sections and
  lessons).
- **Impact:** T-007, T-017, T-018 and T-019 build on a schema whose invariants cannot be
  bypassed by a script, a shell or a second writer. `academy/models/base.py` now binds the
  tenant manager per model (`TenantManager[Course]`) so the type checker keeps model precision
  and still reports any read that bypassed `for_org`.
- **Evidence:** `python manage.py migrate` → `Applying academy.0001_initial... OK`;
  `python manage.py migrate academy zero` → `Unapplying academy.0001_initial... OK`; then
  forward again OK (triggers drop and recreate with the tables). `tests/test_catalog_models.py`
  (26 tests) writes the rows each rule forbids — blank titles, unknown statuses, version 0,
  duplicate version numbers, a second published version, an unstamped publish, position 0,
  duplicate positions (checked with `SET CONSTRAINTS ... IMMEDIATE`), out-of-range watch
  percent, unknown content types, a PDF without body, a `ready` asset without a key, a `ready`
  video with zero duration, a `failed` asset without an error code — and proves the freeze
  triggers reject content changes, inserts and deletes on published versions while drafts stay
  editable. `pytest -q` → 171 passed; `ruff check`, `ruff format --check`, `mypy .` (51 files)
  and `makemigrations --check --dry-run` clean; G7 and G9 pass.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-006, REQ-03, `docs/domain-model.md` §2.1–§2.5, §4–§5,
  `academy/models/catalog.py`, `academy/models/media.py`, `academy/migrations/0001_initial.py`.

### [2026-11-23] — T-006: g2 found a type-checker-only defect on a clean interpreter

- **Type:** Fix
- **Status:** Verified
- **Summary:** The first T-006 push failed gate G2 while the same `mypy .` passed in the
development image. The error was reproducible only from a clean `python:3.12-slim` with a fresh
`pip install ".[dev]"`: `Cannot override class variable ... with instance variable [misc]` on
every `objects: TenantManager[Model]` line. The abstract base declared `objects` as a bare
class attribute while the concrete models re-declare it as an annotated instance variable; the
type checker refuses that mix once the model's own annotation is present. The base now declares
`objects: Any = TenantManager()` with a comment, which is the declaration the per-model
overrides require.
- **Impact:** G2 is green again. The lesson is recorded because the development image had
  already installed the package and did not reproduce it, so an image-local green is not
  evidence for G2 — the clean-interpreter run is.
- **Evidence:** CI run `45168784765` (failed, g2) and run `45173786647` (green on
  `9deb22e`, all jobs except the by-design skipped g8-e2e); the clean-room reproduction printed
  the six errors at `academy/models/{media,catalog}.py` and `tests/test_tenant_model.py`.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-006, `docs/traceability.md` §3 G2, `academy/models/base.py`.


### [2026-11-23] — Documentation: H1 target adopted selectively (charter 2.3)

- **Type:** Documentation
- **Status:** Approved
- **Summary:** The project owner supplied a complete documentation package (charter,
  architecture, LOG, decision register, Hub contract, UI wireframes plus a new screen
  specification). Its product content was reviewed line by line and adopted **selectively**:
  charter 2.3 records the H1 target (Masheed only, one record set with Hub-integrated or
  standalone local sign-in, `grants_only`, Academy-owned dashboard and sidebar), decisions
  D-011 and D-026…D-030 are confirmed, `docs/ui/screen-specification.md` joins the repository,
  and the Hub contract, wireframes and configuration/API/schema/job documents were aligned.
  The package's replacement copies of `LOG.md` and `ARCHITECTURE.md` were **not** adopted:
  they carried a different history and renumbered ADR-001…ADR-018 with different meanings,
  which would have invalidated the references in `docs/adr/`, `docs/domain-model.md`,
  `docs/configuration.md` and `academy/adapters/organization.py`. `INSTALLATION_AR.md` stays
  outside the repository: it is the package's delivery note.
- **Impact:** Documents now describe the H1 product target truthfully as a target. No code,
  migration, endpoint or screen exists for `grants_only`, the standalone mode or
  `AccessSuspension`; T-009, T-014 and T-016 carry that work. No task status was changed by
  this documentation commit.
- **Evidence:** `python scripts/check_docs.py` (G9) passes locally and in CI run `45343579760`
  on commit `fd464be` (branch `docs/h1-alignment`), where g1–g7 and g9 are green and the g8
  journey job is skipped until T-023 activates it. Relative links, retired identifier
  patterns and required documents were re-checked. No test asserts any of the new product
  text.
- **Approved by:** Project owner (2026-11-23), after reviewing the conflicts above.
- **References:** CHARTER §§1, 3.1, 4, 5; ARCHITECTURE §§7, 11; `docs/decisions.md`
  D-011, D-026…D-030; `docs/ui/screen-specification.md`; `docs/domain-model.md` §2.7, §2.15.

### [2026-11-23] — H1 documentation alignment merged to main

- **Type:** Documentation
- **Status:** Merged
- **Summary:** The owner instructed «ادمج». `docs/h1-alignment` was fast-forwarded into
  `main` (no force-push, no rewritten history) and pushed. Charter 2.3, decisions D-011 and
  D-026…D-030, `docs/ui/screen-specification.md` and the aligned architecture, API,
  configuration, schema, job, Hub-contract, wireframe and traceability documents are now on
  `main`.
- **Impact:** Documentation only. No task status changed; T-009, T-014 and T-016 carry the
  implementation of `grants_only`, the access modes and `AccessSuspension`.
- **Evidence:** CI run `45345097262` on `main` at commit `fa75e87` — g1–g7 and g9 green, g8
  journey job skipped until T-023 activates it.
- **Approved by:** Project owner (2026-11-23): «ادمج».
- **References:** T-001 merge discipline (ff-only), `docs/traceability.md` §3.

### [2026-11-24] — T-007: assignment, enrollment and progress schema

- **Type:** Feature
- **Status:** Implemented
- **Summary:** `academy/models/progress.py` adds the four §2.6–§2.9 tables. `Assignment` carries
  the one-target shape with a `CHECK` that ties `target_ref` to `target_type` and an active-only
  unique index over `(organization_id, course, target_type, COALESCE(target_ref, ''))`, so the
  organization target collides too. `Enrollment` pins a learner to a version and allows exactly
  one active row per learner and course, while a cancelled row leaves room for a new
  enrollment after reactivation. `LessonProgress` keeps one row per lesson with the merged
  ranges in `jsonb` and `CHECK`ed non-negative numbers that cannot exceed the last accepted
  position. `CompletionRecord` snapshots course and version ids and is made immutable by the
  `completion_record_immutable` trigger created in the migration.
- **Impact:** The schema half of REQ-03 and REQ-09 now exists; the heartbeat, gating and
  completion services (T-019, T-020) have their tables and the database enforces their
  invariants. No endpoint or service writes these tables yet.
- **Evidence:** `tests/test_progress_models.py` (25 tests) writes the forbidden row for every
  check and partial index, including a cancelled assignment freeing its target, the
  organization target being unique, a cancelled enrollment allowing re-enrollment, and the
  trigger rejecting both `UPDATE` and `DELETE` on a completion row. `pytest -q` → 196 passed;
  `ruff check`, `ruff format --check`, `mypy .` and `makemigrations --check --dry-run` clean;
  `0002` applied, reversed to `0001` and re-applied on the dev database; G7 and G9 pass.
  CI run `45349326406` on branch `task/T-007-progress-models` is green.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-007, REQ-03, REQ-09, `docs/domain-model.md` §2.6–§2.9, `academy/models/progress.py`.

### [2026-11-24] — T-008: quiz and operational schema

- **Type:** Feature
- **Status:** Implemented
- **Summary:** `academy/models/quiz.py` adds the Phase 1 schema-only quiz tables: `Quiz`
  (version, optional lesson, pass mark, attempt cap), ordered `QuizQuestion` and `QuizChoice`,
  numbered `QuizAttempt` per enrollment and `QuizAttemptAnswer`. No endpoint reads or writes
  them; they exist so Phase 2 adds behaviour without a destructive migration.
  `academy/models/operations.py` adds the idempotency layer: `ReminderLog` unique per
  `(enrollment, kind, recipient_ref)`, `NotificationLog` unique per
  `(organization_id, dedupe_key, channel)` with the pending/sent/failed/skipped states and the
  rule that a `sent` row carries its timestamp, and `AuditEvent` with one event id per
  organization plus the object and time indexes.
- **Impact:** The last Phase 1–2 tables exist, so REQ-03's schema is complete and T-021/T-022
  can implement reminders and notifications against their keys. The audit append-only trigger
  is deliberately not created here: T-012 owns the audit service and its enforcement.
- **Evidence:** `tests/test_operational_models.py` (23 tests) covers the quiz ranges and
  uniqueness rules, the reminder and notification idempotency keys, the sent-timestamp rule and
  the audit event id uniqueness across organizations, plus the meta-test that every registered
  `academy` model subclasses `TenantModel`. `pytest -q` → 219 passed; `ruff check`,
  `ruff format --check`, `mypy .` and `makemigrations --check --dry-run` clean; `0003` applied,
  reversed to `0002` and re-applied on the dev database; G7 and G9 pass.
  CI run `45352655085` on branch `task/T-008-operational-models` is green.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-008, REQ-03, `docs/domain-model.md` §2.10–§2.13, T-012 (audit trigger).

### [2026-11-24] — T-009: authorization layer

- **Type:** Feature
- **Status:** Implemented
- **Summary:** `academy/authorization/` resolves effective capabilities from a `Principal`,
  the live grants a caller supplies, and the configured mode. `Scope` separates organization
  scope from an explicit department set, so a department grant cannot widen into an
  organization-wide write; `Access.require` raises `Forbidden`, `AccessSuspended` or
  `InactiveAccount` instead of returning a flag. `grants_only` (H1, D-027) keeps
  `academy.learn` for active members and ignores Hub roles entirely, while `role_plus_grants`
  keeps the documented role defaults as a tested compatibility mode. Expired and revoked
  grants are excluded, an unknown capability in a grant raises instead of silently granting
  access, and a suspension denies every capability (D-028). `AcademyPermission` and
  `CapabilityRequiredMixin` translate a request that already carries `academy_access`; they
  hold no policy of their own. `ACADEMY_AUTHORIZATION_MODE` is now a documented setting.
- **Impact:** T-016 can plug its grant table into `resolve_access` without changing the
  decision rules, and T-011/T-014 can attach the adapters to their authentication layer. No
  view, endpoint or grant table exists yet.
- **Evidence:** `tests/test_authorization.py` (23 tests) covers the allow/deny/scope matrix for
  both modes, department versus organization scope, grant unions, expiry at the exact instant,
  revocation, an unknown capability, suspension and inactivity, and both HTTP adapters.
  `pytest -q` → 242 passed; `ruff check`, `ruff format --check`, `mypy .` (60 files) and
  `makemigrations --check --dry-run` clean; G7 and G9 pass. CI run `45356215354` on branch
  `task/T-009-authorization` is green.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-009, REQ-13, D-027, D-028, `CHARTER.md` §3.1, `docs/api.md` §2.

### [2026-11-24] — T-010: test foundations and the tenant-isolation suite

- **Type:** Test
- **Status:** Implemented
- **Summary:** `tests/factories.py` builds one valid minimal row for every table in `academy`
  and exposes `assert_only_own_rows`, the detector that fails when a query returns a row from
  another organization. `tests/conftest.py` provides the two fixed organization IDs and a
  small course graph built through the factories. `tests/test_tenant_isolation.py` is generic:
  it requires a factory for every model declared under `academy.models`, writes each table in
  both organizations, asserts that `for_org` returns exactly its own row, and deliberately
  feeds an unscoped query to the detector so the detector itself is proven to fire.
- **Impact:** G7's tenant half is now active (`docs/traceability.md` §3), so a future query that
  bypasses `for_org` has an executable witness instead of only a review rule. The factories are
  the single place a schema change updates for test data.
- **Evidence:** `pytest -q` → 281 passed, of which `tests/test_tenant_isolation.py` is 39 cases
  over 17 tables; `ruff check`, `ruff format --check`, `mypy .` (63 files) and
  `makemigrations --check --dry-run` clean; G7 and G9 pass. CI run `45359422981` on branch
  `task/T-010-test-foundations` is green.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-010, REQ-03, `docs/traceability.md` §3 (G7), `docs/domain-model.md` §1.1.

### [2026-11-24] — T-011: API skeleton and error conventions

- **Type:** Feature
- **Status:** Implemented
- **Summary:** `/api/v1/academy/` now exists with the conventions of `docs/api.md` §1 in one
  place: `academy_exception_handler` renders Academy and DRF failures as
  `{code, detail, fields}` with the documented status, `AcademyPagination` fixes `page` and
  `page_size` (25, maximum 100), and `AcademyAccessAuthentication` refuses a request that
  carries no resolved `academy_access`. The only wired endpoint is
  `GET me/capabilities/`, which returns the caller's effective capabilities and scopes with
  `private, no-store`; every other inventory route waits for the service it calls. A
  drf-spectacular extension documents the `X-Masheed-Identity` header, and the generated
  OpenAPI document validates with no warnings.
- **Impact:** REQ-01's API skeleton exists, T-014/T-015 have the one place to attach identity,
  and every later endpoint inherits the envelope and pagination instead of restating them.
- **Evidence:** `tests/test_api_skeleton.py` (8 tests) covers the 401 envelope, the capability
  payload for both scope kinds, the schema path, Academy and DRF error mapping, pagination
  limits and the untouched-500 path. `pytest -q` → 289 passed; `ruff check`,
  `ruff format --check`, `mypy .` (72 files) and `makemigrations --check --dry-run` clean;
  `manage.py spectacular --validate --fail-on-warn` exits 0; G7 and G9 pass. CI run
  `45366886199` on branch `task/T-011-api-skeleton` is green.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-011, REQ-01, `docs/api.md` §1, §3, §9, §11, `docs/hub-contract.md` §2.

### [2026-11-24] — T-012: append-only audit trail and `audit.record`

- **Type:** Feature
- **Status:** Implemented
- **Summary:** `academy.audit.record` appends exactly one `AuditEvent` in the caller's
  transaction, so a rolled-back action leaves no audit row and a committed action cannot lose
  one to a late failure. The service refuses a malformed call before PostgreSQL sees it: a
  dotted lowercase action, a simple object type, a 64-character actor/object reference and
  metadata keys that name ids rather than free text or personal data (a fixed list of
  name/email/phone/notes/title keys is rejected). A repeated `event_id` returns the row that
  already exists and refuses a different actor, action or object under the same id, which is
  what the Hub mirror needs. Migration `0004` installs `academy_guard_audit_event`, and the
  model refuses to save or delete an existing row as a readable second line of defence.
- **Impact:** REQ-04's audit guarantee now holds at the database, not only in Python. Every
  service in T-016…T-022 can call one function inside its own transaction; the S1 audit screen
  reads rows this trigger makes unchanging.
- **Evidence:** `tests/test_audit.py` (22 tests) covers the stored row and tenant scope, the
  `system` actor, rollback leaving nothing, eight malformed calls, six metadata violations,
  idempotent and conflicting `event_id`, trigger-refused UPDATE/DELETE through the queryset, and
  the model guards. `pytest -q` → 311 passed; `ruff check`, `ruff format --check`, `mypy .`
  (75 files) and `makemigrations --check --dry-run` clean; `spectacular --validate
  --fail-on-warn` exits 0; G7 and G9 pass. CI run `45374222862` on branch
  `task/T-012-audit-trail` is green.
- **Approved by:** Project owner (2026-11-24): «كمل».
- **References:** T-012, REQ-04, ADR-009, `docs/domain-model.md` §2.13,
  `docs/skills/audited-action.md`, ARCHITECTURE §7.

### [2026-11-24] — T-013: design tokens, the shell and the component showcase

- **Type:** Feature
- **Status:** Implemented
- **Summary:** One shell now serves every Academy page: a header, a canvas and an
  Academy-owned sidebar that is a native disclosure on phones and sticky from 1024 px, in
  Arabic (RTL) or English (LTR) from the same markup. `static/css/academy.css` holds the tokens
  sampled from the approved PDF, using logical properties only, 44 px targets and a visible
  focus ring; the Arabic face is a locally hosted Noto Sans Arabic subset with its OFL licence.
  `academy/ui/` renders `/academy/preview/ar|en/` with the tokens, type, buttons, statuses,
  cards, a table that becomes labelled cards under 768 px, labelled fields with a validation
  message, the disclosure dialog pattern and the five sample states, plus the 403, 404 and 500
  pages. Every string goes through gettext; the Arabic catalogue is compiled from the tracked
  `.po` by `scripts/compile_messages.py`, which the image entrypoint and CI run, so no binary
  catalogue is committed and no build machine needs GNU `msgfmt`.
- **Impact:** T-016…T-022 inherit one shell, one token set and one set of patterns instead of
  restating them; the preview is the place to review RTL/LTR and the states before those
  screens land.
- **Evidence:** `tests/test_ui.py` (20 tests) covers the Arabic RTL and English LTR documents,
  the redirect, the five sample states, unknown language/state, the preview being absent
  outside a development profile, the 404/403/500 pages, absence of inline style and script,
  a label for every form control, navigation anchors that exist, and the shipped stylesheet and
  font. `pytest -q` → 331 passed; `ruff check`, `ruff format --check`, `mypy .` (81 files) and
  `makemigrations --check --dry-run` clean; `spectacular --validate --fail-on-warn` exits 0;
  G7 and G9 pass. CI run `45382616992` on `main` is green.
- **Approved by:** Project owner (2026-11-24): «كمل».
- **References:** T-013, REQ-05, `docs/ui/screen-specification.md` §1, §5, §7,
  `docs/ui/wireframes.md` §Visual language, §Preview routes, `docs/api.md` §10, RULES §UI.

### [2026-11-25] — T-013 follow-up: the development stack renders the shell

- **Type:** Fix
- **Status:** Implemented
- **Summary:** Running the stack locally exposed four gaps the test suite could not see:
  gunicorn serves no static files, so the stylesheet and the Arabic font answered 404; the
  browser cached the stylesheet heuristically from its `Last-Modified` header, so an edit was
  invisible until a cache purge; `<details>` hides its children entirely when closed, which
  removed the desktop sidebar; and a grid item's min-content width let a long field stretch
  the column past a 360 px viewport. The development profile now mounts `config.dev_static`
  (only with `DEBUG`, with `no-store`), maps `woff2` to its real MIME type, uses a
  checkbox-and-label drawer, and keeps every grid item at `min-inline-size: 0` with
  `minmax(0, 1fr)` main column.
- **Impact:** `/academy/preview/ar|en/` is reviewable in a browser at 360, 768 and 1280 with
  its real font and styles; production is unchanged because the route needs `DEBUG` and the
  build collects statics separately.
- **Evidence:** `pytest -q tests/test_ui.py` → 20 passed; `ruff check`, `ruff format --check`
  and `mypy .` (82 files) clean. In the browser: no console errors, stylesheet and font return
  200, no horizontal overflow at 360 or 768 in Arabic and English, and the menu button opens
  and closes the drawer. CI run `45562632646` on `task/T-013-ui-foundation` is green.
- **Approved by:** Project owner (2026-11-25): «كمل».
- **References:** T-013, `docs/ui/screen-specification.md` §5, `docs/api.md` §10,
  `docs/operations/environments.md`.

## 2026-11-25 — T-018 media upload, verification and HLS pipeline

- **Why:** REQ-07 needs a video lesson the platform can actually deliver; until now the
  `MediaAsset` model had no way in and no way out.
- **What changed:** `academy/media/service.py` issues a presigned `PUT` for a per-asset tenant
  key (`org/<id>/media/<asset>/original.<ext>`), enforces the kind/size/content-type policy
  from §3 and verifies the object with `stat` before the asset leaves `awaiting_upload`, so a
  client cannot declare success for bytes the bucket never received. `complete`/`retry`
  enqueue the worker through `transaction.on_commit`; the worker probes the original, builds
  the rendition ladder from `ACADEMY_HLS_RENDITIONS`, drops a rendition taller than the
  source, and writes `hls/<name>/index.m3u8` plus a poster, all inside the asset prefix so one
  `delete_prefix` cleans it up. `manage/media/` exposes create/detail/complete/retry and
  `playback` returns presigned playlists with `Cache-Control: private, no-store`.
- **Impact:** media state is now durable and visible: every failure keeps a stable
  `error_code` (`upload_missing`, `checksum_mismatch`, `unsupported_type`, `upload_too_large`,
  `transcode_failed`, `storage_unavailable`) and `attempt_count`, and a retry stops at
  `ACADEMY_TRANSCODE_ATTEMPTS`.
- **Evidence:** `pytest -q` → 459 passed, including 15 new media tests (the slow pair runs a
  real two-second `ffmpeg` clip and asserts the playlists, segments and `360p` entry);
  `ruff check`, `ruff format --check`, `mypy .` (126 files), `makemigrations --check` and
  `spectacular --validate --fail-on-warn` (0 warnings) clean, G7 and G9 pass. CI run
  `45617783011` on `task/T-018-media` is green.
- **Approved by:** Project owner (2026-11-25): «كمل».
- **References:** T-018, `docs/api.md` §3–§4, `docs/configuration.md` §3–§4,
  `docs/domain-model.md` §2.5/§5, `docs/background-jobs.md` §1.


## 2026-11-25 — T-020 heartbeat, anti-skip and the completion flow

- **Why:** REQ-09 needs the server to decide what a learner has actually watched, so a player
  cannot declare coverage it never earned, and needs completion that stays correct when the
  same request arrives twice.
- **What changed:** `academy/progress.py` is the whole write path of §7. `record_heartbeat`
  locks the row, credits at most `credit_window * rate` where the window is the elapsed time
  capped at `MAX_HEARTBEAT_GAP_SECONDS`, refuses a forward jump with the ceiling it applied,
  and never lowers the position: rewatching credits nothing and the high-water mark stands,
  because `frontier_seconds <= position_seconds` is a table check. The refusal commits its
  `skip_attempts` counter (the abuse metric) without touching the clock, so a patient retry is
  credited normally, and heartbeats are still neither audited nor stored (ADR-013).
- **Completion:** `complete_lesson` answers 409 `lesson_not_eligible` with the coverage it
  measured until the threshold is met, completes on confirmation for lessons without a duration,
  and is idempotent — a second call returns the original completion and emits nothing.
  `acknowledge` records the acknowledgement once, `complete_enrollment` refuses with
  `enrollment_incomplete` while a required lesson is unfinished (listing the blockers) or while
  an acknowledgement is pending, and the administrative override needs a reason, stays audited
  once with ids-only metadata, and refuses a cancelled enrollment.
- **API:** `enrollments/{id}/lessons/{lesson_id}/progress/` (throttle scope `heartbeat`),
  `…/complete/`, `enrollments/{id}/acknowledge/`, `enrollments/{id}/complete/` and the
  administrative `manage/enrollments/{id}/complete/`; every response is
  `Cache-Control: private, no-store`, and the four new error codes are mapped in
  `academy/api/errors.py`.
- **Evidence:** `pytest -q` → 528 passed (32 new tests: the §9 skip matrix including the
  600-second gap, `rate` 3.0 and 0.4, rewind, replay, a gap after the frontier, the first
  heartbeat, the locked lesson and learner isolation; completion threshold and idempotency;
  acknowledgement; enrollment blocking and override auditing; the HTTP matrix 200/400/401/403/409
  and the administrative override); `ruff check` and `ruff format --check` clean, `mypy .`
  (136 files), `makemigrations --check` (no changes), `spectacular --validate --fail-on-warn`
  (0 warnings), G7 and G9 pass. CI run `45634497939` on
  `task/T-020-progress-heartbeat-completion` is green; merged to `main` as `cff7c9b`.
- **Documented:** §7.3 now states that a refusal commits its counter and that the first
  heartbeat credits no coverage, `skippable_seconds` is defined as the ceiling that was applied,
  §7.6 names the lesson's own media asset as the duration source, and `docs/api.md` §5 spells
  out the override's reason, audit and cancelled-enrollment behavior.
- **Approved by:** Project owner (2026-11-25): «كمل».
- **References:** T-020, `docs/api.md` §1/§3/§5/§11, `docs/domain-model.md` §2.8/§7/§9,
  `docs/configuration.md` §6, ADR-013.

## 2026-11-25 — T-019 assignments, auto-enrolment and gating

- **Why:** REQ-08 needs a manager to reach a group of learners and needs a Hub membership
  change to materialise as an enrollment, without a second code path.
- **What changed:** `academy/assignments/` now owns the write path and its selectors.
  `expansion.expand_target` is the single D-017 selector the preview and the write share:
  `department_members` (descendants included), `role_members`, one `user`, and — for
  `organization` — the union of `role_members` over every reported role, because the Hub has no
  all-members route; the result is de-duplicated, truncated at 5,000 and reports `capped`.
  `service.create_assignment` validates the target shape and scope, refuses an archived course
  or one without a published version (409 `course_not_published`), refuses an expansion that
  reaches nobody (422 `target_empty`), and writes the assignment, its enrollments, the audit row
  and one `assignment.created` event (carrying the count, not 5,000 payloads) in one
  transaction. Cancelling an assignment cancels its active enrollments as `unassigned`;
  cancelling one enrollment is audited as `removed_from_target`.
- **Auto-enrolment:** `member_changed` now enrols a member into every live assignment that
  reaches them and cancels rows whose assignment no longer does (`removed_from_target`);
  `member_deactivated` cancels every active row (`deactivated`). Both run inside the webhook
  transaction, so a rolled-back delivery leaves nothing behind, and a repeat is a no-op because
  the partial unique index already pins one active enrollment per learner and course.
- **Gating:** `gating.state_for` / `require_accessible` implement §7.5 — a required lesson is
  locked while any earlier required lesson is incomplete, optional lessons open at any time and
  never gate later ones. `playback` now consults it before presigning, so a locked lesson
  answers 403 `lesson_locked` with `fields.next_lesson_id` instead of a rendition URL.
- **API:** `manage/assignments/` (list/create with a required `Idempotency-Key` and replay),
  `manage/assignments/preview/`, `manage/assignments/{id}/` (DELETE), the course roster,
  `manage/enrollments/{id}/cancel/`, and the learner reads `my/courses/`, `my/enrollments/`
  and `my/enrollments/{id}/` with the outline. Out-of-scope objects answer 404.
- **Evidence:** `pytest -q` → 496 passed (37 new assignment tests: expansion cap, scope matrix,
  idempotency, cancellation reasons, webhook-driven enrolment, gating matrix, outline, playback
  lock, learner isolation); `ruff check` and `ruff format --check` clean, `mypy .` (133 files),
  `makemigrations --check` (no changes), `spectacular --validate --fail-on-warn` (0 warnings),
  G7 and G9 pass. CI run `45624655284` on `task/T-019-assignments` is green; merged to `main`
  as `1d5fc56`.
- **Approved by:** Project owner (2026-11-25): «كمل».
- **References:** T-019, `docs/api.md` §3/§5/§11, `docs/domain-model.md` §2.6–§2.7/§7.5,
  `docs/hub-contract.md` §3–§4, D-015, D-017, D-028.
