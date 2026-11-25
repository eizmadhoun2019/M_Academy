# Skill: Add a service (business operation)

**Purpose:** Keep all write logic in the service layer, atomic, authorized, company-scoped and
event-driven.
**When to Use:** Any new write behavior.

## Steps
1. Signature: `def verb_noun(*, principal: Principal, organization: Organization, ...)` in
   `academy/services/<area>.py`. Never accept `organization_id` or a role from the request body
   without server resolution; the caller passes the resolved context.
2. Call `require_permission(principal, "<permission>", scope=Scope.COMPANY|DEPARTMENT|SELF,
   organization=organization, department_ids=...)`. Deny by default; raise
   `academy.exceptions.PermissionDenied`/`ScopeDenied`.
3. Load objects through `.for_org(organization)` (or a selector that does) and re-check the object
   scope; a foreign-company id is `NotFound`, not a 403 that confirms existence.
4. `with transaction.atomic():` write, enforce invariants (last admin, unique assignment,
   membership active), and lock rows with `select_for_update()` where concurrent writes race.
5. Emit events with `emit_on_commit(...)`; never call notifications/Hub directly. A post-commit
   handler resolves recipients from local users/memberships.
6. Record an `AuditEvent` in the same transaction for state-changing admin/security operations;
   for a denied admin attempt, record after rolling back to a savepoint.
7. Format dates in the company time zone only at the edge; store UTC.

## Validation
Tests: success, each rule violation, permission denied, wrong scope, wrong company (404),
idempotency if retryable, last-admin conflict; module coverage ≥ 85%; no business logic in
views/tasks/serializers; no Hub import in standalone paths.
