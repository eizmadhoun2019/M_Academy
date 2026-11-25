# Skill: Tenant-isolation test matrix

**Purpose:** Prove no query, cache, task, storage or report path leaks across companies.
**When to Use:** Every new service, selector, endpoint, task, export or cached value.

## Steps
1. Use the shared fixtures: company A with two departments, company B, a user with memberships in
   both, a suspended membership and a removed membership.
2. Act as each principal and assert: (a) lists contain nothing from the other company;
   (b) get/update/delete of a foreign id returns 404/403 without side effects; (c) no write
   touches the other company; (d) a department manager cannot read a sibling department;
   (e) a platform user without `platform.organization.access` cannot read training data.
3. Check every layer touched: ORM queryset, Redis key (`org:<id>:` segment), Celery task argument
   and payload, storage prefix `org/<id>/`, CSV/report row, notification recipient and audit row.
4. Keep the meta-tests green: every concrete company-owned model has `organization_id` and a
   company-scoped manager; every `*_id` lookup includes the company; no global table without an
   approved exception.

## Validation
Run the isolation suite (gate G7) locally and in CI. Deliberately remove one `organization_id`
filter and confirm the suite fails (detector proof), then restore it. A leak must fail the suite,
not be explained away.
