# Skill: Add or change a model

**Purpose:** Safe schema evolution that stays company-scoped, references the right owner and is
reversible.
**When to Use:** Any schema change.

## Steps
1. Identify the **data owner** first: company data → `TenantModel` with `organization_id`;
   identity → `User`/`Membership`; platform-global → an approved exception recorded in
   ARCHITECTURE §5 and `docs/domain-model.md` §3. Never add a global table for convenience.
2. Update `docs/domain-model.md` (entity, fields, constraints, lifecycle) **before** the
   migration; update `ARCHITECTURE.md` §5 only if a boundary/flow changes.
3. Use UUID PKs (`uuid4` now; no migration of existing PKs), `PROTECT`/`RESTRICT` for
   referenced history, status via `TextChoices` + `CheckConstraint`, and composite FKs
   `(organization_id, <parent_id>)` for cross-table ownership.
4. Indexes: composite company indexes start with `organization_id`; add partial/unique indexes
   for real access patterns, not every column. Record the query that justifies an index.
5. `make makemigrations`; read the generated migration; ensure it is reversible and named
   meaningfully. Never edit an applied migration — fix forward. A data migration is separate,
   idempotent and runs with a dry-run/report.
6. For a company-scoped model, add/extend the factory and the isolation meta-test; for identity
   or membership, extend the auth/RBAC fixtures.
7. Tests: constraint violations raise `IntegrityError`; composite FK rejects a parent from another
   company; defaults; `for_org` scoping; migration applies and reverses on a restored copy when
   data is transformed.

## Validation
Migration applies and reverses (`migrate academy <prev>`); `makemigrations --check` clean; docs
updated; isolation meta-test green; no nullable company column left on a tenant table.
