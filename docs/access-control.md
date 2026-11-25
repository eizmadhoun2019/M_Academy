# ACCESS CONTROL — Identity, Membership, Roles and Scopes

**Status:** Canonical. This file is the only source for permission codes, default roles, scope
semantics and authorization rules. Charter: REQ-21…REQ-25, REQ-28. Schema:
`docs/domain-model.md` §2.0. Security controls: `docs/security.md`.
**Last reviewed:** 2026-11-25

## 1. Concepts (separate on purpose)
| Concept | Meaning | Table |
|---|---|---|
| Account | A person who can authenticate. One per person, independent of any company. | `User` |
| Company | A tenant. Has its own settings, departments, members and data. | `Organization` |
| Membership | The link between one account and one company; carries its own state, department and roles. | `Membership` |
| Role | A named bundle of permissions, system-provided or company-defined. | `Role` |
| Permission | A functional capability code, e.g. `academy.content.publish`. | `Permission` |
| Scope | Where a permission applies: `PLATFORM`, `COMPANY`, `DEPARTMENT`, `SELF`. | assignment/grant |
| Assignment | Grants one role at one scope to one membership. | `RoleAssignment` |
| Exceptional grant | Adds one permission at one scope outside roles, with reason and expiry. | `PermissionGrant` |

Account state, membership state and company state are independent. An active account with no
active membership can sign in but reaches only company selection/“no access”. A suspended
company blocks all of its memberships' tenant access while platform administration still works.

## 2. Permission catalogue (22 codes)
Codes are stable API. Prefix `academy.` = tenant capability; `platform.` = platform capability.
`S` = permitted scope kinds.

| Code | Meaning | S |
|---|---|---|
| `academy.learn` | Consume assigned courses, record progress and complete lessons | SELF |
| `academy.content.view` | Read the course catalogue, outlines and lesson metadata (drafts included) | COMPANY, DEPARTMENT |
| `academy.content.manage` | Create and edit courses, versions, sections, lessons (not publish) | COMPANY, DEPARTMENT |
| `academy.content.publish` | Publish/archive a course version | COMPANY, DEPARTMENT |
| `academy.media.manage` | Upload, replace and retire media assets | COMPANY, DEPARTMENT |
| `academy.assignment.view` | Read assignments, targets and rosters | COMPANY, DEPARTMENT |
| `academy.assignment.manage` | Create, change, cancel assignments | COMPANY, DEPARTMENT |
| `academy.report.view` | Read dashboards and reports | COMPANY, DEPARTMENT |
| `academy.report.export` | Export report data as CSV | COMPANY, DEPARTMENT |
| `academy.member.view` | List members, departments and membership states | COMPANY, DEPARTMENT |
| `academy.member.manage` | Invite, activate, suspend, remove members; set membership departments | COMPANY |
| `academy.department.manage` | Create, rename, re-parent, archive departments | COMPANY |
| `academy.role.manage` | Create/edit company roles and role assignments | COMPANY |
| `academy.grant.manage` | Create/revoke exceptional permission grants | COMPANY |
| `academy.audit.view` | Read the company audit trail | COMPANY |
| `academy.settings.manage` | Change company settings (name, language, time zone, reminder hour, sender name) | COMPANY |
| `platform.organization.view` | List and inspect companies and their lifecycle state | PLATFORM |
| `platform.organization.manage` | Create, suspend, reactivate, archive companies | PLATFORM |
| `platform.organization.access` | Audited **read-only** access to one company's training data, content, reports and audit | PLATFORM |
| `platform.user.manage` | Manage platform users and platform role assignments | PLATFORM |
| `platform.audit.view` | Read platform audit events | PLATFORM |
| `platform.settings.manage` | Platform settings and integration enablement | PLATFORM |

Rules: no wildcard permission; no permission without a check; no permission added without a
row here, a test, and a role that uses it. `academy.admin`, `manage_content`, `view_reports`,
`export_reports` are **legacy capability names**, not part of the catalogue; their mapping is in
§5 and they must disappear from runtime checks by T-028.

## 3. Default roles
System roles are seeded, cannot be deleted and their permission sets are fixed by this table.
Company Admins may create additional company roles from catalogue permissions.

| Role | Scope(s) | Permissions |
|---|---|---|
| **Super Admin** (platform) | PLATFORM | `platform.organization.view`, `platform.organization.manage`, `platform.organization.access`, `platform.user.manage`, `platform.audit.view`, `platform.settings.manage` |
| **Company Admin** | COMPANY | `academy.content.view`, `academy.content.manage`, `academy.content.publish`, `academy.media.manage`, `academy.assignment.view`, `academy.assignment.manage`, `academy.report.view`, `academy.report.export`, `academy.member.view`, `academy.member.manage`, `academy.department.manage`, `academy.role.manage`, `academy.grant.manage`, `academy.audit.view`, `academy.settings.manage`; plus `academy.learn` at SELF |
| **Training Manager** | COMPANY or DEPARTMENT | `academy.learn`, `academy.content.view`, `academy.content.manage`, `academy.content.publish`, `academy.media.manage`, `academy.assignment.view`, `academy.assignment.manage`, `academy.report.view`, `academy.report.export`, `academy.member.view` |
| **Auditor** | COMPANY or DEPARTMENT | `academy.content.view`, `academy.assignment.view`, `academy.report.view`, `academy.report.export`, `academy.member.view`, `academy.audit.view` |
| **Learner** | SELF | `academy.learn` |

Notes:
- Super Admin does **not** inherit tenant write permissions. It can create/suspend companies and
  assign Company Admins; cross-company data access happens only through
  `platform.organization.access`, with an explicit company context and an audit event.
- `audit.view` at DEPARTMENT scope is not valid; audit is company-wide.
- A membership may hold several roles; effective permissions are the union, each constrained by
  its assignment's scope.
- System role keys: `super_admin`, `company_admin`, `training_manager`, `auditor`, `learner`.
  Company custom roles use `custom.<slug>` within the company.

## 4. Scope semantics
| Scope | Applies to | Resolution |
|---|---|---|
| `PLATFORM` | Platform permissions only | No company. Company data only via `platform.organization.access` + explicit selected company. |
| `COMPANY` | The whole company | `organization_id` must equal the active company. |
| `DEPARTMENT` | One department and its descendants | the department scopes on the membership's role assignments and grants (explicit list, descendants included by default); a department from another company is invalid. |
| `SELF` | The caller's own membership/records | `membership_id` must equal the caller's membership in the active company. |

Rules:
- Scopes are **not** a hierarchy that silently widens: a permission lists the scopes it accepts
  (§2). A `COMPANY` assignment of `academy.member.manage` does not grant anything at
  `DEPARTMENT`; a `DEPARTMENT` assignment of a company-only permission is rejected at write time.
- Company selection is server-side. The client may send `organization_id` only as a switch
  request; the server verifies an active membership (or platform access) before using it.
- Department scope never includes another department's content/assignments/reports just because
  the caller is a manager elsewhere.
- Objects are re-checked: a department-scoped manager cannot read a company-wide course unless
  the course's owner department is within scope or is `NULL`/general (general courses are
  readable, editable only with `COMPANY` scope).
- A platform access session is read-only even if the user also holds a company role; writes
  require leaving platform-access mode and using the membership.

## 5. Legacy mapping (migration input)
| Legacy capability | Becomes |
|---|---|
| `academy.learn` | `academy.learn` (SELF) |
| `manage_content` | `academy.content.view`, `.manage`, `.publish`, `academy.media.manage` at the same department scope |
| `view_reports` | `academy.report.view` |
| `export_reports` | `academy.report.export` |
| `academy.admin` | Company Admin role bundle at COMPANY (platform roles never derive from it) |

Existing `PermissionGrant` rows are converted to `RoleAssignment` (known bundles) or retained as
exceptional grants with reason `migrated`, an expiry of 90 days and a review task. A mapping is
applied once, idempotently, by the migration command in T-027; the legacy names are removed from
code in T-028.

## 6. Grants and management rules
- Only a holder of `academy.role.manage` (COMPANY) can assign roles; only
  `academy.grant.manage` can create exceptional grants.
- **No escalation:** the grantor must hold every permission being granted, at a scope equal to
  or broader than the granted scope. Platform permissions can never be granted from a company
  context.
- A user cannot change their own roles/grants in a way that increases their access, and cannot
  remove their own last administrative role if they are the last administrator.
- Exceptional grants require a reason and expire (default 30, max 90 days); expired grants are
  ignored immediately and cleaned up by a job.
- Suspension (account or membership) suppresses effective permissions without deleting roles.
- Role/grant changes take effect on the next request (no permission data cached in the session
  beyond the active company id); permission caches are invalidated on change.
- Every assignment, revocation, suspension and role edit writes an `AuditEvent`.
- **Last-admin protection:** at least one active platform user must hold
  `platform.organization.manage` + `platform.user.manage`; at least one active membership per
  company must hold `academy.member.manage` + `academy.role.manage`. The operation that would
  remove the last one is rejected with `LAST_ADMIN` and audited.
- Invitations carry the intended role(s), department(s) and expiry; acceptance creates the
  membership, never grants more than the invitation states.

## 7. Enforcement points (all required)
1. **Route/view:** declares `permission` and allowed scopes; unauthenticated → login;
   authenticated but unauthorized → 403 (HTML) / `FORBIDDEN` (API). Denial is audited
   (sampled per user+route to avoid log flooding).
2. **API serializer:** never accepts role, scope, company or actor authority from the body.
3. **Service:** receives a `Principal` (user + membership + company + effective access) and
   rechecks the permission and object scope before any write.
4. **Selector:** always requires `organization_id`; department filters come from the principal's
   effective scope, never from the query string alone.
5. **Model/query:** tenant manager filters by active company; cross-company FKs are impossible
   by constraint.
6. **Template/JS:** navigation, buttons and actions are rendered from effective permissions;
   hidden UI is not a security control.
7. **Task:** derives the company from the record and enforces the same guards; no task runs with
   a “superuser bypass”.
8. **Report/export:** scope filter is applied before aggregation; export columns are an allowlist.

## 8. State model and effects
| Entity | States | Effect |
|---|---|---|
| Account (`User`) | unverified → active → suspended → deactivated | Suspended/deactivated cannot authenticate; existing sessions revoked; audit retained. |
| Membership | invited → active → suspended → removed | Only `active` yields tenant access; suspension keeps history and roles but suppresses permissions; removal ends access, retains training history, and cancels unfinished enrollments. |
| Company | active → suspended → archived | Suspended blocks tenant access for all members (platform admins can still manage it); archived is read-only for the platform and hidden from members; no hard delete while history exists. |

Transitions are audited and permission-checked: membership changes need `academy.member.manage`,
company lifecycle needs `platform.organization.manage`, suspension/lift needs the same permission
plus a reason. Self-service profile changes are limited to display name, language and password.

## 9. Audit events (minimum)
`auth.login_succeeded`, `auth.login_failed`, `auth.logout`, `auth.password_changed`,
`auth.password_reset`, `auth.email_verified`, `auth.mfa_enabled`, `auth.mfa_disabled`,
`auth.session_revoked`, `membership.invited`, `membership.activated`, `membership.suspended`,
`membership.removed`, `membership.roles_changed`, `grant.created`, `grant.revoked`,
`role.created`, `role.updated`, `organization.created`, `organization.suspended`,
`organization.reactivated`, `organization.archived`, `platform.access_started`,
`platform.access_ended`, `report.exported`, `authorization.denied` (sampled), `settings.changed`.
Event fields: actor user id (or `system`), actor membership id when applicable, company id
(nullable for platform events), action, target type/id, before/after (non-secret), request id,
timestamp. Never store passwords, tokens, MFA secrets or full email in audit payloads.

## 10. Tests and evidence (G10)
The following matrix is implemented in T-027/T-028 and extended by T-034; a permission row is
not “done” until its allow and deny cases exist.

| Suite | Must prove |
|---|---|
| Catalogue integrity | Every code in §2 exists exactly once; no orphan code in views/services; every role permission exists; no wildcard. |
| Role matrix | For each default role × representative endpoint: allowed scope → 2xx; narrower/other company → 403/404 without data. |
| Escalation | Company Admin cannot grant platform rights, a permission they lack, or broader scope; self-escalation blocked. |
| Tenant isolation | Two companies with identical data: list/detail/report/export/audit/media never cross; cache keys and task payloads carry the company. |
| Scope | DEPARTMENT includes descendants, excludes siblings; SELF sees only own enrollment; general course rules. |
| Lifecycle | Suspension suppresses access immediately; removal cancels enrollments; company suspension blocks all members; reactivation restores only valid states. |
| Last admin | Removing/demoting the last platform/company admin returns `LAST_ADMIN` and changes nothing. |
| UI | Navigation and actions match effective permissions for each default role; direct URL access still denied by the server. |
| Audit | Every §9 event is written once with the right actor/company; denied attempts are recorded; audit cannot be updated/deleted. |

Acceptance evidence for T-028: the matrix suite output, a catalogue-coverage check, and the
architecture test that forbids unpermissioned routes.

## 11. UI mapping
- Sidebar groups: **Learning** (`academy.learn`), **Training** (`content.*`, `assignment.*`,
  `media.manage`), **Insights** (`report.*`), **Administration** (`member.*`, `role.manage`,
  `grant.manage`, `department.manage`, `audit.view`, `settings.manage`), **Platform**
  (`platform.*`).
- Empty groups are not rendered. A screen requires every permission listed in its spec; actions
  within a screen require their own permission.
- The dashboard shows counts only for objects inside the caller's scope; platform dashboards name
  the company filter explicitly and never mix companies in one total without a label.
- Disabled actions display the reason (“requires Company Admin”), never a silent no-op.
