# Skill: Add or change a model

**Purpose:** Safe schema evolution that stays tenant-scoped and reversible.
**When to Use:** Any schema change.

## Steps
1. Update ARCHITECTURE §5 (entities/flows) first — docs lead the schema here.
2. Subclass `TenantModel`; statuses via `TextChoices` + `CheckConstraint`; enforce
   invariants in the DB (unique, check, partial unique); composite indexes start with
   `organization_id`.
3. `make makemigrations`; read the generated migration; ensure it is reversible and named
   meaningfully. Never edit an applied migration — fix forward.
4. Add/extend the factory in `academy/tests/factories.py`.
5. Register the model in the tenant-isolation meta-test if it is tenant-scoped.
6. Tests: constraint violations raise `IntegrityError`; defaults; `for_org` scoping.

## Validation
Migration applies and reverses (`migrate academy <prev>`); `makemigrations --check` clean;
docs updated; isolation meta-test green.
