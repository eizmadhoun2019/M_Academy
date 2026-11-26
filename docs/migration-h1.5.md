# MIGRATION H1.5 — From Single-Company References to Local Tenancy

**Status:** Canonical migration plan for T-026…T-028 and T-032/T-034.
**Last updated:** 2026-11-26
**Decisions:** D-032 (tenancy), D-033 (local identity), D-034 (RBAC), D-038 (company settings),
D-043 (one company membership per account).
**Related:** `docs/domain-model.md`, `docs/security.md` §6, `docs/operations/environments.md` §10.

---

## 1. Current → target
| Area | Current (pre-H1.5) | Target |
|---|---|---|
| Company | one fixed `ACADEMY_ORGANIZATION_ID`, no table | `Organization` row per company; FKs everywhere |
| Department | opaque `department_ref` strings | `Department` per company, FK, tree |
| User | opaque `user_ref`; identity from Hub or dev login | `User` (UUID, email login) + at most one `Membership`, with `UNIQUE (user_id)` |
| Roles | fixed capability bundles + `PermissionGrant` on `user_ref` | `Permission`/`Role`/`RoleAssignment` + scoped grants on membership |
| Audit actor | `actor_ref` string | `actor_user_id` + `actor_membership_id` (nullable for platform/system) |
| Notifications | recipient `user_ref`, Hub directory lookup | `recipient_user_id` + `recipient_membership_id`, local address |
| Auth | Hub assertion in production; insecure dev login | local Django auth + MFA; dev login dev/test only |
| Reports | single-company selectors | company scope + platform aggregate |
| Hub | enabled/default integration | dormant, optional (D-031) |

Training history is preserved: courses, versions, sections, lessons, media assets, assignments,
enrollments, progress, completions, quizzes, notification/reminder logs and audit events keep
their rows and primary keys.

## 2. Rules
1. **Expand → migrate → contract.** Add nullable columns/tables, backfill, switch reads, verify,
   then remove legacy columns in a later release. Never drop a column in the same migration that
   adds its replacement.
2. **One backup before any transformation.** A verified pre-migration dump and a bucket copy are
   prerequisites; the task stops if either is missing.
3. **Idempotent data migrations.** Re-running produces the same result and reports counts.
4. **No invented identity data.** Email addresses are imported only from an owner-provided file
   or entered by the person; never guessed.
5. **Cross-tenant integrity is a database guarantee**, not only a service check (composite FKs).
6. **Rehearsal first.** Every step runs on a restored copy of the current database before staging,
   and a second time on staging before production.
7. **Rollback is restore-based** for the cutover: code rollback is supported for one release;
   data rollback uses the pre-migration backup because identifiers are rewritten.
8. **No duplicate membership survives.** Any imported user resolving to more than one company is
   a hard preflight failure: the report names each collision and cutover stops for manual owner
   resolution; the migration never picks a company or drops one silently (D-043).

## 3. Schema mapping
| Legacy value | New owner | Rule |
|---|---|---|
| `ACADEMY_ORGANIZATION_ID` | `Organization.id` | Seed one row with this UUID, name `ACADEMY_COMPANY_NAME` (default “Masheed Academy”), slug `masheed`, `status='active'`, `timezone=ACADEMY_BUSINESS_TZ`, `default_language=ACADEMY_DEFAULT_LANGUAGE`; re-running is a no-op. |
| `department_ref` / `owner_department_ref` / `target_ref` | `Department.id` | Create one Department per distinct ref in the seeded company; keep `legacy_ref` unique per company for lookup; re-parent from the existing hierarchy if present, otherwise flat. Unresolved refs are reported and block cutover. |
| `user_ref` (progress, enrollment, notification, grants) | `User.id` + `Membership.id` | Create a disabled account from the owner's `legacy_user_ref,email,display_name` CSV; without an email, generate `pending+<uuid>@invalid.masheed` and `must_set_email=true` (non-deliverable, cannot sign in). Create one active Membership in the seeded company. `User.legacy_ref` (unique when set) and `Department.legacy_ref` (unique per company) keep the mapping without a permanent mapping table. |
| `actor_ref` / `recipient_ref` / `manager_ref` | `User`/`Membership` | Same mapping; `system` stays null with `actor_type='system'`. Unknown values keep the legacy text in `legacy_actor_ref` for audit reconstruction; they never become a real account. |
| `PermissionGrant(user_ref, capability)` | `RoleAssignment`/`PermissionGrant(membership)` | Map legacy capability strings through `docs/access-control.md` §5; a capability with no H1.5 equivalent is listed in the migration report and dropped only with owner sign-off. |
| `MediaAsset.organization_id`, storage key | `Organization.id` | Keys are already `org/<uuid>/...`; verify prefix matches the new company id; no object copy needed. |
| Hub `organization_id` claim | local `Organization` | Only used when Hub is enabled; unmapped → reject. |

## 4. Steps
**M0 — preflight (T-026).** Freeze writes; take and verify the backup; record row counts for
every table; export `legacy_user_ref` distinct values and department refs; run the cross-company
duplicate-membership query and abort on any hit; confirm storage reachability; record the current
commit and image digest.

**M1 — schema expand.** Add `Organization`, `Department`, `User`, `Membership`; add nullable
`organization_id` FKs (or reuse the existing column where it is already a UUID) and nullable
`user_id`/`membership_id`/`department_id`; add composite unique constraints; add `legacy_ref`
columns. No read path changes yet.

**M2 — seed and map.** Create the company, departments and accounts from the CSV. Write a
mapping table (report, not a permanent model) of `legacy_ref → new id`.
`manage.py backfill_tenancy --identities <csv> --dry-run --report <json>` validates and reports;
the same command without `--dry-run` writes, and a second run changes nothing. Reconcile counts:
distinct legacy user refs = accounts created; distinct department refs = departments created;
every enrollment/progress row has a resolvable learner. Assert one membership per account and
zero accounts with memberships in two companies; any violation aborts with a report.

The command, migration 0009 and their tests are merged (T-026 CP2, `e3f9715`). The reconciliation
itself is an **open acceptance condition**: it closes only when the owner supplies the identity
CSV, or states in writing that no rows require migration. Until then the dry run names every
missing ref and writes nothing, no real account exists, and T-026 cannot close.

**M3 — backfill.** In batches (5,000 rows, one transaction per batch): set `organization_id`,
`user_id`, `membership_id`, `department_id`. Abort on any unresolved row; never guess. The
append-only audit ledger and the immutable completion record accept exactly one fill of their new
nullable links from `NULL` (migration 0009 replaces both guards); any other edit, and any rewrite
of a filled link, is still refused, and reversing 0009 restores the strict guards.

**M4 — constraints and reads.** Make columns non-null where the model requires it; add composite
FKs; switch services/selectors/API/permissions to the new fields; keep legacy columns read-only.
Run the full suite plus the isolation suite.

**M5 — identity cutover (T-027).** Import/verify emails, send invitations or verification mail,
enable local login, remove dev login outside development, disable Hub identity in standalone.
Users who cannot be reached remain disabled with `must_set_email=true`; their history stays
visible to admins.

**M6 — contract (T-034).** After one release with no reads of the legacy columns, drop
`user_ref`/`department_ref`/`actor_ref`/`recipient_ref` and their indexes in a dedicated
migration, with a final backup and a documented reverse. The legacy text needed for audit stays
only in the audit metadata, not in live foreign keys.

## 5. Verification
- **Counts:** per table, before/after equality for rows that must be preserved; mapping coverage
  100% for enrollments, progress, completions, assignments and audit actors.
- **Journeys:** a learner with existing progress resumes at the same frontier; a manager sees the
  same roster; a report produces the same totals for the seeded company (allowing for the
  documented time-zone interpretation change).
- **Isolation:** two-company suite passes; a forged company id cannot read the seeded company.
- **Auth:** every mapped account can be invited and signed in; a disabled placeholder cannot; a
  second invitation to another company is rejected; login lands directly on the permitted
  dashboard with no company chooser.
- **Audit:** historical events remain readable and attributable; new events use UUIDs.
- **Rollback:** restore the pre-migration dump in a scratch environment, boot the previous
  release and confirm the legacy journey works; record the duration.

## 6. Cutover and rollback
1. Announce a maintenance window (staging: 30 min; production: 60 min).
2. Freeze writes, drain workers, take the final backup and verify its checksum.
3. Run migrations (`migrate`), then the mapping/backfill commands with `--dry-run` followed by
   the real run; capture counts.
4. Switch reads/feature flags, deploy the new release, run smoke checks (health, sign-in, one
   learner journey, one admin action, one report).
5. Unfreeze; monitor 5xx, queues, mail and login failures for 60 min.

Rollback within the window: stop the new release, restore the pre-migration database, restore the
bucket if it changed, redeploy the previous digest, verify. After the window, rollback requires
the same restore plus an incident review; the legacy columns are not a second source of truth.

## 7. Out of scope
No H2 features, no billing, no company self-registration, no Hub activation, no table
partitioning or RLS during this migration. Multi-company user moves and multiple memberships
are out of scope (D-043); enabling them later requires a new decision and migration. Those items
have their own trigger and decision.

## 8. Reconciliation audit (2026-11-26)

The owner kept CP2's real-data mapping/reconciliation as an acceptance condition. This audit
answers it with counts only: no name, e-mail, reference value or other row content is selected
for the report, and nothing is written.

**Databases in scope.** The workspace holds exactly one database: the development PostgreSQL
16.14 instance of `docker-compose.yml` (container `m-academy-db-1`, database `academy`, reached
by the application as the compose service `db`). Staging and production do not exist yet —
`docs/operations/environments.md` §1 creates staging in T-034 and production only after the
release decision — and no dump, backup or snapshot is present in the workspace or tracked in
the repository. No other dataset exists that this audit could have missed.

**Method.** `python manage.py audit_legacy_data [--json]` counts, read-only:

- every tenant table's rows, and every nullable backfill link (§4 M3) still `NULL`;
- distinct non-empty values per `*_ref` column and their union — only the numbers are printed;
- the duplicate-membership queries the cutover must see at zero (D-043).

**Result** (2026-11-26, database `academy`):

| Group | Value |
|---|---|
| Organizations | 1 (`masheed`, `active`) |
| Accounts / with a legacy ref / `must_set_email` | 0 / 0 / 0 |
| Departments / with a legacy ref | 0 / 0 |
| Memberships / active | 0 / 0 |
| Tenant tables | 17 audited, **0 rows in total** |
| Rows holding a `NULL` backfill link | 0 |
| Distinct legacy references (union of 21 `*_ref` columns) | 0 |
| Accounts with more than one membership / in more than one company | 0 / 0 |
| Verdict | `needs_migration: false` |

**Conclusion.** The only database contains no legacy row, so nothing has to be mapped: CP2's
command has no input to transform and the owner's identity CSV is not required for it. The
reconciliation condition can be closed on the owner's acceptance of this evidence. The same
command runs against a restored production dump before cutover (§6 step 3); it prints counts
only, so it is safe to run early and its output is the proof that the mapping is complete.
