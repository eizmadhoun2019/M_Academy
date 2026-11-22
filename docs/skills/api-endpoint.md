# Skill: Add an API endpoint

**Purpose:** Consistent, authorized, documented REST operations.
**When to Use:** A new REST operation.

## Steps
1. Ensure the service/selector exists (see service skill).
2. Serializer validates shape only; view calls the service and maps domain exceptions to
   `{code, detail, fields}`.
3. Declare the required capability; add object-level checks (own enrollment / department scope).
4. Register the URL under `/api/v1/academy/`; update ARCHITECTURE §6 endpoint list.
5. Verify the OpenAPI schema builds with 0 warnings.

## Validation
Test matrix: 200/201, 400 validation, 401 anonymous, 403 capability, 403/404 other
organization, other user's object, pagination, query-count assertion for lists.
