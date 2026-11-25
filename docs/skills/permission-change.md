# Skill: Add or change a permission, role or scope

**Purpose:** Keep the permission catalogue, enforcement, UI and tests as one system.
**When to Use:** A new capability, a changed default role, a new scope rule or a grant rule.

## Steps
1. Justify the permission with a REQ and a task; reject duplicates and umbrella permissions that
   only wrap an existing one.
2. Add the row to `docs/access-control.md` §2 with its allowed scopes and one-sentence meaning;
   add it to the default roles in §3 only if the role truly needs it (least privilege).
3. Add it to the enforcement constants and the catalogue seed/migration; a data test compares the
   catalogue with the document exactly.
4. Enforce in the service and route; add the nav/permission mapping and a screen action only when
   a screen uses it. Never check a role name or a UI flag server-side.
5. Add allow/deny/scope cases to the G10 matrix, plus escalation and last-admin cases if the
   permission can change access.
6. Record the change in `docs/api.md` (capability column), `docs/domain-model.md` if a table
   changes, and `LOG.md`; audit the first grant/change.

## Validation
`test_catalogue_integrity` and the role×route matrix pass; no route lacks a declared permission;
no default role gains a platform permission; a company admin cannot grant beyond their own access.
