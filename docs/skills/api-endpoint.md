# Skill: Add an API endpoint

**Purpose:** Consistent, authorized, documented REST operations with explicit company context.
**When to Use:** A new REST operation.

## Steps
1. Ensure the service/selector exists (service skill); selectors are the only read path.
2. Serializer validates shape only; a view resolves the principal and active company from the
   session/URL context, calls the service and maps domain exceptions to `{code, detail, fields}`.
3. Declare the exact `academy.*`/`platform.*` permission from `docs/access-control.md`;
   add object-level checks (own enrollment, department scope, platform read-only access).
4. Register under the base `/api/v1/academy/` — company routes directly, platform routes under
   `platform/` — with a named
   route; add the route to `docs/api.md` and its capability column.
5. Keep the response free of raw internal ids where a name exists; never return another
   company's object or a raw storage key.
6. Verify the OpenAPI schema builds with 0 warnings and the versioning/backward-compatibility
   rule holds (`docs/api.md` §15).

## Validation
Matrix: 200/201, 400 validation, 401 anonymous, 403 capability/scope, 404 other company, other
user's object, CSRF on unsafe methods, pagination, query-count assertion for lists, audit event
for writes. No Hub import in standalone mode.
