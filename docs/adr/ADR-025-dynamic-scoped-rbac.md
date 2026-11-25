# ADR-025 — Dynamic scoped RBAC replacing Hub roles and coarse capabilities

- **Status:** Accepted (2026-11-25)
- **Date:** 2026-11-25
- **Deciders:** Project owner
- **Supersedes:** ADR-011 (Academy grants combined with Hub role defaults), ADR-014 (grants-only default)
- **References:** D-034, D-043; REQ-13, REQ-23

## Context
The old model mapped a Hub role (`platform_admin`/`department_manager`/`employee`) to a fixed
capability bundle and stored exceptional grants against an opaque `user_ref`. It could not express
platform vs company vs department scope, custom company roles, or a clean separation between
identity and authority. (It also assumed multiple memberships; H1.5 now limits one per account,
D-043.) Hub role names were also leaking into Academy
authorization.

## Decision
Academy owns a permission catalogue and resolves effective access from:
`Permission` → allowed scopes; `Role` (system or custom) → permissions; `RoleAssignment`
(membership, role, scope); `PermissionGrant` (membership, permission, scope, expiry) for
exceptions; `PlatformRoleAssignment` for platform authority. Default roles are Super Admin,
Company Admin, Training Manager, Learner, Auditor. The engine is deny-by-default, least-privilege,
scope-aware and enforced in services and routes; the UI only reflects it. Escalation and
last-admin protections are transactional. Authorization derives the company from the single
membership; platform authority is a separate assignment and never creates a membership.

## Rationale
- Real companies need custom roles and departmental delegation.
- Scopes are properties of a permission, not a hierarchy that grants implicitly.
- One catalogue makes API, UI, reports and tests share a single truth.
- Hub roles become identity metadata only; authority stays local.

## Alternatives considered
- **Django groups only:** rejected; no scope, expiry, grant provenance or platform separation.
- **Keep capability bundles:** rejected; cannot model custom roles or department scope.
- **ABAC/policy engine (OPA/Casbin):** deferred; overkill for 22 permissions and five default roles.

## Consequences
- Positive: precise access, auditable changes, multi-company administration without multi-membership
  users, testable matrix.
- Negative: more tables and migration work; every route must declare a permission.
- Existing grants migrate through the legacy capability mapping; unmapped grants are reported.
- Revisit: policy engine only if rules become attribute-heavy; do not grow permissions per screen.

## Risks and mitigations
Privilege escalation → service-level checks, “cannot grant beyond own access”, G10 matrix.
Over-broad COMPANY scope → default roles reviewed and matrix-tested. Permission sprawl → catalogue
cap and permission-change skill. Lockout → last-admin guard + recovery runbook.

## Dependencies
`docs/access-control.md` (canonical), `docs/domain-model.md` §2.0, `docs/api.md` §2/§10.
