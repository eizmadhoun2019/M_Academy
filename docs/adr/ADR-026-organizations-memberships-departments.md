# ADR-026 — First-class organizations, memberships and departments with composite FKs

- **Status:** Accepted (2026-11-25); membership cardinality amended by D-043
- **Date:** 2026-11-25
- **Deciders:** Project owner
- **Supersedes:** ADR-012 (membership read from Hub, no local projection)
- **References:** D-032, D-036, D-038, D-043; REQ-03, REQ-21, REQ-28

## Context
A single fixed `ACADEMY_ORGANIZATION_ID` and opaque `department_ref`/`user_ref` strings made
multi-company support impossible and allowed a parent record from one company to be referenced by
another without a database-level guarantee. Organization identity lived in configuration, not data.

## Decision
`Organization`, `Department`, `Membership` and `User` are first-class tables. `Organization` owns
company settings (name, default language, time zone, reminder hour, sender name, status).
`Department` is a per-company tree. `Membership` is the only place roles, grants, suspension and
department membership attach. Every tenant table has a non-null `organization_id` FK; parent
references use composite FKs `(organization_id, parent_id)` so a cross-company reference cannot be
stored. Each account has **at most one membership** in H1.5 (`UNIQUE (user_id)`); the company is
resolved server-side from that membership, never from a session selection or request value.
Platform administrators use `PlatformRoleAssignment` and need no membership or synthetic company.
Removal retains the membership row; a same-company restore may reuse it before anonymization,
while a move to another company is out of scope.

## Rationale
- Multi-tenancy is a product requirement, not a later extension.
- Company settings and locale belong to data, not environment variables.
- Composite FKs make isolation a database invariant; ORM filters remain the first line.
- A separate Membership keeps account state independent from company state, while one row per
  account keeps H1.5 unambiguous and avoids a company chooser.

## Alternatives considered
- **One company forever:** rejected; contradicts the approved vision.
- **Schema per company:** rejected; migration/ops complexity for the expected 10 companies.
- **Organization id only on top-level tables:** rejected; leaks through child references.
- **PostgreSQL RLS now:** assessed and deferred (ADR-027).

## Consequences
- Positive: true multi-company behavior, safe FKs, per-company settings, clear lifecycle.
- Negative: migrations rewrite every tenant table and backfill identities; all queries must scope.
- Legacy data maps through `docs/migration-h1.5.md`; unresolved refs or duplicate memberships
  block cutover.
- Adding multi-company users later requires an explicit decision and a constraint migration.
- Revisit: RLS, partitioning, sharding only on measured need.

## Risks and mitigations
Data mapping errors → dry-run, counts, backup, restore rehearsal. Cross-tenant leak → G7 isolation
suite and composite-FK tests. Overhead of organization joins → indexes lead with
`organization_id`; measure before optimizing.

## Dependencies
`docs/domain-model.md` §2.0, `docs/migration-h1.5.md`, `docs/api.md` §2–§4.
