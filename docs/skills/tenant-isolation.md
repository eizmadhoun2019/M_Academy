# Skill: Tenant-isolation test matrix

**Purpose:** Prove no query path leaks across organizations.
**When to Use:** Every new service, selector, and endpoint.

## Steps
1. Use the shared two-organization fixture; create rows in org A and org B via factories.
2. Act as org B and assert: (a) lists contain nothing from A; (b) get/update/delete of A's
   ids returns not-found/forbidden; (c) no write touches A's rows.
3. Keep the meta-tests green: every concrete model subclasses `TenantModel`; every `*_id`
   lookup in selectors includes `organization_id`.

## Validation
Run `docker compose exec -T web pytest academy/tests/test_tenant_isolation.py` (same
check as CI gate G7). A leak must fail the suite.
